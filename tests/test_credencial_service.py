from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service
from edupass.modules.credencial_qr import credencial_service
from edupass.modules.credencial_qr._token_utils import interpretar_utc
from edupass.persistence import database_manager
from edupass.persistence.repositories import qr_token_repository
from edupass.shared.errors import (
    AlumnoInactivoError,
    AlumnoNoEncontradoError,
    QRNoDisponibleError,
    RepositoryError,
    ValidationError,
)


class TestCredencialService(unittest.TestCase):
    TOKEN_A = "A" * 43
    TOKEN_B = "B" * 43
    AHORA = datetime(2026, 7, 27, 12, 0, 0, 123456, tzinfo=timezone.utc)

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "credencial_service.sqlite"
        )
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        self.activo = alumnos_service.registrar_alumno(
            "Ana Alumna Demo",
            "EDUPASS-1234",
            "3",
            "A",
            fotografia="C:/privada/ana.png",
            estado="activo",
            database_path=self.database_path,
        )
        self.inactivo = alumnos_service.registrar_alumno(
            "Luis Alumno Demo",
            "INAC-5678",
            "4",
            "B",
            estado="inactivo",
            database_path=self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _clock(self):
        return self.AHORA

    def _generar(self, token=None, clock=None):
        selected = token or self.TOKEN_A
        return credencial_service.generar_credencial(
            self.activo["alumno_id"],
            self.database_path,
            clock or self._clock,
            lambda: selected,
        )

    def test_generar_para_alumno_activo(self):
        credential = self._generar()

        self.assertEqual(credential["alumno_id"], self.activo["alumno_id"])
        self.assertEqual(credential["estado"], "activo")
        self.assertEqual(credential["token"], self.TOKEN_A)

    def test_rechazar_alumno_inexistente(self):
        with self.assertRaises(AlumnoNoEncontradoError):
            credencial_service.generar_credencial(
                9999,
                self.database_path,
                self._clock,
                lambda: self.TOKEN_A,
            )

    def test_rechazar_alumno_inactivo(self):
        with self.assertRaisesRegex(AlumnoInactivoError, "inactivo"):
            credencial_service.generar_credencial(
                self.inactivo["alumno_id"],
                self.database_path,
                self._clock,
                lambda: self.TOKEN_A,
            )

    def test_vigencia_exacta_de_treinta_segundos(self):
        credential = self._generar()

        generated = interpretar_utc(credential["generado_en"])
        expires = interpretar_utc(credential["expira_en"])
        self.assertEqual(expires - generated, timedelta(seconds=30))
        self.assertEqual(credential["vigencia_segundos"], 30)

    def test_fecha_se_normaliza_a_utc(self):
        offset = timezone(timedelta(hours=-6))
        local = datetime(2026, 7, 27, 6, 0, tzinfo=offset)

        credential = self._generar(clock=lambda: local)

        self.assertEqual(credential["generado_en"], "2026-07-27T12:00:00.000000Z")

    def test_formato_temporal_es_fijo(self):
        credential = self._generar()
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"

        self.assertRegex(credential["generado_en"], pattern)
        self.assertRegex(credential["expira_en"], pattern)

    def test_token_tiene_longitud_43(self):
        credential = credencial_service.generar_credencial(
            self.activo["alumno_id"],
            self.database_path,
            self._clock,
        )

        self.assertEqual(len(credential["token"]), 43)

    def test_token_tiene_formato_base64url(self):
        credential = credencial_service.generar_credencial(
            self.activo["alumno_id"],
            self.database_path,
            self._clock,
        )

        self.assertIsNotNone(re.fullmatch(r"[A-Za-z0-9_-]{43}", credential["token"]))

    def test_token_factory_es_inyectable(self):
        factory = Mock(return_value=self.TOKEN_A)

        credential = credencial_service.generar_credencial(
            self.activo["alumno_id"],
            self.database_path,
            self._clock,
            factory,
        )

        factory.assert_called_once_with()
        self.assertEqual(credential["token"], self.TOKEN_A)

    def test_token_no_contiene_datos_del_alumno(self):
        credential = self._generar()
        token = credential["token"]

        for value in (
            self.activo["nombre"],
            self.activo["matricula"],
            str(self.activo["alumno_id"]),
            "2026-07-27",
        ):
            self.assertNotIn(value, token)

    def test_repositorio_recibe_hash_y_no_token_original(self):
        with patch.object(
            credencial_service.qr_token_repository,
            "reemplazar_token_activo",
            return_value={},
        ) as mocked:
            self._generar()

        args = mocked.call_args.args
        expected_hash = hashlib.sha256(self.TOKEN_A.encode("ascii")).hexdigest()
        self.assertEqual(args[1], expected_hash)
        self.assertNotIn(self.TOKEN_A, args)

    def test_respuesta_segura_no_incluye_token_hash(self):
        credential = self._generar()

        self.assertNotIn("token_hash", credential)
        self.assertNotIn(hashlib.sha256(self.TOKEN_A.encode()).hexdigest(), credential.values())

    def test_respuesta_no_incluye_fotografia(self):
        credential = self._generar()

        self.assertNotIn("fotografia", credential)
        self.assertNotIn("C:/privada/ana.png", credential.values())

    def test_matricula_es_enmascarada(self):
        credential = self._generar()

        self.assertEqual(credential["matricula_enmascarada"], "********1234")
        self.assertNotIn(self.activo["matricula"], credential.values())

    def test_matricula_corta_se_oculta_completa(self):
        corto = alumnos_service.registrar_alumno(
            "Alumno Corto",
            "A12",
            "1",
            "C",
            estado="activo",
            database_path=self.database_path,
        )

        credential = credencial_service.generar_credencial(
            corto["alumno_id"],
            self.database_path,
            self._clock,
            lambda: self.TOKEN_B,
        )

        self.assertEqual(credential["matricula_enmascarada"], "***")

    def test_renovacion_produce_token_diferente(self):
        first = self._generar(self.TOKEN_A)
        second = credencial_service.renovar_token_qr(
            self.activo["alumno_id"],
            self.database_path,
            self._clock,
            lambda: self.TOKEN_B,
        )

        self.assertNotEqual(first["token"], second["token"])

    def test_renovacion_invalida_token_anterior(self):
        self._generar(self.TOKEN_A)
        credencial_service.renovar_token_qr(
            self.activo["alumno_id"],
            self.database_path,
            self._clock,
            lambda: self.TOKEN_B,
        )

        old = qr_token_repository.obtener_por_hash(
            hashlib.sha256(self.TOKEN_A.encode()).hexdigest(),
            self.database_path,
        )
        self.assertEqual(old["estado"], "invalidado")

    def test_obtener_metadata_no_devuelve_token(self):
        self._generar()

        metadata = credencial_service.obtener_metadata_vigente(
            self.activo["alumno_id"],
            self.database_path,
            self._clock,
        )

        self.assertNotIn("token", metadata)
        self.assertNotIn("token_hash", metadata)
        self.assertFalse(metadata["token_recuperable"])
        self.assertIn("no puede reconstruirse", metadata["mensaje"])

    def test_obtener_metadata_sin_vigente_genera_error(self):
        with self.assertRaises(QRNoDisponibleError):
            credencial_service.obtener_metadata_vigente(
                self.activo["alumno_id"],
                self.database_path,
                self._clock,
            )

    def test_obtener_metadata_en_instante_de_vencimiento_falla(self):
        credential = self._generar()
        expiration = interpretar_utc(credential["expira_en"])

        with self.assertRaises(QRNoDisponibleError):
            credencial_service.obtener_metadata_vigente(
                self.activo["alumno_id"],
                self.database_path,
                lambda: expiration,
            )

    def test_reloj_ingenuo_es_rechazado(self):
        naive = datetime(2026, 7, 27, 12, 0, 0)

        with self.assertRaisesRegex(ValidationError, "zona horaria"):
            self._generar(clock=lambda: naive)

    def test_token_factory_invalida_es_rechazada_sin_filtrarla(self):
        invalid = "token-personal-invalido"

        with self.assertRaises(ValidationError) as context:
            self._generar(token=invalid)

        self.assertNotIn(invalid, str(context.exception))
        self.assertEqual(len(qr_token_repository.obtener_por_hash("f" * 64, self.database_path) or {}), 0)

    def test_error_de_repositorio_se_propaga_controladamente(self):
        original = RepositoryError("fallo controlado")
        with patch.object(
            credencial_service.qr_token_repository,
            "reemplazar_token_activo",
            side_effect=original,
        ):
            with self.assertRaises(RepositoryError) as context:
                self._generar()

        self.assertIs(context.exception, original)


if __name__ == "__main__":
    unittest.main()
