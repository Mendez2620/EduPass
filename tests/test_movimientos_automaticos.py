from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service
from edupass.modules.auth import usuarios_service
from edupass.modules.credencial_qr import credencial_service
from edupass.modules.movimientos import movimientos_service
from edupass.persistence import database_manager
from edupass.shared.errors import (
    EstadoMovimientoCambiadoError,
    QRUtilizadoError,
    QRVencidoError,
)


class TestMovimientosAutomaticos(unittest.TestCase):
    PASSWORD = "ClaveAutomatica123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "automaticos.sqlite"
        )
        database_manager.initialize_database(self.database_path)
        self.scanner = usuarios_service.crear_escaner(
            "Escaner Automatico",
            "scanner.auto@edupass.test",
            self.PASSWORD,
            self.database_path,
        )
        self.alumno = alumnos_service.registrar_alumno(
            "Alumno Automatico",
            "AUTO-0001",
            "2",
            "B",
            estado="activo",
            database_path=self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _generate(self, clock=None):
        return credencial_service.generar_credencial(
            self.alumno["alumno_id"],
            self.database_path,
            clock,
        )["token"]

    def _preview(self, token):
        return movimientos_service.previsualizar_movimiento_con_token(
            token,
            self.database_path,
        )

    def _confirm(self, preview, expected=None):
        return movimientos_service.confirmar_movimiento_automatico(
            preview["token_hash"],
            expected or preview["tipo_movimiento"],
            self.scanner["usuario_id"],
            database_path=self.database_path,
        )

    def _query_one(self, sql, parameters=()):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(sql, parameters).fetchone()
        finally:
            connection.close()

    def _count(self, table):
        return self._query_one(f"SELECT COUNT(*) FROM {table};")[0]

    def _token_state(self, token):
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        return self._query_one(
            "SELECT estado FROM qr_tokens WHERE token_hash = ?;",
            (token_hash,),
        )[0]

    def test_first_preview_is_entry_and_does_not_write(self):
        token = self._generate()
        preview = self._preview(token)
        self.assertEqual(preview["tipo_movimiento"], "entrada")
        self.assertEqual(preview["matricula_enmascarada"], "*****0001")
        self.assertEqual(self._token_state(token), "activo")
        self.assertEqual(self._count("movimientos"), 0)

    def test_after_entry_preview_is_exit(self):
        first = self._preview(self._generate())
        self.assertEqual(self._confirm(first)["tipo_movimiento"], "entrada")
        second = self._preview(self._generate())
        self.assertEqual(second["tipo_movimiento"], "salida")

    def test_after_exit_preview_returns_to_entry(self):
        first = self._preview(self._generate())
        self._confirm(first)
        second = self._preview(self._generate())
        self._confirm(second)
        third = self._preview(self._generate())
        self.assertEqual(third["tipo_movimiento"], "entrada")

    def test_confirmation_consumes_once_and_registers_detected_type(self):
        token = self._generate()
        preview = self._preview(token)
        result = self._confirm(preview)
        self.assertEqual(result["tipo_movimiento"], "entrada")
        self.assertEqual(self._token_state(token), "utilizado")
        self.assertEqual(self._count("movimientos"), 1)
        with self.assertRaises(QRUtilizadoError):
            self._confirm(preview)

    def test_manipulated_expected_type_cannot_force_exit(self):
        token = self._generate()
        preview = self._preview(token)
        with self.assertRaises(EstadoMovimientoCambiadoError) as context:
            self._confirm(preview, "salida")
        self.assertEqual(context.exception.tipo_movimiento_actual, "entrada")
        self.assertEqual(self._token_state(token), "activo")
        self.assertEqual(self._count("movimientos"), 0)

    def test_state_change_between_preview_and_confirmation_does_not_write(self):
        token = self._generate()
        preview = self._preview(token)
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute(
                "INSERT INTO movimientos (alumno_id, tipo_movimiento, "
                "fecha_hora, punto_plantel, usuario_id) VALUES (?, ?, ?, ?, ?);",
                (
                    self.alumno["alumno_id"],
                    "entrada",
                    datetime.now(timezone.utc).isoformat(),
                    "acceso_principal",
                    self.scanner["usuario_id"],
                ),
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(EstadoMovimientoCambiadoError) as context:
            self._confirm(preview)
        self.assertEqual(context.exception.tipo_movimiento_actual, "salida")
        self.assertEqual(self._token_state(token), "activo")
        self.assertEqual(self._count("movimientos"), 1)

    def test_expired_qr_is_rejected_during_preview(self):
        old = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = self._generate(clock=lambda: old)
        with self.assertRaises(QRVencidoError):
            self._preview(token)

    def test_automatic_repository_keeps_begin_immediate(self):
        repository = (
            SRC_PATH / "edupass" / "persistence" / "repositories" /
            "movimiento_repository.py"
        ).read_text(encoding="utf-8")
        self.assertIn('connection.execute("BEGIN IMMEDIATE;")', repository)
        self.assertIn("registrar_automatico_con_token", repository)
        self.assertIn("_determinar_tipo(last_row)", repository)


if __name__ == "__main__":
    unittest.main()
