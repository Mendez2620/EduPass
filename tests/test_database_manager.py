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

    def test_expected_tables_includes_usuario_alumno(self):
        self.assertIn("usuario_alumno", database_manager.EXPECTED_TABLES)

    def test_new_database_includes_usuario_alumno(self):
        self._initialize_test_database()
        self.assertIn(
            "usuario_alumno",
            database_manager.list_tables(self.database_path),
        )

    def test_usuario_alumno_schema_is_one_to_one_and_safe(self):
        self._initialize_test_database()
        connection = sqlite3.connect(self.database_path)
        try:
            columns = connection.execute(
                "PRAGMA table_info(usuario_alumno);"
            ).fetchall()
            foreign_keys = connection.execute(
                "PRAGMA foreign_key_list(usuario_alumno);"
            ).fetchall()
        finally:
            connection.close()

        columns_by_name = {row[1]: row for row in columns}
        self.assertEqual(
            set(columns_by_name),
            {"usuario_alumno_id", "usuario_id", "alumno_id"},
        )
        self.assertEqual(columns_by_name["usuario_id"][3], 1)
        self.assertEqual(columns_by_name["alumno_id"][3], 1)
        self.assertTrue(
            self._table_has_unique_column("usuario_alumno", "usuario_id")
        )
        self.assertTrue(
            self._table_has_unique_column("usuario_alumno", "alumno_id")
        )
        references = {(row[2], row[3], row[4]) for row in foreign_keys}
        self.assertIn(("usuarios", "usuario_id", "usuario_id"), references)
        self.assertIn(("alumnos", "alumno_id", "alumno_id"), references)
        for sensitive in (
            "password_hash", "fotografia", "token", "estado", "matricula"
        ):
            self.assertNotIn(sensitive, columns_by_name)

    def test_initialize_existing_database_preserves_domain_data(self):
        self._initialize_test_database()
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("DROP TABLE usuario_alumno;")
            role_id = connection.execute(
                "INSERT INTO roles (nombre) VALUES (?);", ("alumno",)
            ).lastrowid
            user_id = connection.execute(
                "INSERT INTO usuarios "
                "(nombre, correo, password_hash, estado, rol_id) "
                "VALUES (?, ?, ?, ?, ?);",
                ("Usuario", "u@edupass.test", "hash", "activo", role_id),
            ).lastrowid
            student_id = connection.execute(
                "INSERT INTO alumnos "
                "(nombre, matricula, grado, grupo, fotografia, estado) "
                "VALUES (?, ?, ?, ?, ?, ?);",
                ("Alumno", "MAT-1", "1", "A", "foto.png", "activo"),
            ).lastrowid
            connection.execute(
                "INSERT INTO qr_tokens "
                "(alumno_id, token_hash, generado_en, expira_en, estado) "
                "VALUES (?, ?, ?, ?, ?);",
                (student_id, "qr-hash", "2026-01-01", "2026-01-02", "activo"),
            )
            connection.execute(
                "INSERT INTO movimientos "
                "(alumno_id, tipo_movimiento, fecha_hora, usuario_id) "
                "VALUES (?, ?, ?, ?);",
                (student_id, "entrada", "2026-01-01", user_id),
            )
            connection.commit()
        finally:
            connection.close()

        database_manager.initialize_database(self.database_path, self.schema_path)
        database_manager.initialize_database(self.database_path, self.schema_path)
        connection = database_manager.get_connection(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM usuarios;").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM alumnos;").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM qr_tokens;").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM movimientos;").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM usuario_alumno;").fetchone()[0], 0)
        finally:
            connection.close()

    def test_usuario_alumno_unique_constraints_remain_active(self):
        self._initialize_test_database()
        connection = database_manager.get_connection(self.database_path)
        try:
            role_id = connection.execute(
                "INSERT INTO roles (nombre) VALUES (?);", ("alumno",)
            ).lastrowid
            user_ids = []
            student_ids = []
            for number in (1, 2):
                user_ids.append(connection.execute(
                    "INSERT INTO usuarios "
                    "(nombre, correo, password_hash, estado, rol_id) "
                    "VALUES (?, ?, ?, ?, ?);",
                    (f"U{number}", f"u{number}@edupass.test", "hash", "activo", role_id),
                ).lastrowid)
                student_ids.append(connection.execute(
                    "INSERT INTO alumnos "
                    "(nombre, matricula, grado, grupo, estado) "
                    "VALUES (?, ?, ?, ?, ?);",
                    (f"A{number}", f"M-{number}", "1", "A", "activo"),
                ).lastrowid)
            connection.execute(
                "INSERT INTO usuario_alumno (usuario_id, alumno_id) VALUES (?, ?);",
                (user_ids[0], student_ids[0]),
            )
            connection.commit()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO usuario_alumno (usuario_id, alumno_id) VALUES (?, ?);",
                    (user_ids[0], student_ids[1]),
                )
            connection.rollback()
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO usuario_alumno (usuario_id, alumno_id) VALUES (?, ?);",
                    (user_ids[1], student_ids[0]),
                )
        finally:
            connection.close()

    def test_database_manager_connections_enable_foreign_keys(self):
        self._initialize_test_database()
        connection = database_manager.get_connection(self.database_path)
        try:
            self.assertEqual(
                connection.execute("PRAGMA foreign_keys;").fetchone()[0], 1
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
