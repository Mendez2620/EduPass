from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.persistence import database_manager
from edupass.persistence.repositories import rol_repository
from edupass.shared.errors import ConsultaSqlError, RepositoryError


class TestRolRepository(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "roles_test.sqlite"
        )
        database_manager.initialize_database(
            self.database_path,
            SCHEMA_PATH,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_obtener_rol_inexistente_devuelve_none(self):
        self.assertIsNone(
            rol_repository.obtener_por_nombre(
                "administrador",
                self.database_path,
            )
        )

    def test_crear_administrador(self):
        rol = rol_repository.crear_si_no_existe(
            "administrador",
            "Administracion escolar.",
            self.database_path,
        )

        self.assertGreater(rol["rol_id"], 0)
        self.assertEqual(rol["nombre"], "administrador")
        self.assertEqual(rol["descripcion"], "Administracion escolar.")

    def test_crear_escaner(self):
        rol = rol_repository.crear_si_no_existe(
            "escaner",
            "Personal de escaneo.",
            self.database_path,
        )

        self.assertGreater(rol["rol_id"], 0)
        self.assertEqual(rol["nombre"], "escaner")

    def test_crear_mismo_rol_dos_veces_es_idempotente(self):
        primero = rol_repository.crear_si_no_existe(
            "administrador",
            "Primera descripcion.",
            self.database_path,
        )
        segundo = rol_repository.crear_si_no_existe(
            "administrador",
            "Segunda descripcion.",
            self.database_path,
        )

        connection = database_manager.get_connection(self.database_path)
        try:
            cantidad = connection.execute(
                "SELECT COUNT(*) FROM roles WHERE nombre = ?;",
                ("administrador",),
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(primero["rol_id"], segundo["rol_id"])
        self.assertEqual(cantidad, 1)

    def test_normaliza_nombre_del_rol(self):
        creado = rol_repository.crear_si_no_existe(
            "  ADMINISTRADOR  ",
            database_path=self.database_path,
        )
        consultado = rol_repository.obtener_por_nombre(
            "  AdMiNiStRaDoR  ",
            self.database_path,
        )

        self.assertEqual(creado, consultado)
        self.assertEqual(creado["nombre"], "administrador")

    def test_devuelve_rol_id_real_sin_asumir_valor_fijo(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute(
                "INSERT INTO roles (nombre) VALUES (?);",
                ("rol_previo",),
            )
            connection.commit()
        finally:
            connection.close()

        rol = rol_repository.crear_si_no_existe(
            "administrador",
            database_path=self.database_path,
        )

        self.assertGreater(rol["rol_id"], 1)
        self.assertEqual(
            rol_repository.obtener_por_nombre(
                "administrador",
                self.database_path,
            )["rol_id"],
            rol["rol_id"],
        )

    def test_error_sqlite_se_traduce_a_repository_error(self):
        original = sqlite3.OperationalError("fallo controlado")
        with patch.object(
            rol_repository.database_manager,
            "get_connection",
            side_effect=original,
        ):
            with self.assertRaises(RepositoryError) as context:
                rol_repository.obtener_por_nombre(
                    "administrador",
                    self.database_path,
                )

        self.assertIs(context.exception.__cause__, original)
        self.assertNotIn("SELECT", str(context.exception).upper())

    def test_sql_faltante_se_traduce_segun_patron_existente(self):
        with patch.object(
            rol_repository,
            "_SELECT_BY_NAME_FILE",
            "consulta_inexistente.sql",
        ):
            with self.assertRaises(ConsultaSqlError):
                rol_repository.obtener_por_nombre(
                    "administrador",
                    self.database_path,
                )


if __name__ == "__main__":
    unittest.main()
