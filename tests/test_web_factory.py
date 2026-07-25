from datetime import timedelta
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.persistence import database_manager
from edupass.web import create_app
from edupass.web.__main__ import _port_from_environment


class TestWebFactory(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "web_factory.sqlite"
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _config(self, **changes):
        config = {
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE_PATH": self.database_path,
        }
        config.update(changes)
        return config

    def test_create_app_accepts_test_config_and_initializes_database(self):
        app = create_app(self._config())

        self.assertTrue(app.config["TESTING"])
        self.assertEqual(app.config["DATABASE_PATH"], self.database_path)
        self.assertTrue(self.database_path.is_file())
        ready, missing = database_manager.verify_expected_tables(
            self.database_path
        )
        self.assertTrue(ready)
        self.assertEqual(missing, set())

    def test_missing_secret_key_outside_tests_fails_clearly(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "EDUPASS_SECRET_KEY"):
                create_app()

    def test_default_session_and_cookie_security_configuration(self):
        app = create_app(self._config())

        self.assertEqual(
            app.config["PERMANENT_SESSION_LIFETIME"],
            timedelta(minutes=30),
        )
        self.assertTrue(app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        self.assertFalse(app.config["SESSION_COOKIE_SECURE"])
        self.assertTrue(app.config["WTF_CSRF_ENABLED"])

    def test_database_path_is_normalized_to_path(self):
        app = create_app(
            self._config(DATABASE_PATH=str(self.database_path))
        )

        self.assertIsInstance(app.config["DATABASE_PATH"], Path)

    def test_invalid_session_minutes_fails_clearly(self):
        with patch.dict(
            os.environ,
            {"EDUPASS_SESSION_MINUTES": "invalido"},
            clear=False,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "EDUPASS_SESSION_MINUTES",
            ):
                create_app(self._config())

    def test_invalid_web_port_fails_clearly(self):
        for value in ("texto", "0", "65536"):
            with self.subTest(value=value):
                with patch.dict(
                    os.environ,
                    {"EDUPASS_PORT": value},
                    clear=False,
                ):
                    with self.assertRaisesRegex(RuntimeError, "EDUPASS_PORT"):
                        _port_from_environment()

    def test_loading_web_package_does_not_import_pyside6(self):
        was_loaded = "PySide6" in sys.modules
        import edupass.web

        importlib.reload(edupass.web)

        self.assertEqual("PySide6" in sys.modules, was_loaded)

    def test_web_entrypoint_does_not_import_desktop_main(self):
        was_loaded = "edupass.main" in sys.modules
        import edupass.web.__main__

        importlib.reload(edupass.web.__main__)

        self.assertEqual("edupass.main" in sys.modules, was_loaded)


if __name__ == "__main__":
    unittest.main()
