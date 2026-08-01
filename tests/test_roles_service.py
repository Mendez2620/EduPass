from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.auth import roles_service, usuarios_service
from edupass.persistence import database_manager
from edupass.shared.constants import (
    ROL_ADMINISTRADOR,
    ROL_ALUMNO,
    ROL_ESCANER,
    ROLES_AUTENTICACION,
    ROLES_SISTEMA,
)
from edupass.shared.errors import InvalidRoleError


class TestRolesService(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "roles_service_test.sqlite"
        )
        database_manager.initialize_database(
            self.database_path,
            SCHEMA_PATH,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_validar_administrador(self):
        self.assertEqual(
            roles_service.validar_nombre_rol(" ADMINISTRADOR "),
            "administrador",
        )

    def test_validar_escaner(self):
        self.assertEqual(
            roles_service.validar_nombre_rol(" EsCaNeR "),
            "escaner",
        )

    def test_rechazar_rol_diferente(self):
        for rol in ("tutor", "directivo", "", None):
            with self.subTest(rol=rol):
                with self.assertRaises(InvalidRoleError):
                    roles_service.validar_nombre_rol(rol)

    def test_asegurar_roles_de_autenticacion(self):
        roles = roles_service.asegurar_roles_autenticacion(
            self.database_path
        )

        self.assertEqual(
            [rol["nombre"] for rol in roles],
            ["administrador", "escaner", "alumno"],
        )
        self.assertTrue(all(rol["rol_id"] > 0 for rol in roles))

    def test_ejecutar_dos_veces_no_duplica_roles(self):
        primero = roles_service.asegurar_roles_autenticacion(
            self.database_path
        )
        segundo = roles_service.asegurar_roles_autenticacion(
            self.database_path
        )

        connection = database_manager.get_connection(self.database_path)
        try:
            cantidad = connection.execute(
                "SELECT COUNT(*) FROM roles;"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(cantidad, 3)
        self.assertEqual(
            [rol["rol_id"] for rol in primero],
            [rol["rol_id"] for rol in segundo],
        )

    def test_no_depende_de_ids_fijos(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute(
                "INSERT INTO roles (nombre) VALUES (?);",
                ("rol_previo",),
            )
            connection.commit()
        finally:
            connection.close()

        roles = roles_service.asegurar_roles_autenticacion(
            self.database_path
        )

        self.assertTrue(all(rol["rol_id"] > 1 for rol in roles))


    def test_role_constants_separate_system_from_authentication(self):
        self.assertEqual(ROL_ALUMNO, "alumno")
        self.assertEqual(
            ROLES_SISTEMA,
            (ROL_ADMINISTRADOR, ROL_ESCANER, ROL_ALUMNO),
        )
        self.assertEqual(
            ROLES_AUTENTICACION,
            (ROL_ADMINISTRADOR, ROL_ESCANER, ROL_ALUMNO),
        )

    def test_validar_nombre_rol_sistema_accepts_all_system_roles(self):
        for role in ROLES_SISTEMA:
            with self.subTest(role=role):
                self.assertEqual(
                    roles_service.validar_nombre_rol_sistema(
                        f" {role.upper()} "
                    ),
                    role,
                )

    def test_validar_nombre_rol_sistema_rejects_unknown_roles(self):
        for role in ("tutor", "directivo", "", None, True):
            with self.subTest(role=role):
                with self.assertRaises(InvalidRoleError):
                    roles_service.validar_nombre_rol_sistema(role)

    def test_asegurar_roles_sistema_creates_three_roles_idempotently(self):
        first = roles_service.asegurar_roles_sistema(self.database_path)
        second = roles_service.asegurar_roles_sistema(self.database_path)
        self.assertEqual(
            [item["nombre"] for item in first], list(ROLES_SISTEMA)
        )
        self.assertEqual(
            [item["rol_id"] for item in first],
            [item["rol_id"] for item in second],
        )
        connection = database_manager.get_connection(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM roles;").fetchone()[0],
                3,
            )
        finally:
            connection.close()

    def test_alumno_role_has_controlled_description(self):
        roles_service.asegurar_roles_sistema(self.database_path)
        connection = database_manager.get_connection(self.database_path)
        try:
            description = connection.execute(
                "SELECT descripcion FROM roles WHERE nombre = ?;",
                (ROL_ALUMNO,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(
            description,
            "Alumno con acceso exclusivo a su informacion escolar.",
        )

    def test_crear_usuario_demo_does_not_enable_student_role(self):
        with self.assertRaises(InvalidRoleError):
            usuarios_service.crear_usuario_demo(
                "Alumno",
                "alumno@edupass.test",
                "Password123!",
                ROL_ALUMNO,
                self.database_path,
            )

    def test_historical_demo_roles_still_create_users(self):
        for index, role in enumerate((ROL_ADMINISTRADOR, ROL_ESCANER)):
            with self.subTest(role=role):
                user = usuarios_service.crear_usuario_demo(
                    role,
                    f"{index}@edupass.test",
                    "Password123!",
                    role,
                    self.database_path,
                )
                self.assertEqual(user["rol_nombre"], role)

if __name__ == "__main__":
    unittest.main()
