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

from edupass.modules.alumnos import alumnos_service, cuentas_alumno_service
from edupass.modules.auth import roles_service, usuarios_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import usuario_repository
from edupass.shared.errors import (
    AutoBloqueoAdministradorError,
    AuthenticationError,
    AuthorizationError,
    DuplicateUserError,
    InvalidRoleError,
    RepositoryError,
    UltimoAdministradorActivoError,
    UsuarioNoEncontradoError,
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

    def _crear_cuenta_alumno(self):
        admin = self._crear_demo()
        alumno = alumnos_service.registrar_alumno(
            "Alumno Auth", "AUTH-001", "2", "B", None, "activo", self.database_path
        )
        cuenta = cuentas_alumno_service.crear_cuenta_alumno(
            alumno["alumno_id"], "student.auth@edupass.test", self.PASSWORD,
            admin["usuario_id"], self.database_path,
        )
        return admin, alumno, cuenta

    def test_alumno_activo_vinculado_autentica_y_sesion_es_segura(self):
        _, alumno, cuenta = self._crear_cuenta_alumno()
        authenticated = usuarios_service.autenticar_usuario(
            cuenta["correo"], self.PASSWORD, self.database_path
        )
        session_user = usuarios_service.obtener_usuario_sesion(
            cuenta["usuario_id"], self.database_path
        )
        self.assertEqual(authenticated["rol_nombre"], "alumno")
        self.assertEqual(session_user, authenticated)
        self.assertNotIn("password_hash", authenticated)
        self.assertNotIn("alumno_id", authenticated)
        self.assertEqual(alumno["estado"], "activo")

    def test_alumno_inactivo_o_cuenta_inactiva_no_autentica_con_mensaje_generico(self):
        _, alumno, cuenta = self._crear_cuenta_alumno()
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE usuarios SET estado = 'inactivo' WHERE usuario_id = ?", (cuenta["usuario_id"],))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(AuthenticationError) as inactive_account:
            usuarios_service.autenticar_usuario(cuenta["correo"], self.PASSWORD, self.database_path)
        self.assertEqual(str(inactive_account.exception), self.AUTH_MESSAGE)
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE usuarios SET estado = 'activo' WHERE usuario_id = ?", (cuenta["usuario_id"],))
            connection.execute("UPDATE alumnos SET estado = 'inactivo' WHERE alumno_id = ?", (alumno["alumno_id"],))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(AuthenticationError) as inactive_student:
            usuarios_service.autenticar_usuario(cuenta["correo"], self.PASSWORD, self.database_path)
        self.assertEqual(str(inactive_student.exception), self.AUTH_MESSAGE)

    def test_alumno_sin_vinculo_no_autentica_y_sesion_es_none(self):
        role = next(role for role in roles_service.asegurar_roles_autenticacion(self.database_path) if role["nombre"] == "alumno")
        user_id = usuario_repository.crear(
            "Alumno sin vinculo", "unlinked.auth@edupass.test",
            generate_password_hash(self.PASSWORD), "activo", role["rol_id"], self.database_path,
        )
        with self.assertRaises(AuthenticationError) as context:
            usuarios_service.autenticar_usuario("unlinked.auth@edupass.test", self.PASSWORD, self.database_path)
        self.assertEqual(str(context.exception), self.AUTH_MESSAGE)
        self.assertIsNone(usuarios_service.obtener_usuario_sesion(user_id, self.database_path))

    def test_sesion_alumno_se_invalida_por_cuenta_alumno_o_vinculo(self):
        _, alumno, cuenta = self._crear_cuenta_alumno()
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE usuarios SET estado = 'inactivo' WHERE usuario_id = ?", (cuenta["usuario_id"],))
            connection.commit()
        finally:
            connection.close()
        self.assertIsNone(usuarios_service.obtener_usuario_sesion(cuenta["usuario_id"], self.database_path))
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE usuarios SET estado = 'activo' WHERE usuario_id = ?", (cuenta["usuario_id"],))
            connection.execute("UPDATE alumnos SET estado = 'inactivo' WHERE alumno_id = ?", (alumno["alumno_id"],))
            connection.commit()
        finally:
            connection.close()
        self.assertIsNone(usuarios_service.obtener_usuario_sesion(cuenta["usuario_id"], self.database_path))
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE alumnos SET estado = 'activo' WHERE alumno_id = ?", (alumno["alumno_id"],))
            connection.execute("DELETE FROM usuario_alumno WHERE usuario_id = ?", (cuenta["usuario_id"],))
            connection.commit()
        finally:
            connection.close()
        self.assertIsNone(usuarios_service.obtener_usuario_sesion(cuenta["usuario_id"], self.database_path))
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
                "requiere_cambio_password",
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

    def test_validar_rol_rechaza_rol_requerido_distinto(self):
        usuario = self._crear_demo()

        with self.assertRaises(AuthorizationError):
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



class TestAuthServiceAdministradores(unittest.TestCase):
    PASSWORD = "ClaveAdministrativa123"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "admins.sqlite"
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)

    def tearDown(self):
        self.temp.cleanup()

    def _admin(self, correo="admin@edupass.test", **changes):
        data = {"nombre": "Administrador", "correo": correo, "password": self.PASSWORD}
        data.update(changes)
        return usuarios_service.crear_administrador(database_path=self.database_path, **data)

    def _scanner(self):
        return usuarios_service.crear_usuario_demo(
            "Escaner", "scanner@edupass.test", self.PASSWORD,
            "escaner", self.database_path,
        )

    def test_crear_listar_consultar_y_respuestas_seguras(self):
        admin = self._admin(correo="  ADMIN@EDUPASS.TEST  ")
        scanner = self._scanner()
        self.assertEqual((admin["rol_nombre"], admin["estado"], admin["correo"]),
                         ("administrador", "activo", "admin@edupass.test"))
        self.assertNotIn("password_hash", admin)
        rows = usuarios_service.listar_administradores(self.database_path)
        self.assertEqual([row["usuario_id"] for row in rows], [admin["usuario_id"]])
        self.assertTrue(all("password_hash" not in row for row in rows))
        self.assertEqual(usuarios_service.consultar_administrador(
            admin["usuario_id"], self.database_path)["usuario_id"], admin["usuario_id"])
        with self.assertRaises(UsuarioNoEncontradoError):
            usuarios_service.consultar_administrador(scanner["usuario_id"], self.database_path)
        with self.assertRaises(DuplicateUserError):
            self._admin(nombre="Duplicado")

    def test_editar_conserva_rol_estado_password_y_valida_correo(self):
        admin = self._admin()
        second = self._admin("second@edupass.test")
        before = usuario_repository.obtener_por_id(admin["usuario_id"], self.database_path)
        edited = usuarios_service.editar_administrador(
            admin["usuario_id"], "Editado", "ADMIN@EDUPASS.TEST", self.database_path)
        after = usuario_repository.obtener_por_id(admin["usuario_id"], self.database_path)
        self.assertEqual(edited["nombre"], "Editado")
        self.assertEqual((after["rol_id"], after["estado"], after["password_hash"]),
                         (before["rol_id"], before["estado"], before["password_hash"]))
        with self.assertRaises(DuplicateUserError):
            usuarios_service.editar_administrador(
                admin["usuario_id"], "Duplicado", second["correo"], self.database_path)

    def test_restablecer_password_y_longitudes(self):
        admin = self._admin()
        new_password = "NuevaClaveAdministrativa456"
        result = usuarios_service.restablecer_password_administrador(
            admin["usuario_id"], new_password, self.database_path)
        self.assertNotIn("password_hash", result)
        with self.assertRaises(AuthenticationError):
            usuarios_service.autenticar_usuario(admin["correo"], self.PASSWORD, self.database_path)
        self.assertEqual(usuarios_service.autenticar_usuario(
            admin["correo"], new_password, self.database_path)["usuario_id"], admin["usuario_id"])
        for invalid in ("corta", "x" * 257):
            with self.subTest(length=len(invalid)):
                with self.assertRaises(ValidationError):
                    usuarios_service.restablecer_password_administrador(
                        admin["usuario_id"], invalid, self.database_path)

    def test_estados_auto_bloqueo_y_ultimo_activo(self):
        actor = self._admin()
        target = self._admin("target@edupass.test")
        self.assertEqual(usuarios_service.desactivar_administrador(
            target["usuario_id"], actor["usuario_id"], self.database_path)["estado"], "inactivo")
        self.assertEqual(usuarios_service.activar_administrador(
            target["usuario_id"], actor["usuario_id"], self.database_path)["estado"], "activo")
        with self.assertRaises(AutoBloqueoAdministradorError):
            usuarios_service.desactivar_administrador(
                actor["usuario_id"], actor["usuario_id"], self.database_path)
        with patch.object(usuarios_service.usuario_repository,
                          "cambiar_estado_administrador_protegido",
                          side_effect=UltimoAdministradorActivoError("controlado")):
            with self.assertRaises(UltimoAdministradorActivoError):
                usuarios_service.desactivar_administrador(
                    target["usuario_id"], actor["usuario_id"], self.database_path)

    def test_ids_errores_y_compatibilidad_historica(self):
        for usuario_id in (0, -1, "1", True, None):
            with self.subTest(usuario_id=usuario_id):
                with self.assertRaises(ValidationError):
                    usuarios_service.consultar_administrador(usuario_id, self.database_path)
        with self.assertRaises(UsuarioNoEncontradoError):
            usuarios_service.consultar_administrador(9999, self.database_path)
        error = RepositoryError("controlado")
        with patch.object(usuarios_service.usuario_repository, "listar_por_rol", side_effect=error):
            with self.assertRaises(RepositoryError) as context:
                usuarios_service.listar_administradores(self.database_path)
        self.assertIs(context.exception, error)
        historic = usuarios_service.crear_usuario_demo(
            "Historico", "historico@edupass.test", self.PASSWORD,
            "administrador", self.database_path)
        self.assertEqual(usuarios_service.autenticar_usuario(
            historic["correo"], self.PASSWORD, self.database_path), historic)

