from datetime import datetime, timedelta, timezone
from pathlib import Path
import inspect
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service
from edupass.modules.credencial_qr import credencial_service
from edupass.modules.validacion_qr import validacion_service
from edupass.persistence import database_manager
from edupass.shared.errors import (
    AlumnoInactivoError,
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    RepositoryError,
)


class TestValidacionQrService(unittest.TestCase):
    TOKEN_A = "A" * 43
    TOKEN_B = "B" * 43
    AHORA = datetime(2026, 7, 27, 12, 0, 0, tzinfo=timezone.utc)

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "validacion_qr.sqlite"
        )
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        self.alumno = alumnos_service.registrar_alumno(
            "Alumno Validacion",
            "VAL-0001",
            "3",
            "A",
            estado="activo",
            database_path=self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _clock(self, value=None):
        selected = value or self.AHORA
        return lambda: selected

    def _generar(self, token=None, now=None):
        selected = token or self.TOKEN_A
        return credencial_service.generar_credencial(
            self.alumno["alumno_id"],
            self.database_path,
            self._clock(now),
            lambda: selected,
        )

    def _consume(self, token=None, now=None):
        return validacion_service.consumir_token_qr(
            token or self.TOKEN_A,
            self.database_path,
            self._clock(now),
        )

    def _count(self, table):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(
                f"SELECT COUNT(*) FROM {table};"
            ).fetchone()[0]
        finally:
            connection.close()

    def test_token_vigente_es_consumido(self):
        self._generar()

        result = self._consume()

        self.assertEqual(result["resultado"], "consumido")
        self.assertEqual(result["alumno_id"], self.alumno["alumno_id"])

    def test_mensaje_de_exito_es_exacto(self):
        self._generar()

        result = self._consume()

        self.assertEqual(
            result["mensaje"],
            "Token válido y consumido; no se registró ningún movimiento.",
        )

    def test_exito_indica_que_no_registro_movimiento(self):
        self._generar()

        self.assertTrue(self._consume()["no_registro_movimiento"])

    def test_respuesta_no_contiene_token_ni_hash(self):
        self._generar()

        result = self._consume()

        self.assertNotIn("token", result)
        self.assertNotIn("token_hash", result)
        self.assertNotIn(self.TOKEN_A, result.values())

    def test_token_con_espacios_externos_es_aceptado(self):
        self._generar()

        result = validacion_service.consumir_token_qr(
            f"  {self.TOKEN_A}  ",
            self.database_path,
            self._clock(),
        )

        self.assertEqual(result["resultado"], "consumido")

    def test_token_vacio_es_rechazado(self):
        for token in ("", "   "):
            with self.subTest(token=repr(token)):
                with self.assertRaises(QRInvalidoError):
                    validacion_service.consumir_token_qr(
                        token, self.database_path, self._clock()
                    )

    def test_token_no_textual_es_rechazado(self):
        for token in (None, 123, True, [], {}):
            with self.subTest(token=token):
                with self.assertRaises(QRInvalidoError):
                    validacion_service.consumir_token_qr(
                        token, self.database_path, self._clock()
                    )

    def test_token_demasiado_corto_es_rechazado(self):
        with self.assertRaises(QRInvalidoError):
            validacion_service.consumir_token_qr(
                "A" * 42, self.database_path, self._clock()
            )

    def test_token_demasiado_largo_es_rechazado(self):
        with self.assertRaises(QRInvalidoError):
            validacion_service.consumir_token_qr(
                "A" * 44, self.database_path, self._clock()
            )

    def test_caracteres_invalidos_son_rechazados(self):
        for token in ("A" * 42 + "=", "A" * 42 + "+", "A" * 42 + "/"):
            with self.subTest(token=token[-1]):
                with self.assertRaises(QRInvalidoError):
                    validacion_service.consumir_token_qr(
                        token, self.database_path, self._clock()
                    )

    def test_token_inexistente_es_rechazado(self):
        with self.assertRaisesRegex(QRInvalidoError, "no es válido"):
            self._consume()

    def test_token_alterado_es_rechazado(self):
        self._generar()
        altered = self.TOKEN_A[:-1] + "B"

        with self.assertRaises(QRInvalidoError):
            self._consume(altered)

    def test_token_vencido_es_rechazado(self):
        self._generar()

        with self.assertRaisesRegex(QRVencidoError, "vencido"):
            self._consume(now=self.AHORA + timedelta(seconds=31))

    def test_instante_exacto_de_vencimiento_es_rechazado(self):
        self._generar()

        with self.assertRaises(QRVencidoError):
            self._consume(now=self.AHORA + timedelta(seconds=30))

    def test_token_utilizado_es_rechazado(self):
        self._generar()
        self._consume()

        with self.assertRaisesRegex(QRUtilizadoError, "utilizado"):
            self._consume()

    def test_token_invalidado_es_rechazado_como_invalido(self):
        self._generar(self.TOKEN_A)
        self._generar(self.TOKEN_B)

        with self.assertRaises(QRInvalidoError):
            self._consume(self.TOKEN_A)

    def test_alumno_inactivo_despues_de_generacion_es_rechazado(self):
        self._generar()
        alumnos_service.desactivar_alumno(
            self.alumno["alumno_id"], self.database_path
        )

        with self.assertRaisesRegex(AlumnoInactivoError, "inactivo"):
            self._consume()

    def test_dos_consumos_tienen_un_solo_exito(self):
        self._generar()
        first = self._consume()

        with self.assertRaises(QRUtilizadoError):
            self._consume()

        self.assertEqual(first["resultado"], "consumido")

    def test_error_de_repositorio_se_propaga(self):
        original = RepositoryError("fallo controlado")
        with patch.object(
            validacion_service.qr_token_repository,
            "consumir_condicionalmente",
            side_effect=original,
        ):
            with self.assertRaises(RepositoryError) as context:
                self._consume()

        self.assertIs(context.exception, original)

    def test_consumo_no_crea_movimientos(self):
        self._generar()
        before = self._count("movimientos")

        self._consume()

        self.assertEqual(before, 0)
        self.assertEqual(self._count("movimientos"), 0)

    def test_rechazos_no_crean_intentos_rechazados(self):
        self._generar()
        for operation in (
            lambda: self._consume(self.TOKEN_A[:-1] + "B"),
            lambda: self._consume(now=self.AHORA + timedelta(seconds=31)),
        ):
            with self.assertRaises((QRInvalidoError, QRVencidoError)):
                operation()

        self.assertEqual(self._count("intentos_rechazados"), 0)

    def test_servicio_no_importa_flask_ni_pyside6(self):
        source = inspect.getsource(validacion_service)

        self.assertNotIn("flask", source.lower())
        self.assertNotIn("pyside6", source.lower())

    def test_resultado_persistido_no_contiene_token_original(self):
        self._generar()
        self._consume()
        connection = database_manager.get_connection(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            row = dict(connection.execute("SELECT * FROM qr_tokens;").fetchone())
        finally:
            connection.close()

        self.assertNotIn(self.TOKEN_A, row.values())
        self.assertNotIn("token", row)


if __name__ == "__main__":
    unittest.main()
