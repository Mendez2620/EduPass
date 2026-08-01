from datetime import datetime, timedelta, timezone
import hashlib
import inspect
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumno_portal_service, alumnos_service, cuentas_alumno_service
from edupass.modules.auth import roles_service, usuarios_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import qr_token_repository, usuario_repository
from edupass.shared.errors import (
    AlumnoInactivoError, AuthenticationError, MovimientoNoEncontradoError,
    RepositoryError, UsuarioNoEsAlumnoError, UsuarioNoEncontradoError,
    ValidationError, VinculoUsuarioAlumnoNoEncontradoError,
)


class TestAlumnoPortalService(unittest.TestCase):
    PASSWORD = "Password123!"
    NOW = datetime(2026, 7, 31, 18, 0, tzinfo=timezone.utc)
    TOKEN_A = "A" * 43
    TOKEN_B = "B" * 43

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "portal.sqlite"
        database_manager.initialize_database(self.database_path)
        self.admin = usuarios_service.crear_usuario_demo(
            "Admin", "admin@edupass.test", self.PASSWORD, "administrador", self.database_path
        )
        self.scanner = usuarios_service.crear_usuario_demo(
            "Scanner", "scanner@edupass.test", self.PASSWORD, "escaner", self.database_path
        )
        self.student = alumnos_service.registrar_alumno(
            "Alumno Propio", "PORTAL-0001", "3", "A", "C:/privado/foto.png",
            "activo", self.database_path,
        )
        self.other = alumnos_service.registrar_alumno(
            "Alumno Ajeno", "PORTAL-0002", "4", "B", None, "activo", self.database_path
        )
        self.account = cuentas_alumno_service.crear_cuenta_alumno(
            self.student["alumno_id"], "alumno@edupass.test", self.PASSWORD,
            self.admin["usuario_id"], self.database_path,
        )

    def tearDown(self):
        self.temp.cleanup()

    def _raw_student_user(self, email="sin-vinculo@edupass.test"):
        role = next(item for item in roles_service.asegurar_roles_autenticacion(self.database_path) if item["nombre"] == "alumno")
        return usuario_repository.crear(
            "Sin vinculo", email, generate_password_hash(self.PASSWORD), "activo",
            role["rol_id"], self.database_path,
        )

    def _movements(self, count, student_id=None):
        connection = database_manager.get_connection(self.database_path)
        try:
            result = []
            for index in range(count):
                cursor = connection.execute(
                    "INSERT INTO movimientos (alumno_id, tipo_movimiento, fecha_hora, area_id, punto_plantel, usuario_id, dispositivo_id) VALUES (?, ?, ?, NULL, ?, ?, NULL);",
                    (student_id or self.student["alumno_id"], "entrada" if index % 2 == 0 else "salida", f"2026-07-31T18:{index:02d}:00.000000Z", "acceso_principal", self.scanner["usuario_id"]),
                )
                result.append(int(cursor.lastrowid))
            connection.commit()
            return result
        finally:
            connection.close()

    def test_obtener_perfil_propio_es_seguro_y_resuelve_por_usuario(self):
        profile = alumno_portal_service.obtener_perfil_propio(self.account["usuario_id"], self.database_path)
        self.assertEqual(profile["alumno_id"], self.student["alumno_id"])
        self.assertEqual(profile["matricula"], "PORTAL-0001")
        self.assertEqual(set(profile), {"usuario_id", "alumno_id", "nombre", "matricula", "grado", "grupo", "alumno_estado", "correo", "usuario_estado"})
        for forbidden in ("password_hash", "fotografia", "token", "token_hash", "rol_id"):
            self.assertNotIn(forbidden, profile)

    def test_ids_invalidos_son_rechazados(self):
        for value in (0, -1, True, "1", None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                alumno_portal_service.obtener_perfil_propio(value, self.database_path)

    def test_usuario_inexistente_y_roles_no_alumno_son_rechazados(self):
        with self.assertRaises(UsuarioNoEncontradoError):
            alumno_portal_service.obtener_perfil_propio(999999, self.database_path)
        for user in (self.admin, self.scanner):
            with self.subTest(role=user["rol_nombre"]), self.assertRaises(UsuarioNoEsAlumnoError):
                alumno_portal_service.obtener_perfil_propio(user["usuario_id"], self.database_path)

    def test_alumno_sin_vinculo_es_rechazado(self):
        with self.assertRaises(VinculoUsuarioAlumnoNoEncontradoError):
            alumno_portal_service.obtener_perfil_propio(self._raw_student_user(), self.database_path)

    def test_cuenta_inactiva_es_rechazada(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE usuarios SET estado = 'inactivo' WHERE usuario_id = ?", (self.account["usuario_id"],))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(AuthenticationError):
            alumno_portal_service.obtener_perfil_propio(self.account["usuario_id"], self.database_path)

    def test_alumno_inactivo_es_rechazado(self):
        alumnos_service.desactivar_alumno(self.student["alumno_id"], self.database_path)
        with self.assertRaises(AlumnoInactivoError):
            alumno_portal_service.obtener_perfil_propio(self.account["usuario_id"], self.database_path)

    def test_vinculo_corrupto_es_rechazado(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("UPDATE usuario_alumno SET alumno_id = 999999 WHERE usuario_id = ?", (self.account["usuario_id"],))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises((VinculoUsuarioAlumnoNoEncontradoError, AlumnoInactivoError)):
            alumno_portal_service.obtener_perfil_propio(self.account["usuario_id"], self.database_path)

    def test_generar_credencial_propia_conserva_token_y_vigencia(self):
        result = alumno_portal_service.generar_credencial_propia(
            self.account["usuario_id"], self.database_path, lambda: self.NOW, lambda: self.TOKEN_A
        )
        self.assertEqual(result["alumno_id"], self.student["alumno_id"])
        self.assertEqual(result["token"], self.TOKEN_A)
        self.assertEqual(len(result["token"]), 43)
        self.assertEqual(result["vigencia_segundos"], 30)
        self.assertEqual(result["expira_en"], "2026-07-31T18:00:30.000000Z")
        self.assertNotIn("token_hash", result)
        self.assertNotIn("fotografia", result)

    def test_renovar_invalida_token_anterior(self):
        alumno_portal_service.generar_credencial_propia(self.account["usuario_id"], self.database_path, lambda: self.NOW, lambda: self.TOKEN_A)
        renewed = alumno_portal_service.renovar_credencial_propia(self.account["usuario_id"], self.database_path, lambda: self.NOW + timedelta(seconds=1), lambda: self.TOKEN_B)
        old = qr_token_repository.obtener_por_hash(hashlib.sha256(self.TOKEN_A.encode()).hexdigest(), self.database_path)
        self.assertEqual(renewed["token"], self.TOKEN_B)
        self.assertEqual(old["estado"], "invalidado")

    def test_historial_propio_vacio(self):
        result = alumno_portal_service.consultar_historial_propio(self.account["usuario_id"], database_path=self.database_path)
        self.assertEqual(result["movimientos"], [])
        self.assertEqual(result["alumno"]["alumno_id"], self.student["alumno_id"])

    def test_historial_propio_orden_y_paginacion(self):
        ids = self._movements(51)
        first = alumno_portal_service.consultar_historial_propio(self.account["usuario_id"], 1, self.database_path)
        second = alumno_portal_service.consultar_historial_propio(self.account["usuario_id"], 2, self.database_path)
        self.assertEqual(len(first["movimientos"]), 50)
        self.assertEqual(len(second["movimientos"]), 1)
        self.assertEqual(first["movimientos"][0]["movimiento_id"], ids[-1])

    def test_movimiento_propio_y_ajeno_o_inexistente(self):
        own = self._movements(1)[0]
        foreign = self._movements(1, self.other["alumno_id"])[0]
        result = alumno_portal_service.consultar_movimiento_propio(self.account["usuario_id"], own, self.database_path)
        self.assertEqual(result["movimiento_id"], own)
        for movement_id in (foreign, 999999):
            with self.subTest(movement_id=movement_id), self.assertRaises(MovimientoNoEncontradoError):
                alumno_portal_service.consultar_movimiento_propio(self.account["usuario_id"], movement_id, self.database_path)

    def test_repository_error_se_propaga(self):
        with patch.object(alumno_portal_service.usuario_repository, "obtener_por_id", side_effect=RepositoryError("controlado")):
            with self.assertRaises(RepositoryError):
                alumno_portal_service.obtener_perfil_propio(self.account["usuario_id"], self.database_path)

    def test_servicio_no_importa_flask_ni_contiene_sql(self):
        source = inspect.getsource(alumno_portal_service)
        self.assertNotIn("import flask", source.lower())
        self.assertNotIn("SELECT ", source)
        self.assertNotIn("INSERT ", source)
        self.assertNotIn("UPDATE ", source)
        self.assertNotIn("get_connection", source)

    def test_api_publica_no_acepta_alumno_id(self):
        public = (
            alumno_portal_service.obtener_perfil_propio,
            alumno_portal_service.generar_credencial_propia,
            alumno_portal_service.renovar_credencial_propia,
            alumno_portal_service.consultar_historial_propio,
            alumno_portal_service.consultar_movimiento_propio,
        )
        for function in public:
            with self.subTest(function=function.__name__):
                self.assertNotIn("alumno_id", inspect.signature(function).parameters)
        self.assertFalse(hasattr(alumno_portal_service, "consultar_por_alumno_id"))


if __name__ == "__main__":
    unittest.main()