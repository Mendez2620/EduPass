from pathlib import Path
import shutil
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
TEST_TMP_DIR = PROJECT_ROOT / ".test_tmp"
sys.path.insert(0, str(SRC_PATH))

from edupass.persistence import database_manager


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        TEST_TMP_DIR.mkdir(exist_ok=True)

    def tearDown(self):
        if TEST_TMP_DIR.exists():
            shutil.rmtree(TEST_TMP_DIR)

    def test_initialize_database_creates_expected_tables(self):
        database_path = TEST_TMP_DIR / "edupass_test.sqlite"
        schema_path = PROJECT_ROOT / "src" / "edupass" / "persistence" / "schema.sql"

        result_path = database_manager.initialize_database(database_path, schema_path)
        is_ready, missing_tables = database_manager.verify_expected_tables(result_path)

        self.assertTrue(result_path.exists())
        self.assertTrue(is_ready)
        self.assertEqual(missing_tables, set())

    def test_initialize_database_fails_when_schema_is_missing(self):
        database_path = TEST_TMP_DIR / "edupass_test.sqlite"
        missing_schema = TEST_TMP_DIR / "schema_no_existe.sql"

        with self.assertRaises(FileNotFoundError) as context:
            database_manager.initialize_database(database_path, missing_schema)

        self.assertIn("No se encontro el archivo de esquema", str(context.exception))


if __name__ == "__main__":
    unittest.main()
