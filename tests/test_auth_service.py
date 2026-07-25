from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.auth import roles_service, usuarios_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import usuario_repository
from edupass.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    DuplicateUserError,
    InvalidRoleError,
    RepositoryError,
    ValidationError,
)


class TestAuthService(unittest.TestCase):
    PASSWORD = "ClaveSegura123"
    AUTH_MESSAGE = (
        "No fue posible iniciar sesi?n con las credenciales proporcionadas."
    )

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "auth_service_test.sqlite"
        )
        database_manager.initialize_database(
            self.database_path,
            SCHEMA_PATH,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _crear_demo(self, **changes):
        data = {
            "nombre": "Administrador Demo",
            "correo": "admin@edupass.test",
            "password": self.PASSWORD,
            "rol": "administrador",
        }
        data.update(changes)
        return usuarios_service.crear_usuario_demo(
            database_path=self.database_path,
            **data,
        )

    def _crear_inactivo(self):
        roles = roles_service.asegurar_roles_autenticacion(
            self.database_path
        )
        administrador = next(
            rol for rol in roles if rol["nombre"] == "administrador"
        )
        usuario_id = usuario_repository.crear(
            "Usuario Inactivo",
            "inactivo@edupass.test",
            generate_password_hash(self.PASSWORD),
            "inactivo",
            administrador["rol_id"],
            self.database_path,
        )
        return usuario_repository.obtener_por_id(
            usuario_id,
            self.database_path,
        )

    def test_crear_administrador_demo(self):
        usuario = self._crear_demo()

        self.assertEqual(usuario["rol_nombre"], "administrador")
        self.assertEqual(usuario["estado"], "activo")

    def test_crear_escaner_demo(self):
        usuario = self._crear_demo(
            nombre="Escaner Demo",
            correo="escaner@edupass.test",
            rol="escaner",
        )

        self.assertEqual(usuario["rol_nombre"], "escaner")

    def test_crear_usuario_normaliza_correo_y_nombre(self):
        usuario = self._crear_demo(
            nombre="  Administrador Demo  ",
            correo="  ADMIN@EDUPASS.TEST  ",
        )

        self.assertEqual(usuario["nombre"], "Administrador Demo")
        self.assertEqual(usuario["correo"], "admin@edupass.test")

    def test_crear_usuario_almacena_hash(self):
        usuario = self._crear_demo()
        interno = usuario_repository.obtener_por_id(
            usuario["usuario_id"],
            self.database_path,
        )

        self.assertNotEqual(interno["password_hash"], self.PASSWORD)
        self.assertTrue(
            check_password_hash(interno["password_hash"], self.PASSWORD)
        )

    def test_crear_usuario_rechaza_contrasena_corta(self):
        with self.assertRaises(ValidationError):
            self._crear_demo(password="corta")

    def test_crear_usuario_rechaza_correo_vacio(self):
        for correo in ("", "   ", None):
            with self.subTest(correo=correo):
                with self.assertRaises(ValidationError):
                    self._crear_demo(correo=correo)

    def test_crear_usuario_rechaza_contrasena_vacia(self):
        for password in ("", None):
            with self.subTest(password=password):
                with self.assertRaises(ValidationError):
                    self._crear_demo(password=password)

    def test_crear_usuario_rechaza_rol_invalido(self):
        with self.assertRaises(InvalidRoleError):
            self._crear_demo(rol="alumno")

    def test_crear_usuario_rechaza_correo_duplicado(self):
        self._crear_demo()

        with self.assertRaises(DuplicateUserError):
            self._crear_demo(nombre="Otro Administrador")

    def test_autenticacion_correcta_administrador(self):
        esperado = self._crear_demo()

        usuario = usuarios_service.autenticar_usuario(
            "admin@edupass.test",
            self.PASSWORD,
            self.database_path,
        )

        self.assertEqual(usuario, esperado)

    def test_autenticacion_correcta_escaner(self):
        esperado = self._crear_demo(
            nombre="Escaner Demo",
            correo="escaner@edupass.test",
            rol="escaner",
        )

        usuario = usuarios_service.autenticar_usuario(
            "escaner@edupass.test",
            self.PASSWORD,
            self.database_path,
        )

        self.assertEqual(usuario, esperado)

    def test_autenticacion_normaliza_correo(self):
        esperado = self._crear_demo()

        usuario = usuarios_service.autenticar_usuario(
            "  ADMIN@EDUPASS.TEST  ",
            self.PASSWORD,
            self.database_path,
        )

        self.assertEqual(usuario, esperado)

    def test_autenticacion_rechaza_contrasena_incorrecta(self):
        self._crear_demo()

        with self.assertRaises(AuthenticationError) as context:
            usuarios_service.autenticar_usuario(
                "admin@edupass.test",
                "ClaveIncorrecta",
                self.database_path,
            )

        self.assertEqual(str(context.exception), self.AUTH_MESSAGE)

    def test_autenticacion_rechaza_correo_inexistente(self):
        with self.assertRaises(AuthenticationError) as context:
            usuarios_service.autenticar_usuario(
                "noexiste@edupass.test",
                self.PASSWORD,
                self.database_path,
            )

        self.assertEqual(str(context.exception), self.AUTH_MESSAGE)

    def test_autenticacion_rechaza_usuario_inactivo(self):
        self._crear_inactivo()

        with self.assertRaises(AuthenticationError) as context:
            usuarios_service.autenticar_usuario(
                "inactivo@edupass.test",
                self.PASSWORD,
                self.database_path,
            )

        self.assertEqual(str(context.exception), self.AUTH_MESSAGE)

    def test_errores_de_credenciales_comparten_mensaje_generico(self):
        self._crear_demo()
        self._crear_inactivo()
        cases = (
            ("admin@edupass.test", "incorrecta"),
            ("noexiste@edupass.test", self.PASSWORD),
            ("inactivo@edupass.test", self.PASSWORD),
        )
        messages = []

        for correo, password in cases:
            with self.subTest(correo=correo):
                with self.assertRaises(AuthenticationError) as context:
                    usuarios_service.autenticar_usuario(
                        correo,
                        password,
                        self.database_path,
                    )
                messages.append(str(context.exception))

        self.assertEqual(messages, [self.AUTH_MESSAGE] * 3)

    def test_autenticacion_rechaza_campos_vacios_con_mensaje_generico(self):
        for correo, password in (("", self.PASSWORD), ("a@b.test", "")):
            with self.subTest(correo=correo):
                with self.assertRaises(AuthenticationError) as context:
                    usuarios_service.autenticar_usuario(
                        correo,
                        password,
                        self.database_path,
                    )
                self.assertEqual(str(context.exception), self.AUTH_MESSAGE)

    def test_respuesta_segura_no_contiene_password_hash(self):
        self._crear_demo()

        usuario = usuarios_service.autenticar_usuario(
            "admin@edupass.test",
            self.PASSWORD,
            self.database_path,
        )

        self.assertNotIn("password_hash", usuario)
        self.assertEqual(
            set(usuario),
            {
                "usuario_id",
                "nombre",
                "correo",
                "estado",
                "rol_id",
                "rol_nombre",
            },
        )

    def test_obtener_usuario_sesion_activo(self):
        esperado = self._crear_demo()

        usuario = usuarios_service.obtener_usuario_sesion(
            esperado["usuario_id"],
            self.database_path,
        )

        self.assertEqual(usuario, esperado)
        self.assertNotIn("password_hash", usuario)

    def test_obtener_usuario_sesion_inexistente(self):
        self.assertIsNone(
            usuarios_service.obtener_usuario_sesion(
                9999,
                self.database_path,
            )
        )

    def test_obtener_usuario_sesion_inactivo(self):
        interno = self._crear_inactivo()

        self.assertIsNone(
            usuarios_service.obtener_usuario_sesion(
                interno["usuario_id"],
                self.database_path,
            )
        )

    def test_obtener_usuario_sesion_rechaza_id_invalido(self):
        for usuario_id in (0, -1, "1", True, None):
            with self.subTest(usuario_id=usuario_id):
                with self.assertRaises(ValidationError):
                    usuarios_service.obtener_usuario_sesion(
                        usuario_id,
                        self.database_path,
                    )

    def test_validar_rol_correcto(self):
        usuario = self._crear_demo()

        self.assertTrue(
            usuarios_service.validar_rol(usuario, "administrador")
        )

    def test_validar_rol_rechaza_rol_incorrecto(self):
        usuario = self._crear_demo()

        with self.assertRaises(AuthorizationError):
            usuarios_service.validar_rol(usuario, "escaner")

    def test_validar_rol_rechaza_rol_requerido_invalido(self):
        usuario = self._crear_demo()

        with self.assertRaises(InvalidRoleError):
            usuarios_service.validar_rol(usuario, "alumno")

    def test_repository_error_se_propaga_controlado(self):
        original = RepositoryError("fallo controlado")
        with patch.object(
            usuarios_service.usuario_repository,
            "obtener_por_correo",
            side_effect=original,
        ):
            with self.assertRaises(RepositoryError) as context:
                usuarios_service.autenticar_usuario(
                    "admin@edupass.test",
                    self.PASSWORD,
                    self.database_path,
                )

        self.assertIs(context.exception, original)


if __name__ == "__main__":
    unittest.main()
