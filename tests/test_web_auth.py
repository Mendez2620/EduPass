from html.parser import HTMLParser
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.auth import usuarios_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import usuario_repository
from edupass.web import create_app


class _CsrfParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input" and attributes.get("name") == "csrf_token":
            self.token = attributes.get("value")


class TestWebAuth(unittest.TestCase):
    PASSWORD = "ClaveWebSegura123"
    GENERIC_MESSAGE = (
        "No fue posible iniciar sesion con las credenciales proporcionadas."
    )

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "web_auth.sqlite"
        )
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-only-secret",
                "DATABASE_PATH": self.database_path,
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        self.admin = self._create_user(
            "Administradora Web",
            "admin@edupass.test",
            "administrador",
        )
        self.scanner = self._create_user(
            "Escaner Web",
            "scanner@edupass.test",
            "escaner",
        )
        self.inactive = self._create_user(
            "Usuario Inactivo",
            "inactive@edupass.test",
            "administrador",
        )
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute(
                "UPDATE usuarios SET estado = 'inactivo' "
                "WHERE usuario_id = ?;",
                (self.inactive["usuario_id"],),
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _create_user(self, name, email, role):
        return usuarios_service.crear_usuario_demo(
            name,
            email,
            self.PASSWORD,
            role,
            self.database_path,
        )

    def _login(self, email, password=None, follow_redirects=False):
        return self.client.post(
            "/login",
            data={
                "correo": email,
                "password": password or self.PASSWORD,
            },
            follow_redirects=follow_redirects,
        )

    def test_get_login_returns_form_with_csrf_field(self):
        csrf_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "csrf-form-test-only-secret",
                "DATABASE_PATH": Path(self.temporary_directory.name) / "csrf_form.sqlite",
                "WTF_CSRF_ENABLED": True,
            }
        )
        response = csrf_app.test_client().get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn('name="csrf_token"', response.get_data(as_text=True))

    def test_valid_admin_login_redirects_to_admin(self):
        response = self._login("admin@edupass.test")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin"))

    def test_valid_scanner_login_redirects_to_scanner(self):
        response = self._login("scanner@edupass.test")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/scanner"))

    def test_invalid_credentials_and_inactive_user_share_generic_message(self):
        cases = (
            ("admin@edupass.test", "incorrecta"),
            ("missing@edupass.test", self.PASSWORD),
            ("inactive@edupass.test", self.PASSWORD),
        )
        for email, password in cases:
            with self.subTest(email=email):
                response = self._login(
                    email,
                    password,
                    follow_redirects=True,
                )
                body = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(self.GENERIC_MESSAGE, body)

    def test_login_response_does_not_expose_password_or_hash(self):
        stored_user = usuario_repository.obtener_por_id(
            self.admin["usuario_id"],
            self.database_path,
        )
        response = self._login(
            "admin@edupass.test",
            "incorrecta",
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)

        self.assertNotIn("incorrecta", body)
        self.assertNotIn("password_hash", body)
        self.assertNotIn(self.app.config["SECRET_KEY"], body)
        self.assertNotIn(stored_user["password_hash"], body)
        self.assertNotIn(self.PASSWORD, body)

    def test_authenticated_user_is_redirected_away_from_login(self):
        self._login("admin@edupass.test")

        response = self.client.get("/login")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin"))

    def test_root_redirects_by_authentication_and_role(self):
        visitor = self.client.get("/")
        self.assertTrue(visitor.headers["Location"].endswith("/login"))

        self._login("scanner@edupass.test")
        scanner = self.client.get("/")
        self.assertTrue(scanner.headers["Location"].endswith("/scanner"))

    def test_login_marks_session_permanent(self):
        self._login("admin@edupass.test")

        with self.client.session_transaction() as session:
            self.assertTrue(session.permanent)
            self.assertEqual(
                session.get("_user_id"),
                str(self.admin["usuario_id"]),
            )

    def test_logout_post_removes_session_and_get_is_not_allowed(self):
        self._login("admin@edupass.test")

        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)
        self.assertEqual(self.client.get("/logout").status_code, 405)

    def test_inactive_user_is_not_reloaded(self):
        self._login("admin@edupass.test")
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute(
                "UPDATE usuarios SET estado = 'inactivo' "
                "WHERE usuario_id = ?;",
                (self.admin["usuario_id"],),
            )
            connection.commit()
        finally:
            connection.close()

        response = self.client.get("/admin")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_deleted_user_is_not_reloaded(self):
        self._login("admin@edupass.test")
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute(
                "DELETE FROM usuarios WHERE usuario_id = ?;",
                (self.admin["usuario_id"],),
            )
            connection.commit()
        finally:
            connection.close()

        response = self.client.get("/admin")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_real_csrf_accepts_token_and_rejects_missing_token(self):
        csrf_database = (
            Path(self.temporary_directory.name) / "csrf_enabled.sqlite"
        )
        csrf_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "csrf-test-only-secret",
                "DATABASE_PATH": csrf_database,
                "WTF_CSRF_ENABLED": True,
            }
        )
        usuarios_service.crear_usuario_demo(
            "Admin CSRF",
            "csrf@edupass.test",
            self.PASSWORD,
            "administrador",
            csrf_database,
        )
        client = csrf_app.test_client()
        page = client.get("/login")
        parser = _CsrfParser()
        parser.feed(page.get_data(as_text=True))
        self.assertIsNotNone(parser.token)

        accepted = client.post(
            "/login",
            data={
                "correo": "csrf@edupass.test",
                "password": self.PASSWORD,
                "csrf_token": parser.token,
            },
        )
        self.assertEqual(accepted.status_code, 302)

        second_client = csrf_app.test_client()
        rejected = second_client.post(
            "/login",
            data={
                "correo": "csrf@edupass.test",
                "password": self.PASSWORD,
            },
        )
        self.assertEqual(rejected.status_code, 400)

    def test_logout_accepts_valid_csrf_and_rejects_missing_csrf(self):
        csrf_database = (
            Path(self.temporary_directory.name) / "logout_csrf.sqlite"
        )
        csrf_app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "csrf-test-only-secret",
                "DATABASE_PATH": csrf_database,
                "WTF_CSRF_ENABLED": True,
            }
        )
        usuarios_service.crear_usuario_demo(
            "Admin CSRF",
            "logout@edupass.test",
            self.PASSWORD,
            "administrador",
            csrf_database,
        )
        client = csrf_app.test_client()
        page = client.get("/login")
        parser = _CsrfParser()
        parser.feed(page.get_data(as_text=True))
        client.post(
            "/login",
            data={
                "correo": "logout@edupass.test",
                "password": self.PASSWORD,
                "csrf_token": parser.token,
            },
        )

        admin_page = client.get("/admin")
        logout_parser = _CsrfParser()
        logout_parser.feed(admin_page.get_data(as_text=True))
        valid_logout = client.post(
            "/logout",
            data={"csrf_token": logout_parser.token},
        )
        self.assertEqual(valid_logout.status_code, 302)

        page = client.get("/login")
        parser = _CsrfParser()
        parser.feed(page.get_data(as_text=True))
        client.post(
            "/login",
            data={
                "correo": "logout@edupass.test",
                "password": self.PASSWORD,
                "csrf_token": parser.token,
            },
        )

        response = client.post("/logout")

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
