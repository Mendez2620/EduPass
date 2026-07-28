from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.auth import usuarios_service
from edupass.web import create_app


class TestWebRoles(unittest.TestCase):
    PASSWORD = "ClaveWebSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "web_roles.sqlite"
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
        self._create_user(
            "Administradora Web",
            "admin@edupass.test",
            "administrador",
        )
        self._create_user(
            "Escaner Web",
            "scanner@edupass.test",
            "escaner",
        )

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

    def _login(self, email):
        return self.client.post(
            "/login",
            data={"correo": email, "password": self.PASSWORD},
        )

    def test_visitor_is_redirected_from_protected_routes(self):
        for route in ("/admin", "/admin/alumnos", "/scanner"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_admin_accesses_admin_and_is_forbidden_from_scanner(self):
        self._login("admin@edupass.test")

        self.assertEqual(self.client.get("/admin").status_code, 200)
        forbidden = self.client.get("/scanner")
        self.assertEqual(forbidden.status_code, 403)
        self.assertIn(
            "Acceso no autorizado",
            forbidden.get_data(as_text=True),
        )

    def test_scanner_accesses_scanner_and_is_forbidden_from_admin(self):
        self._login("scanner@edupass.test")

        self.assertEqual(self.client.get("/scanner").status_code, 200)
        for route in ("/admin", "/admin/alumnos"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 403)
                self.assertIn(
                    "Acceso no autorizado",
                    response.get_data(as_text=True),
                )

    def test_scanner_dashboard_offers_manual_qr_validation(self):
        self._login("scanner@edupass.test")

        body = self.client.get("/scanner").get_data(as_text=True)

        self.assertIn("Validacion QR", body)
        self.assertIn("/scanner/validar", body)
        self.assertIn("Validar token", body)
        self.assertNotIn("getUserMedia", body)
        self.assertNotIn("Registrar movimiento", body)

    def test_unknown_route_uses_404_template(self):
        response = self.client.get("/ruta-inexistente")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Recurso no encontrado", response.get_data(as_text=True))

    def test_role_checks_use_names_not_fixed_numeric_ids(self):
        self._login("admin@edupass.test")

        body = self.client.get("/admin").get_data(as_text=True)

        self.assertIn("administrador", body)
        self.assertNotIn("rol_id", body)


if __name__ == "__main__":
    unittest.main()
