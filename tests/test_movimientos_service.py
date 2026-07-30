from datetime import datetime, timedelta, timezone
import hashlib
import inspect
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.movimientos import movimientos_service
from edupass.shared.errors import (
    AlumnoInactivoError,
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    RepositoryError,
    SecuenciaMovimientoError,
    TipoMovimientoInvalidoError,
    UsuarioEscanerInvalidoError,
    ValidationError,
)


class TestMovimientosService(unittest.TestCase):
    TOKEN = "A" * 43
    NOW = datetime(2026, 7, 30, 18, 0, 0, tzinfo=timezone.utc)
    REPOSITORY_RESULT = {
        "movimiento_id": 7,
        "alumno_id": 3,
        "alumno_nombre": "Alumno Ficticio",
        "tipo_movimiento": "entrada",
        "fecha_hora": "2026-07-30T18:00:00.000000Z",
        "punto_plantel": "acceso_principal",
        "usuario_id": 5,
        "usuario_nombre": "Escaner Ficticio",
    }

    def _call(self, movement_type="entrada", **kwargs):
        result = dict(self.REPOSITORY_RESULT)
        result["tipo_movimiento"] = movement_type.strip().lower()
        with patch.object(
            movimientos_service.movimiento_repository,
            "registrar_con_token",
            return_value=result,
        ) as repository_mock:
            response = movimientos_service.registrar_movimiento_con_token(
                self.TOKEN,
                movement_type,
                5,
                clock=lambda: self.NOW,
                **kwargs,
            )
        return response, repository_mock

    def test_normaliza_entrada(self):
        result, repository = self._call("  Entrada  ")
        self.assertEqual(result["tipo_movimiento"], "entrada")
        self.assertEqual(repository.call_args.args[1], "entrada")

    def test_normaliza_salida(self):
        result, repository = self._call("SALIDA")
        self.assertEqual(result["tipo_movimiento"], "salida")
        self.assertEqual(repository.call_args.args[1], "salida")

    def test_tipo_vacio(self):
        with self.assertRaises(TipoMovimientoInvalidoError):
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN, "  ", 5, clock=lambda: self.NOW
            )

    def test_tipo_desconocido(self):
        with self.assertRaises(TipoMovimientoInvalidoError):
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN, "acceso", 5, clock=lambda: self.NOW
            )

    def test_tipo_no_textual(self):
        with self.assertRaises(TipoMovimientoInvalidoError):
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN, None, 5, clock=lambda: self.NOW
            )

    def test_token_vacio(self):
        with self.assertRaises(QRInvalidoError):
            movimientos_service.registrar_movimiento_con_token(
                "", "entrada", 5, clock=lambda: self.NOW
            )

    def test_token_con_formato_invalido(self):
        with self.assertRaises(QRInvalidoError):
            movimientos_service.registrar_movimiento_con_token(
                "A" * 42, "entrada", 5, clock=lambda: self.NOW
            )

    def test_token_no_textual(self):
        with self.assertRaises(QRInvalidoError):
            movimientos_service.registrar_movimiento_con_token(
                None, "entrada", 5, clock=lambda: self.NOW
            )

    def test_token_con_espacios_externos(self):
        result = dict(self.REPOSITORY_RESULT)
        with patch.object(
            movimientos_service.movimiento_repository,
            "registrar_con_token",
            return_value=result,
        ) as repository:
            movimientos_service.registrar_movimiento_con_token(
                f"  {self.TOKEN}  ", "entrada", 5, clock=lambda: self.NOW
            )
        expected_hash = hashlib.sha256(self.TOKEN.encode("ascii")).hexdigest()
        self.assertEqual(repository.call_args.args[0], expected_hash)

    def test_usuario_id_cero(self):
        with self.assertRaises(UsuarioEscanerInvalidoError):
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN, "entrada", 0, clock=lambda: self.NOW
            )

    def test_usuario_id_negativo(self):
        with self.assertRaises(UsuarioEscanerInvalidoError):
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN, "entrada", -1, clock=lambda: self.NOW
            )

    def test_usuario_id_no_entero(self):
        for value in ("5", 5.0, True, None):
            with self.subTest(value=value):
                with self.assertRaises(UsuarioEscanerInvalidoError):
                    movimientos_service.registrar_movimiento_con_token(
                        self.TOKEN, "entrada", value, clock=lambda: self.NOW
                    )

    def test_punto_permitido(self):
        result, repository = self._call(
            "entrada", punto_plantel="  ACCESO_PRINCIPAL  "
        )
        self.assertEqual(result["punto_plantel"], "acceso_principal")
        self.assertEqual(repository.call_args.args[4], "acceso_principal")

    def test_punto_desconocido(self):
        with self.assertRaises(ValidationError):
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN,
                "entrada",
                5,
                punto_plantel="puerta_norte",
                clock=lambda: self.NOW,
            )

    def test_punto_no_textual(self):
        with self.assertRaises(ValidationError):
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN,
                "entrada",
                5,
                punto_plantel=None,
                clock=lambda: self.NOW,
            )

    def test_reloj_utc(self):
        _result, repository = self._call()
        self.assertEqual(
            repository.call_args.args[2],
            "2026-07-30T18:00:00.000000Z",
        )

    def test_reloj_con_zona_convertible(self):
        local_time = datetime(
            2026,
            7,
            30,
            12,
            0,
            tzinfo=timezone(timedelta(hours=-6)),
        )
        result = dict(self.REPOSITORY_RESULT)
        with patch.object(
            movimientos_service.movimiento_repository,
            "registrar_con_token",
            return_value=result,
        ) as repository:
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN, "entrada", 5, clock=lambda: local_time
            )
        self.assertEqual(
            repository.call_args.args[2],
            "2026-07-30T18:00:00.000000Z",
        )

    def test_datetime_ingenuo_rechazado(self):
        naive = datetime(2026, 7, 30, 18, 0, 0)
        with self.assertRaises(ValidationError):
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN, "entrada", 5, clock=lambda: naive
            )

    def test_delegacion_correcta(self):
        database_path = Path("base-temporal.sqlite")
        _result, repository = self._call(database_path=database_path)
        self.assertEqual(repository.call_count, 1)
        self.assertEqual(repository.call_args.args[3], 5)
        self.assertEqual(repository.call_args.args[5], database_path)

    def test_hash_correcto(self):
        _result, repository = self._call()
        expected = hashlib.sha256(self.TOKEN.encode("ascii")).hexdigest()
        self.assertEqual(repository.call_args.args[0], expected)

    def test_fecha_se_obtiene_una_sola_vez(self):
        clock = Mock(return_value=self.NOW)
        result = dict(self.REPOSITORY_RESULT)
        with patch.object(
            movimientos_service.movimiento_repository,
            "registrar_con_token",
            return_value=result,
        ):
            movimientos_service.registrar_movimiento_con_token(
                self.TOKEN, "entrada", 5, clock=clock
            )
        clock.assert_called_once_with()

    def test_mensaje_entrada(self):
        result, _repository = self._call("entrada")
        self.assertEqual(result["mensaje"], "Entrada registrada correctamente.")

    def test_mensaje_salida(self):
        result, _repository = self._call("salida")
        self.assertEqual(result["mensaje"], "Salida registrada correctamente.")

    def test_respuesta_segura(self):
        repository_result = {
            **self.REPOSITORY_RESULT,
            "token": self.TOKEN,
            "token_hash": "f" * 64,
            "correo": "oculto@edupass.test",
            "password_hash": "oculto",
        }
        with patch.object(
            movimientos_service.movimiento_repository,
            "registrar_con_token",
            return_value=repository_result,
        ):
            result = movimientos_service.registrar_movimiento_con_token(
                self.TOKEN, "entrada", 5, clock=lambda: self.NOW
            )
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
                "mensaje",
            },
        )

    def test_repositorio_incompleto_es_controlado(self):
        with patch.object(
            movimientos_service.movimiento_repository,
            "registrar_con_token",
            return_value={"movimiento_id": 1},
        ):
            with self.assertRaises(RepositoryError):
                movimientos_service.registrar_movimiento_con_token(
                    self.TOKEN, "entrada", 5, clock=lambda: self.NOW
                )

    def _assert_repository_error_propagates(self, error):
        with patch.object(
            movimientos_service.movimiento_repository,
            "registrar_con_token",
            side_effect=error,
        ):
            with self.assertRaises(type(error)) as context:
                movimientos_service.registrar_movimiento_con_token(
                    self.TOKEN, "entrada", 5, clock=lambda: self.NOW
                )
        self.assertIs(context.exception, error)

    def test_propaga_qr_invalido(self):
        self._assert_repository_error_propagates(QRInvalidoError("invalido"))

    def test_propaga_qr_vencido(self):
        self._assert_repository_error_propagates(QRVencidoError("vencido"))

    def test_propaga_qr_utilizado(self):
        self._assert_repository_error_propagates(QRUtilizadoError("utilizado"))

    def test_propaga_alumno_inactivo(self):
        self._assert_repository_error_propagates(
            AlumnoInactivoError("inactivo")
        )

    def test_propaga_secuencia_invalida(self):
        self._assert_repository_error_propagates(
            SecuenciaMovimientoError("secuencia")
        )

    def test_propaga_usuario_escaner_invalido(self):
        self._assert_repository_error_propagates(
            UsuarioEscanerInvalidoError("usuario")
        )

    def test_propaga_repository_error(self):
        self._assert_repository_error_propagates(RepositoryError("repositorio"))

    def test_servicio_no_importa_flask(self):
        source = inspect.getsource(movimientos_service)
        self.assertNotIn("import flask", source.lower())
        self.assertNotIn("from flask", source.lower())

    def test_servicio_no_contiene_sql(self):
        source = inspect.getsource(movimientos_service).upper()
        self.assertNotIn("SELECT ", source)
        self.assertNotIn("INSERT INTO", source)
        self.assertNotIn("UPDATE ", source)

    def test_resultado_no_incluye_token_o_hash(self):
        result, _repository = self._call()
        self.assertNotIn("token", result)
        self.assertNotIn("token_hash", result)
        self.assertNotIn(self.TOKEN, result.values())


if __name__ == "__main__":
    unittest.main()
