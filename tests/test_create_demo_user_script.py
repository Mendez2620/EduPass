from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SRC_PATH))

from scripts import create_demo_user
from edupass.shared.errors import DuplicateUserError


class TestCreateDemoUserScript(unittest.TestCase):
    PASSWORD = "ClaveSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "script_test.sqlite"
        )
        self.local_database_path = PROJECT_ROOT / "data" / "edupass.sqlite"
        self.local_database_state = self._database_state(
            self.local_database_path
        )

    def tearDown(self):
        self.assertEqual(
            self._database_state(self.local_database_path),
            self.local_database_state,
        )
        self.temporary_directory.cleanup()

    @staticmethod
    def _database_state(path):
        if not path.exists():
            return None
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns

    def _run_script(
        self,
        inputs=None,
        passwords=None,
        database_path=None,
    ):
        inputs = inputs or (
            "Administrador Demo",
            "admin@edupass.test",
            "administrador",
        )
        passwords = passwords or (self.PASSWORD, self.PASSWORD)
        selected_path = database_path or self.database_path
        stdout = StringIO()
        stderr = StringIO()

        with patch("builtins.input", side_effect=inputs), patch.object(
            create_demo_user.getpass,
            "getpass",
            side_effect=passwords,
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            result = create_demo_user.main(
                ["--database", str(selected_path)]
            )

        return result, stdout.getvalue(), stderr.getvalue()

    def test_creacion_exitosa(self):
        result, stdout, stderr = self._run_script()

        self.assertEqual(result, 0)
        self.assertIn("[OK]", stdout)
        self.assertEqual(stderr, "")

        connection = sqlite3.connect(self.database_path)
        try:
            roles = connection.execute(
                "SELECT COUNT(*) FROM roles;"
            ).fetchone()[0]
            users = connection.execute(
                "SELECT COUNT(*) FROM usuarios;"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(roles, 2)
        self.assertEqual(users, 1)

    def test_confirmacion_de_contrasena_diferente(self):
        result, stdout, stderr = self._run_script(
            passwords=(self.PASSWORD, "OtraClave123")
        )

        self.assertEqual(result, 2)
        self.assertEqual(stdout, "")
        self.assertIn("[ERROR]", stderr)
        self.assertFalse(self.database_path.exists())

    def test_rol_invalido(self):
        result, stdout, stderr = self._run_script(
            inputs=(
                "Alumno Demo",
                "alumno@edupass.test",
                "alumno",
            )
        )

        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertIn("[ERROR]", stderr)
        self.assertFalse(self.database_path.exists())

    def test_usuario_duplicado(self):
        first_result, _, _ = self._run_script()
        second_result, stdout, stderr = self._run_script()

        self.assertEqual(first_result, 0)
        self.assertEqual(second_result, 1)
        self.assertEqual(stdout, "")
        self.assertIn("[ERROR]", stderr)

    def test_contrasena_no_aparece_en_salida(self):
        _, stdout, stderr = self._run_script()

        output = stdout + stderr
        self.assertNotIn(self.PASSWORD, output)

    def test_hash_no_aparece_en_salida(self):
        _, stdout, stderr = self._run_script()

        connection = sqlite3.connect(self.database_path)
        try:
            password_hash = connection.execute(
                "SELECT password_hash FROM usuarios;"
            ).fetchone()[0]
        finally:
            connection.close()

        output = stdout + stderr
        self.assertNotIn(password_hash, output)
        self.assertNotIn("scrypt:", output)

    def test_error_controlado_devuelve_codigo_distinto_de_cero(self):
        stdout = StringIO()
        stderr = StringIO()
        with patch("builtins.input", side_effect=(
            "Administrador Demo",
            "admin@edupass.test",
            "administrador",
        )), patch.object(
            create_demo_user.getpass,
            "getpass",
            side_effect=(self.PASSWORD, self.PASSWORD),
        ), patch.object(
            create_demo_user.usuarios_service,
            "crear_usuario_demo",
            side_effect=DuplicateUserError("dato sensible"),
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            result = create_demo_user.main(
                ["--database", str(self.database_path)]
            )

        self.assertEqual(result, 1)
        self.assertNotIn("dato sensible", stderr.getvalue())

    def test_opcion_database_utiliza_ruta_indicada(self):
        alternative_path = (
            Path(self.temporary_directory.name) / "alternativa.sqlite"
        )

        result, _, _ = self._run_script(database_path=alternative_path)

        self.assertEqual(result, 0)
        self.assertTrue(alternative_path.exists())
        self.assertFalse(self.database_path.exists())


if __name__ == "__main__":
    unittest.main()