class TestAuthServiceEscaneres(unittest.TestCase):
    PASSWORD = "ClaveEscanerServicio123"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "escaneres_service.sqlite"
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)

    def tearDown(self):
        self.temp.cleanup()

    def _scanner(self, correo="scanner@edupass.test", **changes):
        data = {"nombre": "Escaner", "correo": correo, "password": self.PASSWORD}
        data.update(changes)
        return usuarios_service.crear_escaner(
            database_path=self.database_path, **data
        )

    def _admin(self, correo="admin@edupass.test"):
        return usuarios_service.crear_administrador(
            "Administrador", correo, self.PASSWORD, self.database_path
        )

    def test_crear_fija_rol_activo_normaliza_y_oculta_hash(self):
        result = self._scanner(correo="  SCANNER@EDUPASS.TEST  ")
        self.assertEqual(
            (result["rol_nombre"], result["estado"], result["correo"]),
            ("escaner", "activo", "scanner@edupass.test"),
        )
        self.assertNotIn("password_hash", result)
        with self.assertRaises(DuplicateUserError):
            self._scanner(nombre="Duplicado")

    def test_listar_y_consultar_solo_escaneres(self):
        scanner = self._scanner()
        admin = self._admin()
        rows = usuarios_service.listar_escaneres(self.database_path)
        self.assertEqual([row["usuario_id"] for row in rows], [scanner["usuario_id"]])
        self.assertTrue(all("password_hash" not in row for row in rows))
        self.assertEqual(usuarios_service.consultar_escaner(
            scanner["usuario_id"], self.database_path)["usuario_id"], scanner["usuario_id"])
        with self.assertRaises(UsuarioNoEncontradoError):
            usuarios_service.consultar_escaner(admin["usuario_id"], self.database_path)

    def test_editar_conserva_rol_estado_password_y_correo_propio(self):
        scanner = self._scanner()
        before = usuario_repository.obtener_por_id(scanner["usuario_id"], self.database_path)
        edited = usuarios_service.editar_escaner(
            scanner["usuario_id"], "Escaner Editado", "SCANNER@EDUPASS.TEST",
            self.database_path,
        )
        after = usuario_repository.obtener_por_id(scanner["usuario_id"], self.database_path)
        self.assertEqual(edited["nombre"], "Escaner Editado")
        self.assertEqual((after["rol_id"], after["estado"], after["password_hash"]),
                         (before["rol_id"], before["estado"], before["password_hash"]))

    def test_editar_rechaza_correo_de_otro_usuario_incluso_admin(self):
        scanner = self._scanner()
        other = self._scanner("other@edupass.test")
        admin = self._admin()
        for email in (other["correo"], admin["correo"]):
            with self.subTest(email=email):
                with self.assertRaises(DuplicateUserError):
                    usuarios_service.editar_escaner(
                        scanner["usuario_id"], "Duplicado", email, self.database_path
                    )

    def test_restablecer_password_rechaza_anterior_acepta_nueva_y_no_vacia(self):
        scanner = self._scanner()
        new_password = "NuevaClaveEscaner456"
        result = usuarios_service.restablecer_password_escaner(
            scanner["usuario_id"], new_password, self.database_path
        )
        self.assertNotIn("password_hash", result)
        with self.assertRaises(AuthenticationError):
            usuarios_service.autenticar_usuario(
                scanner["correo"], self.PASSWORD, self.database_path
            )
        self.assertEqual(usuarios_service.autenticar_usuario(
            scanner["correo"], new_password, self.database_path)["usuario_id"],
            scanner["usuario_id"],
        )
        for invalid in ("", "corta", "x" * 257):
            with self.subTest(length=len(invalid)):
                with self.assertRaises(ValidationError):
                    usuarios_service.restablecer_password_escaner(
                        scanner["usuario_id"], invalid, self.database_path
                    )

    def test_activar_desactivar_y_actor_no_administrador_rechazado(self):
        admin = self._admin()
        scanner = self._scanner()
        other_scanner = self._scanner("other@edupass.test")
        self.assertEqual(usuarios_service.desactivar_escaner(
            scanner["usuario_id"], admin["usuario_id"], self.database_path)["estado"],
            "inactivo",
        )
        with self.assertRaises(AuthenticationError):
            usuarios_service.autenticar_usuario(
                scanner["correo"], self.PASSWORD, self.database_path
            )
        self.assertEqual(usuarios_service.activar_escaner(
            scanner["usuario_id"], admin["usuario_id"], self.database_path)["estado"],
            "activo",
        )
        with self.assertRaises(AuthorizationError):
            usuarios_service.desactivar_escaner(
                scanner["usuario_id"], other_scanner["usuario_id"], self.database_path
            )

    def test_ids_inexistente_y_repository_error(self):
        for usuario_id in (0, -1, "1", True, None):
            with self.subTest(usuario_id=usuario_id):
                with self.assertRaises(ValidationError):
                    usuarios_service.consultar_escaner(usuario_id, self.database_path)
        with self.assertRaises(UsuarioNoEncontradoError):
            usuarios_service.consultar_escaner(99999, self.database_path)
        error = RepositoryError("controlado")
        with patch.object(usuario_repository, "listar_por_rol", side_effect=error):
            with self.assertRaises(RepositoryError) as context:
                usuarios_service.listar_escaneres(self.database_path)
        self.assertIs(context.exception, error)

    def test_crud_administradores_y_autenticacion_siguen_compatibles(self):
        admin = self._admin()
        second = usuarios_service.crear_administrador(
            "Segundo", "second@edupass.test", self.PASSWORD, self.database_path
        )
        edited = usuarios_service.editar_administrador(
            second["usuario_id"], "Segundo Editado", second["correo"], self.database_path
        )
        self.assertEqual(edited["rol_nombre"], "administrador")
        self.assertEqual(usuarios_service.autenticar_usuario(
            admin["correo"], self.PASSWORD, self.database_path), admin)

if __name__ == "__main__":
    unittest.main()
