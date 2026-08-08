import inspect
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service, cuentas_alumno_service
from edupass.modules.auth import roles_service, usuarios_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import usuario_alumno_repository
from edupass.shared.constants import ESTADO_ACTIVO, ESTADO_INACTIVO, ROL_ALUMNO
from edupass.shared.errors import (
    AlumnoInactivoError,
    AlumnoNoEncontradoError,
    AlumnoYaTieneUsuarioError,
    AuthenticationError,
    AuthorizationError,
    DuplicateUserError,
    RepositoryError,
    UsuarioNoEsAlumnoError,
    ValidationError,
    VinculoUsuarioAlumnoNoEncontradoError,
)


class TestCuentasAlumnoService(unittest.TestCase):
    PASSWORD = "Password123!"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "service.sqlite"
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        roles_service.asegurar_roles_sistema(self.database_path)
        self.admin = usuarios_service.crear_usuario_demo(
            "Admin", "admin@edupass.test", self.PASSWORD,
            "administrador", self.database_path,
        )
        self.scanner = usuarios_service.crear_usuario_demo(
            "Scanner", "scanner@edupass.test", self.PASSWORD,
            "escaner", self.database_path,
        )
        self.sequence = 0
        self.student = self._student()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _student(self, state=ESTADO_ACTIVO):
        self.sequence += 1
        return alumnos_service.registrar_alumno(
            f"Alumno {self.sequence}", f"SRV-{self.sequence}",
            "3", "C", None, state, self.database_path,
        )

    def _create(self, student=None, email="alumno@edupass.test", password=None, actor=None):
        return cuentas_alumno_service.crear_cuenta_alumno(
            (student or self.student)["alumno_id"], email,
            password or self.PASSWORD,
            actor or self.admin["usuario_id"], self.database_path,
        )

    def _stored_hash(self, user_id):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(
                "SELECT password_hash FROM usuarios WHERE usuario_id = ?;",
                (user_id,),
            ).fetchone()[0]
        finally:
            connection.close()

    def test_list_accounts_and_available_students(self):
        other = self._student()
        account = self._create()
        accounts = cuentas_alumno_service.listar_cuentas_alumno(self.database_path)
        available = cuentas_alumno_service.listar_alumnos_sin_cuenta(self.database_path)
        self.assertEqual(accounts[0]["usuario_id"], account["usuario_id"])
        self.assertEqual({item["alumno_id"] for item in available}, {other["alumno_id"]})

    def test_consult_account(self):
        account = self._create()
        self.assertEqual(
            cuentas_alumno_service.consultar_cuenta_alumno(account["usuario_id"], self.database_path),
            account,
        )

    def test_create_normalizes_email_hashes_password_and_fixes_role_state(self):
        account = self._create(email="  ALUMNO@EDUPASS.TEST  ")
        self.assertEqual(account["correo"], "alumno@edupass.test")
        self.assertEqual(account["rol_nombre"], ROL_ALUMNO)
        self.assertEqual(account["usuario_estado"], ESTADO_ACTIVO)
        stored = self._stored_hash(account["usuario_id"])
        self.assertNotEqual(stored, self.PASSWORD)
        self.assertTrue(check_password_hash(stored, self.PASSWORD))

    def test_create_rejects_missing_inactive_linked_or_duplicate(self):
        with self.assertRaises(AlumnoNoEncontradoError):
            cuentas_alumno_service.crear_cuenta_alumno(999999, "x@edupass.test", self.PASSWORD, self.admin["usuario_id"], self.database_path)
        inactive = self._student(ESTADO_INACTIVO)
        with self.assertRaises(AlumnoInactivoError):
            self._create(inactive, "inactive@edupass.test")
        self._create()
        with self.assertRaises(AlumnoYaTieneUsuarioError):
            self._create(self.student, "second@edupass.test")
        other = self._student()
        with self.assertRaises(DuplicateUserError):
            self._create(other, "admin@edupass.test")

    def test_edit_email_preserves_link_role_and_state(self):
        account = self._create()
        updated = cuentas_alumno_service.editar_cuenta_alumno(
            account["usuario_id"], " NEW@EDUPASS.TEST ",
            self.admin["usuario_id"], self.database_path,
        )
        self.assertEqual(updated["correo"], "new@edupass.test")
        self.assertEqual(updated["usuario_alumno_id"], account["usuario_alumno_id"])
        self.assertEqual(updated["rol_nombre"], account["rol_nombre"])
        self.assertEqual(updated["usuario_estado"], account["usuario_estado"])

    def test_password_reset_rejects_old_and_accepts_new(self):
        account = self._create()
        old_hash = self._stored_hash(account["usuario_id"])
        with patch.object(
            cuentas_alumno_service,
            "generar_password_temporal",
            return_value="NuevaClave123!",
        ):
            updated, temporary = (
                cuentas_alumno_service.generar_password_temporal_cuenta_alumno(
                    account["usuario_id"],
                    self.admin["usuario_id"], self.database_path,
                )
            )
        self.assertEqual(temporary, "NuevaClave123!")
        self.assertEqual(updated["requiere_cambio_password"], 1)
        new_hash = self._stored_hash(account["usuario_id"])
        self.assertNotEqual(old_hash, new_hash)
        self.assertFalse(check_password_hash(new_hash, self.PASSWORD))
        self.assertTrue(check_password_hash(new_hash, "NuevaClave123!"))

    def test_activate_and_deactivate(self):
        account = self._create()
        inactive = cuentas_alumno_service.desactivar_cuenta_alumno(
            account["usuario_id"], self.admin["usuario_id"], self.database_path
        )
        self.assertEqual(inactive["usuario_estado"], ESTADO_INACTIVO)
        active = cuentas_alumno_service.activar_cuenta_alumno(
            account["usuario_id"], self.admin["usuario_id"], self.database_path
        )
        self.assertEqual(active["usuario_estado"], ESTADO_ACTIVO)

    def test_activation_rejects_inactive_student(self):
        account = self._create()
        cuentas_alumno_service.desactivar_cuenta_alumno(account["usuario_id"], self.admin["usuario_id"], self.database_path)
        alumnos_service.desactivar_alumno(self.student["alumno_id"], self.database_path)
        with self.assertRaises(AlumnoInactivoError):
            cuentas_alumno_service.activar_cuenta_alumno(account["usuario_id"], self.admin["usuario_id"], self.database_path)

    def test_invalid_actor_is_rejected(self):
        for actor in (999999, self.scanner["usuario_id"]):
            with self.subTest(actor=actor), self.assertRaises(AuthorizationError):
                self._create(actor=actor, email=f"actor{actor}@edupass.test")

    def test_invalid_ids_are_rejected(self):
        for value in (0, -1, True, "1", None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                cuentas_alumno_service.consultar_cuenta_alumno(value, self.database_path)

    def test_email_and_password_validation(self):
        for email in (None, "", "x" * 255):
            with self.subTest(email=email), self.assertRaises(ValidationError):
                self._create(email=email)
        for password in (None, "", "short", "x" * 257):
            with self.subTest(password=password), self.assertRaises(ValidationError):
                cuentas_alumno_service.crear_cuenta_alumno(
                    self.student["alumno_id"],
                    f"p{len(str(password))}@edupass.test",
                    password,
                    self.admin["usuario_id"],
                    self.database_path,
                )

    def test_missing_or_unlinked_account_is_rejected(self):
        with self.assertRaises(VinculoUsuarioAlumnoNoEncontradoError):
            cuentas_alumno_service.consultar_cuenta_alumno(999999, self.database_path)
        with self.assertRaises(VinculoUsuarioAlumnoNoEncontradoError):
            cuentas_alumno_service.consultar_cuenta_alumno(self.admin["usuario_id"], self.database_path)

    def test_linked_wrong_role_is_rejected(self):
        extra = self._student()
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("INSERT INTO usuario_alumno (usuario_id, alumno_id) VALUES (?, ?);", (self.scanner["usuario_id"], extra["alumno_id"]))
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(UsuarioNoEsAlumnoError):
            cuentas_alumno_service.consultar_cuenta_alumno(self.scanner["usuario_id"], self.database_path)

    def test_results_exclude_sensitive_fields(self):
        account = self._create()
        results = [account, cuentas_alumno_service.consultar_cuenta_alumno(account["usuario_id"], self.database_path)]
        for result in results:
            for key in ("password_hash", "fotografia", "qr", "token"):
                self.assertNotIn(key, result)

    def test_repository_error_is_propagated(self):
        original = RepositoryError("controlado")
        with patch.object(usuario_alumno_repository, "listar_cuentas", side_effect=original):
            with self.assertRaises(RepositoryError) as context:
                cuentas_alumno_service.listar_cuentas_alumno(self.database_path)
        self.assertIs(context.exception, original)

    def test_service_has_no_flask_sql_or_direct_connection(self):
        source = inspect.getsource(cuentas_alumno_service)
        self.assertNotIn("flask", source.lower())
        for fragment in ("SELECT ", "INSERT ", "UPDATE ", "sqlite3", "get_connection"):
            self.assertNotIn(fragment, source)

    def test_active_linked_student_can_authenticate(self):
        account = self._create()
        authenticated = usuarios_service.autenticar_usuario(
            account["correo"], self.PASSWORD, self.database_path
        )
        self.assertEqual(authenticated["usuario_id"], account["usuario_id"])
        self.assertEqual(authenticated["rol_nombre"], ROL_ALUMNO)
        self.assertEqual(authenticated["estado"], ESTADO_ACTIVO)
        self.assertNotIn("password_hash", authenticated)


if __name__ == "__main__":
    unittest.main()
