from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.auth import roles_service
from edupass.persistence import database_manager
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
        for rol in ("alumno", "tutor", "directivo", "", None):
            with self.subTest(rol=rol):
                with self.assertRaises(InvalidRoleError):
                    roles_service.validar_nombre_rol(rol)

    def test_asegurar_ambos_roles(self):
        roles = roles_service.asegurar_roles_autenticacion(
            self.database_path
        )

        self.assertEqual(
            [rol["nombre"] for rol in roles],
            ["administrador", "escaner"],
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

        self.assertEqual(cantidad, 2)
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


if __name__ == "__main__":
    unittest.main()
