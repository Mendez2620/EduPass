from pathlib import Path
import shutil
import sqlite3
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_ROOT = PROJECT_ROOT / ".test_tmp"
sys.path.insert(0, str(SRC_PATH))

from edupass.persistence import database_manager


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = TEST_TMP_ROOT / self._testMethodName
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = self.test_dir / "edupass_test.sqlite"
        self.schema_path = PROJECT_ROOT / "src" / "edupass" / "persistence" / "schema.sql"

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        if TEST_TMP_ROOT.exists() and not any(TEST_TMP_ROOT.iterdir()):
            TEST_TMP_ROOT.rmdir()

    def _initialize_test_database(self):
        return database_manager.initialize_database(self.database_path, self.schema_path)

    def _get_table_columns(self, table_name):
        connection = sqlite3.connect(self.database_path)
        try:
            rows = connection.execute(f"PRAGMA table_info({table_name});").fetchall()
        finally:
            connection.close()
        return {row[1] for row in rows}

    def _table_has_unique_column(self, table_name, column_name):
        connection = sqlite3.connect(self.database_path)
        try:
            indexes = connection.execute(f"PRAGMA index_list({table_name});").fetchall()
            for index in indexes:
                index_name = index[1]
                is_unique = bool(index[2])
                if not is_unique:
                    continue

                columns = connection.execute(f"PRAGMA index_info({index_name});").fetchall()
                unique_columns = {column[2] for column in columns}
                if column_name in unique_columns:
                    return True
        finally:
            connection.close()
        return False

    def test_initialize_database_creates_temporary_sqlite_database(self):
        result_path = self._initialize_test_database()

        self.assertEqual(result_path, self.database_path)
        self.assertTrue(result_path.exists())
        self.assertEqual(result_path.name, "edupass_test.sqlite")

    def test_verify_expected_tables_confirms_minimum_tables_exist(self):
        self._initialize_test_database()

        is_ready, missing_tables = database_manager.verify_expected_tables(self.database_path)

        self.assertTrue(is_ready)
        self.assertEqual(missing_tables, set())

    def test_list_tables_returns_core_edupass_tables(self):
        self._initialize_test_database()

        tables = set(database_manager.list_tables(self.database_path))

        self.assertIn("alumnos", tables)
        self.assertIn("movimientos", tables)
        self.assertIn("notificaciones_push", tables)
        self.assertIn("intentos_rechazados", tables)

    def test_initialize_database_can_run_twice_on_same_database(self):
        first_result = self._initialize_test_database()
        second_result = self._initialize_test_database()
        is_ready, missing_tables = database_manager.verify_expected_tables(self.database_path)

        self.assertEqual(first_result, self.database_path)
        self.assertEqual(second_result, self.database_path)
        self.assertTrue(is_ready)
        self.assertEqual(missing_tables, set())

    def test_initialize_database_fails_when_schema_is_missing(self):
        missing_schema = self.test_dir / "schema_no_existe.sql"

        with self.assertRaises(FileNotFoundError) as context:
            database_manager.initialize_database(self.database_path, missing_schema)

        self.assertIn("No se encontro el archivo de esquema", str(context.exception))

    def test_movimientos_table_contains_columns_for_hu28_and_rf33(self):
        self._initialize_test_database()

        columns = self._get_table_columns("movimientos")

        expected_columns = {
            "alumno_id",
            "fecha_hora",
            "tipo_movimiento",
            "area_id",
            "punto_plantel",
            "usuario_id",
            "dispositivo_id",
        }
        self.assertTrue(expected_columns.issubset(columns))

    def test_notificaciones_push_table_contains_estado_for_rf44(self):
        self._initialize_test_database()

        columns = self._get_table_columns("notificaciones_push")

        self.assertIn("estado", columns)

    def test_intentos_rechazados_table_contains_columns_for_rf50(self):
        self._initialize_test_database()

        columns = self._get_table_columns("intentos_rechazados")

        expected_columns = {
            "motivo",
            "fecha_hora",
            "usuario_id",
            "dispositivo_id",
            "alumno_id",
        }
        self.assertTrue(expected_columns.issubset(columns))

    def test_alumnos_matricula_has_unique_constraint_for_rf02(self):
        self._initialize_test_database()

        has_unique_matricula = self._table_has_unique_column("alumnos", "matricula")

        self.assertTrue(has_unique_matricula)


if __name__ == "__main__":
    unittest.main()
