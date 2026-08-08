from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service, cuentas_alumno_service
from edupass.modules.auth import usuarios_service
from edupass.web import create_app


class TestWebUiResponsive(unittest.TestCase):
    PASSWORD = "ClaveVisual123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "ui.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "ui-test-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.admin = usuarios_service.crear_administrador(
            "Admin UI", "admin.ui@edupass.test", self.PASSWORD,
            self.database_path,
        )
        usuarios_service.crear_escaner(
            "Escaner UI", "scanner.ui@edupass.test", self.PASSWORD,
            self.database_path,
        )
        alumno = alumnos_service.registrar_alumno(
            "Alumno UI", "UI-001", "1", "A", estado="activo",
            database_path=self.database_path,
        )
        cuentas_alumno_service.crear_cuenta_alumno(
            alumno["alumno_id"], "student.ui@edupass.test", self.PASSWORD,
            self.admin["usuario_id"], self.database_path,
        )
        self.css = (
            SRC_PATH / "edupass" / "web" / "static" / "css" / "app.css"
        ).read_text(encoding="utf-8")
        self.scanner_js = (
            SRC_PATH / "edupass" / "web" / "static" / "js" /
            "scanner_validation.js"
        ).read_text(encoding="utf-8")
        self.scanner_template = (
            SRC_PATH / "edupass" / "web" / "templates" / "scanner" /
            "validar_qr.html"
        ).read_text(encoding="utf-8")
        self.base_template = (
            SRC_PATH / "edupass" / "web" / "templates" / "base.html"
        ).read_text(encoding="utf-8")

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _login(self, email):
        self.client.post(
            "/login", data={"correo": email, "password": self.PASSWORD}
        )

    def test_base_has_mobile_viewport_and_local_stylesheet(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn('name="viewport"', body)
        self.assertIn('content="width=device-width, initial-scale=1"', body)
        self.assertIn('/static/css/app.css', body)
        self.assertNotIn("cdn", body.lower())

    def test_css_has_390px_mobile_layout(self):
        self.assertIn("@media (max-width: 390px)", self.css)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", self.css)
        self.assertIn("min-height: 46px", self.css)
        self.assertIn("overflow-x: auto", self.css)

    def test_navigation_remains_separated_by_role(self):
        cases = (
            ("admin.ui@edupass.test", "/admin/alumnos", "/scanner/validar"),
            ("scanner.ui@edupass.test", "/scanner/validar", "/admin/alumnos"),
            ("student.ui@edupass.test", "/alumno/credencial", "/admin/alumnos"),
        )
        for email, expected, forbidden in cases:
            with self.subTest(email=email):
                self.client.post("/logout")
                self._login(email)
                body = self.client.get("/", follow_redirects=True).get_data(
                    as_text=True
                )
                self.assertIn('class="site-nav"', body)
                self.assertIn(expected, body)
                self.assertNotIn(forbidden, body)

    def test_admin_dashboard_is_grouped_without_duplicate_links(self):
        self._login("admin.ui@edupass.test")
        body = self.client.get("/admin").get_data(as_text=True)
        dashboard = body.split('<main class="page-shell">', 1)[1]
        for heading in (
            "Gestión escolar", "Usuarios y accesos", "Operación y consulta",
            "Credenciales", "Historial",
        ):
            self.assertIn(heading, body)
        for route in (
            "/admin/alumnos", "/admin/cuentas-alumnos",
            "/admin/administradores", "/admin/escaneres", "/admin/historial",
        ):
            self.assertEqual(dashboard.count(f'href="{route}"'), 1)

    def test_flash_messages_have_accessible_semantics_and_text_icons(self):
        response = self.client.post(
            "/login",
            data={"correo": "missing@edupass.test", "password": "incorrecta"},
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)
        self.assertIn('class="message message-error"', body)
        self.assertIn('role="alert"', body)
        self.assertIn('aria-live="assertive"', body)
        self.assertIn('class="message-icon" aria-hidden="true">✕', body)
        self.assertIn("No fue posible iniciar sesion", body)
        for indicator in ("✓", "⚠", "✕", "ℹ"):
            self.assertIn(indicator, self.base_template)
        for category in ("success", "warning", "error", "info"):
            self.assertIn(f".message-{category}", self.css)

    def test_scanner_has_css_qr_guide_without_external_resource_or_token(self):
        self._login("scanner.ui@edupass.test")
        body = self.client.get("/scanner/validar").get_data(as_text=True)
        self.assertIn('class="camera-guide"', body)
        self.assertIn("Coloca el código QR dentro del marco", body)
        self.assertIn("pointer-events: none", self.css)
        guide = body.split('class="camera-guide"', 1)[1].split("</div>", 1)[0]
        self.assertNotIn("<img", guide)
        self.assertNotIn("token", guide.lower())

    def test_movement_result_has_text_icon_and_live_region(self):
        self.assertIn('class="validation-result-icon"', self.scanner_template)
        self.assertIn('aria-live="polite"', self.scanner_template)
        self.assertIn('"✓" if result.estado == "valido" else "✕"', self.scanner_template)
        self.assertIn("Movimiento registrado", self.scanner_template)

    def test_camera_contract_and_manual_capture_are_preserved(self):
        self._login("scanner.ui@edupass.test")
        body = self.client.get("/scanner/validar").get_data(as_text=True)
        self.assertRegex(body, r"<video[^>]*autoplay")
        self.assertRegex(body, r"<video[^>]*muted")
        self.assertRegex(body, r"<video[^>]*playsinline")
        self.assertIn("data-camera-start", body)
        self.assertIn("data-token-input", body)
        self.assertIn("form.hidden_tag()", self.scanner_template)
        self.assertIn("decodeFromConstraints", self.scanner_js)
        self.assertIn('facingMode: { ideal: "environment" }', self.scanner_js)
        self.assertIn("audio: false", self.scanner_js)
        self.assertNotIn("form.submit", self.scanner_js)

    def test_student_credential_and_history_remain_available(self):
        self._login("student.ui@edupass.test")
        credential = self.client.get("/alumno/credencial")
        history = self.client.get("/alumno/historial")
        self.assertEqual(credential.status_code, 200)
        self.assertEqual(history.status_code, 200)
        self.assertIn("Mi credencial", credential.get_data(as_text=True))
        self.assertIn("Mi historial", history.get_data(as_text=True))

    def test_entry_exit_and_qr_logic_are_unchanged(self):
        self.assertIn("tipo_movimiento", self.scanner_template)
        self.assertIn("El movimiento se confirma manualmente", self.scanner_template)
        self.assertNotIn("data-camera-guide", self.scanner_js)
        self.assertNotIn("tokenPattern =", self.scanner_template)


if __name__ == "__main__":
    unittest.main()
