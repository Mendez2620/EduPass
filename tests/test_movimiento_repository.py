from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service
from edupass.modules.auth import usuarios_service
from edupass.modules.credencial_qr import credencial_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import movimiento_repository
from edupass.shared.errors import (
    AlumnoInactivoError,
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    RepositoryError,
    SecuenciaMovimientoError,
    UsuarioEscanerInvalidoError,
)
from edupass.shared.time_utils import serializar_utc


class TestMovimientoRepository(unittest.TestCase):
    PASSWORD = "ClaveFicticiaSegura123"
    NOW = datetime(2026, 7, 30, 18, 0, 0, tzinfo=timezone.utc)
    NOW_TEXT = serializar_utc(NOW)

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "movimientos.sqlite"
        )
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        self.alumno = alumnos_service.registrar_alumno(
            "Alumno Movimiento",
            "MOV-0001",
            "3",
            "A",
            estado="activo",
            database_path=self.database_path,
        )
        self.scanner = usuarios_service.crear_usuario_demo(
            "Escaner Movimiento",
            "scanner.movimientos@edupass.test",
            self.PASSWORD,
            "escaner",
            self.database_path,
        )
        self.admin = usuarios_service.crear_usuario_demo(
            "Admin Movimiento",
            "admin.movimientos@edupass.test",
            self.PASSWORD,
            "administrador",
            self.database_path,
        )
        self.inactive_scanner = usuarios_service.crear_usuario_demo(
            "Escaner Inactivo",
            "scanner.inactivo@edupass.test",
            self.PASSWORD,
            "escaner",
            self.database_path,
        )
        self._execute(
            "UPDATE usuarios SET estado = ? WHERE usuario_id = ?;",
            ("inactivo", self.inactive_scanner["usuario_id"]),
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _execute(self, query, parameters=()):
        connection = database_manager.get_connection(self.database_path)
        try:
            cursor = connection.execute(query, parameters)
            connection.commit()
            return cursor.rowcount
        finally:
            connection.close()

    def _scalar(self, query, parameters=()):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(query, parameters).fetchone()[0]
        finally:
            connection.close()

    def _row(self, query, parameters=()):
        connection = database_manager.get_connection(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(query, parameters).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()

    def _generate(self, character="A", alumno_id=None, now=None):
        return credencial_service.generar_credencial(
            alumno_id or self.alumno["alumno_id"],
            self.database_path,
            lambda: now or self.NOW,
            lambda: character * 43,
        )["token"]

    def _register(self, token, movement_type, now_text=None, user_id=None):
        return movimiento_repository.registrar_con_token(
            hashlib.sha256(token.encode("ascii")).hexdigest(),
            movement_type,
            now_text or self.NOW_TEXT,
            user_id or self.scanner["usuario_id"],
            "acceso_principal",
            self.database_path,
        )

    def _entry(self, character="A"):
        token = self._generate(character)
        return self._register(token, "entrada")

    def _qr_state(self, token):
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        return self._row(
            "SELECT estado, usado_en FROM qr_tokens WHERE token_hash = ?;",
            (token_hash,),
        )

    def test_primera_entrada_valida(self):
        result = self._entry()
        self.assertEqual(result["tipo_movimiento"], "entrada")
        self.assertEqual(self._scalar("SELECT COUNT(*) FROM movimientos;"), 1)

    def test_salida_valida_despues_de_entrada(self):
        self._entry("A")
        token = self._generate("B")
        result = self._register(token, "salida")
        self.assertEqual(result["tipo_movimiento"], "salida")

    def test_nueva_entrada_despues_de_salida(self):
        self._entry("A")
        self._register(self._generate("B"), "salida")
        result = self._register(self._generate("C"), "entrada")
        self.assertEqual(result["tipo_movimiento"], "entrada")
        self.assertEqual(self._scalar("SELECT COUNT(*) FROM movimientos;"), 3)

    def test_salida_sin_movimientos_previos(self):
        token = self._generate()
        with self.assertRaisesRegex(SecuenciaMovimientoError, "entrada previa"):
            self._register(token, "salida")
        self.assertEqual(self._qr_state(token)["estado"], "activo")

    def test_doble_entrada(self):
        self._entry("A")
        token = self._generate("B")
        with self.assertRaisesRegex(SecuenciaMovimientoError, "otra entrada"):
            self._register(token, "entrada")
        self.assertEqual(self._qr_state(token)["estado"], "activo")

    def test_doble_salida(self):
        self._entry("A")
        self._register(self._generate("B"), "salida")
        token = self._generate("C")
        with self.assertRaisesRegex(SecuenciaMovimientoError, "otra salida"):
            self._register(token, "salida")
        self.assertEqual(self._qr_state(token)["estado"], "activo")

    def test_qr_inexistente(self):
        with self.assertRaises(QRInvalidoError):
            movimiento_repository.registrar_con_token(
                "f" * 64,
                "entrada",
                self.NOW_TEXT,
                self.scanner["usuario_id"],
                "acceso_principal",
                self.database_path,
            )

    def test_qr_vencido(self):
        token = self._generate()
        expired = serializar_utc(self.NOW + timedelta(seconds=30))
        with self.assertRaises(QRVencidoError):
            self._register(token, "entrada", expired)

    def test_qr_utilizado(self):
        token = self._generate()
        self._register(token, "entrada")
        with self.assertRaises(QRUtilizadoError):
            self._register(token, "salida")

    def test_qr_invalidado(self):
        old_token = self._generate("A")
        self._generate("B")
        with self.assertRaises(QRInvalidoError):
            self._register(old_token, "entrada")

    def test_alumno_inactivo(self):
        token = self._generate()
        alumnos_service.desactivar_alumno(
            self.alumno["alumno_id"], self.database_path
        )
        with self.assertRaises(AlumnoInactivoError):
            self._register(token, "entrada")

    def test_usuario_inexistente(self):
        token = self._generate()
        with self.assertRaises(UsuarioEscanerInvalidoError):
            self._register(token, "entrada", user_id=99999)
        self.assertEqual(self._qr_state(token)["estado"], "activo")

    def test_usuario_inactivo(self):
        token = self._generate()
        with self.assertRaises(UsuarioEscanerInvalidoError):
            self._register(
                token,
                "entrada",
                user_id=self.inactive_scanner["usuario_id"],
            )
        self.assertEqual(self._qr_state(token)["estado"], "activo")

    def test_usuario_administrador_rechazado(self):
        token = self._generate()
        with self.assertRaises(UsuarioEscanerInvalidoError):
            self._register(token, "entrada", user_id=self.admin["usuario_id"])
        self.assertEqual(self._qr_state(token)["estado"], "activo")

    def test_punto_persistido(self):
        result = self._entry()
        self.assertEqual(result["punto_plantel"], "acceso_principal")

    def test_area_es_nula(self):
        result = self._entry()
        row = self._row(
            "SELECT area_id FROM movimientos WHERE movimiento_id = ?;",
            (result["movimiento_id"],),
        )
        self.assertIsNone(row["area_id"])

    def test_dispositivo_es_nulo(self):
        result = self._entry()
        row = self._row(
            "SELECT dispositivo_id FROM movimientos WHERE movimiento_id = ?;",
            (result["movimiento_id"],),
        )
        self.assertIsNone(row["dispositivo_id"])

    def test_usuario_responsable_persistido(self):
        result = self._entry()
        self.assertEqual(result["usuario_id"], self.scanner["usuario_id"])
        self.assertEqual(result["usuario_nombre"], "Escaner Movimiento")

    def test_resultado_seguro(self):
        result = self._entry()
        self.assertEqual(
            set(result),
            {
                "movimiento_id",
                "alumno_id",
                "alumno_nombre",
                "tipo_movimiento",
                "fecha_hora",
                "punto_plantel",
                "usuario_id",
                "usuario_nombre",
            },
        )
        self.assertNotIn("token", result)
        self.assertNotIn("token_hash", result)

    def test_consulta_ultimo_movimiento(self):
        first = self._entry("A")
        second = self._register(self._generate("B"), "salida")
        last = movimiento_repository.obtener_ultimo_por_alumno(
            self.alumno["alumno_id"], self.database_path
        )
        self.assertEqual(last["movimiento_id"], second["movimiento_id"])
        self.assertNotEqual(last["movimiento_id"], first["movimiento_id"])

    def test_consulta_ultimo_movimiento_vacia(self):
        self.assertIsNone(
            movimiento_repository.obtener_ultimo_por_alumno(
                self.alumno["alumno_id"], self.database_path
            )
        )

    def test_consulta_por_id(self):
        expected = self._entry()
        result = movimiento_repository.obtener_por_id(
            expected["movimiento_id"], self.database_path
        )
        self.assertEqual(result, expected)

    def test_consulta_por_id_inexistente(self):
        self.assertIsNone(
            movimiento_repository.obtener_por_id(99999, self.database_path)
        )

    def test_error_sqlite_traducido(self):
        original = sqlite3.OperationalError("fallo controlado")
        with patch.object(
            movimiento_repository.database_manager,
            "get_connection",
            side_effect=original,
        ):
            with self.assertRaises(RepositoryError) as context:
                movimiento_repository.obtener_por_id(1, self.database_path)
        self.assertIs(context.exception.__cause__, original)

    def test_rollback_si_falla_insert_despues_del_consumo(self):
        token = self._generate()
        original_loader = movimiento_repository._load_query

        def controlled_query(file_name):
            if file_name == movimiento_repository._INSERT_FILE:
                return "INSERT INTO tabla_inexistente VALUES (?, ?, ?, ?, ?);"
            return original_loader(file_name)

        with patch.object(
            movimiento_repository,
            "_load_query",
            side_effect=controlled_query,
        ):
            with self.assertRaises(RepositoryError):
                self._register(token, "entrada")

        self.assertEqual(self._qr_state(token)["estado"], "activo")
        self.assertIsNone(self._qr_state(token)["usado_en"])
        self.assertEqual(self._scalar("SELECT COUNT(*) FROM movimientos;"), 0)

    def test_rechazo_secuencia_no_crea_intento_rechazado(self):
        token = self._generate()
        with self.assertRaises(SecuenciaMovimientoError):
            self._register(token, "salida")
        self.assertEqual(
            self._scalar("SELECT COUNT(*) FROM intentos_rechazados;"), 0
        )

    def test_concurrencia_permite_exactamente_un_movimiento(self):
        token = self._generate()
        barrier = threading.Barrier(2, timeout=5)

        def register_once():
            barrier.wait()
            try:
                self._register(token, "entrada")
                return "registrado"
            except QRUtilizadoError:
                return "utilizado"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: register_once(), range(2)))

        self.assertEqual(results.count("registrado"), 1)
        self.assertEqual(results.count("utilizado"), 1)
        self.assertEqual(self._scalar("SELECT COUNT(*) FROM movimientos;"), 1)
        self.assertEqual(self._qr_state(token)["estado"], "utilizado")

    def test_indice_movimientos_existe(self):
        indexes = self._scalar(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type = 'index' AND name = ?;",
            ("idx_movimientos_alumno_fecha",),
        )
        self.assertEqual(indexes, 1)

    def test_inicializacion_del_indice_es_idempotente(self):
        before = self._scalar("SELECT COUNT(*) FROM alumnos;")
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        after = self._scalar("SELECT COUNT(*) FROM alumnos;")
        self.assertEqual(after, before)
        self.assertEqual(
            self._scalar(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type = 'index' AND name = ?;",
                ("idx_movimientos_alumno_fecha",),
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
