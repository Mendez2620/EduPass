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


class TestWebUxFinal(unittest.TestCase):
    PASSWORD = "Password123!"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "ux_final.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "ux-final-test",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.admin = usuarios_service.crear_administrador(
            "Admin UX", "admin.ux@edupass.test", self.PASSWORD,
            self.database_path,
        )
        self.scanner = usuarios_service.crear_escaner(
            "Scanner UX", "scanner.ux@edupass.test", self.PASSWORD,
            self.database_path,
        )
        self.student = alumnos_service.registrar_alumno(
            "Laura Martínez Hernández", "SEM9-UI-001", "6", "A",
            estado="activo", database_path=self.database_path,
        )
        self.historical = alumnos_service.registrar_alumno(
            "Alumno Histórico", "SEM9-UI-002", "5", "B",
            estado="activo", database_path=self.database_path,
        )
        self.account = cuentas_alumno_service.crear_cuenta_alumno(
            self.student["alumno_id"], "student.ux@edupass.test",
            self.PASSWORD, self.admin["usuario_id"], self.database_path,
        )
        self.navigation_js = (
            SRC_PATH / "edupass" / "web" / "static" / "js" / "navigation.js"
        ).read_text(encoding="utf-8")
        self.css = (
            SRC_PATH / "edupass" / "web" / "static" / "css" / "app.css"
        ).read_text(encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _login(self, email="admin.ux@edupass.test"):
        return self.client.post(
            "/login", data={"correo": email, "password": self.PASSWORD}
        )

    def test_edit_student_contains_school_and_access_fields(self):
        self._login()
        body = self.client.get(
            f'/admin/alumnos/{self.student["alumno_id"]}/editar'
        ).get_data(as_text=True)
        for value in (
            "Datos escolares", "Estado escolar", "Acceso a EduPass",
            "Correo", "Estado de acceso", "student.ux@edupass.test",
        ):
            self.assertIn(value, body)
        self.assertNotIn('type="password"', body)

    def test_edit_updates_student_and_linked_account(self):
        self._login()
        response = self.client.post(
            f'/admin/alumnos/{self.student["alumno_id"]}/editar',
            data={
                "nombre": "Laura Martínez Actualizada",
                "matricula": "SEM9-UI-009",
                "grado": "6",
                "grupo": "C",
                "estado_escolar": "activo",
                "correo": "laura.actualizada@edupass.test",
                "estado_acceso": "inactivo",
            },
        )
        self.assertEqual(response.status_code, 302)
        student = alumnos_service.consultar_alumno_por_id(
            self.student["alumno_id"], self.database_path
        )
        account = cuentas_alumno_service.consultar_cuenta_alumno(
            self.account["usuario_id"], self.database_path
        )
        self.assertEqual(student["nombre"], "Laura Martínez Actualizada")
        self.assertEqual(student["matricula"], "SEM9-UI-009")
        self.assertEqual(student["grupo"], "C")
        self.assertEqual(account["correo"], "laura.actualizada@edupass.test")
        self.assertEqual(account["usuario_estado"], "inactivo")

    def test_listing_has_simplified_access_and_independent_password_action(self):
        self._login()
        body = self.client.get("/admin/alumnos").get_data(as_text=True)
        self.assertIn("Acceso EduPass", body)
        self.assertNotIn(">Cuenta EduPass<", body)
        self.assertNotIn(">Acceso<", body)
        self.assertNotIn("Administrar acceso", body)
        self.assertIn("Generar contraseña temporal", body)
        self.assertIn(f'/admin/cuentas-alumnos/{self.account["usuario_id"]}/password', body)

    def test_historical_student_shows_create_account(self):
        self._login()
        body = self.client.get("/admin/alumnos").get_data(as_text=True)
        row = body.split("Alumno Histórico", 1)[1].split("</tr>", 1)[0]
        self.assertIn("Sin cuenta", row)
        self.assertIn("Crear cuenta", row)
        self.assertIn(f'alumno_id={self.historical["alumno_id"]}', row)

    def test_mobile_student_rows_are_cards_without_duplicated_markup(self):
        self.assertIn(".students-responsive-table tr", self.css)
        self.assertIn('content: attr(data-label)', self.css)
        self.assertIn("grid-template-columns: minmax(110px, 42%)", self.css)
        self.assertIn("white-space: normal", self.css)

    def test_hamburger_starts_closed_and_toggles(self):
        self.assertIn('aria-expanded="false"', (
            SRC_PATH / "edupass" / "web" / "templates" / "base.html"
        ).read_text(encoding="utf-8"))
        self.assertIn("display: none", self.css)
        self.assertIn('button.setAttribute("aria-expanded", "true")', self.navigation_js)
        self.assertIn("closeMenu();", self.navigation_js)

    def test_hamburger_closes_on_link_outside_and_escape(self):
        self.assertIn('event.target.closest("a")', self.navigation_js)
        self.assertIn("!navigation.contains(event.target)", self.navigation_js)
        self.assertIn('event.key === "Escape"', self.navigation_js)
        self.assertIn('button.setAttribute("aria-expanded", "false")', self.navigation_js)

    def test_desktop_navigation_remains_horizontal(self):
        desktop = self.css.split("@media (max-width: 768px)", 1)[0]
        self.assertIn("nav {", desktop)
        self.assertIn("display: flex", desktop)
        self.assertIn(".nav-toggle", desktop)
        self.assertIn("display: none", desktop)

    def test_role_menus_remain_separated(self):
        expected = {
            "admin.ux@edupass.test": ("Administracion", "Alumnos", "Administradores", "Escáneres", "Historial"),
            "student.ux@edupass.test": ("Mi panel", "Mi credencial", "Mi historial", "Notificaciones"),
            "scanner.ux@edupass.test": ("Panel de escaneo", "Escanear QR"),
        }
        forbidden = {
            "admin.ux@edupass.test": ("Mi credencial", "Panel de escaneo"),
            "student.ux@edupass.test": ("Administradores", "Panel de escaneo"),
            "scanner.ux@edupass.test": ("Administradores", "Mi credencial"),
        }
        for email, labels in expected.items():
            with self.subTest(email=email):
                with self.client.session_transaction() as session:
                    session.clear()
                self._login(email)
                body = self.client.get("/", follow_redirects=True).get_data(as_text=True)
                for label in labels:
                    self.assertIn(label, body)
                for label in forbidden[email]:
                    self.assertNotIn(label, body)
                self.assertIn('method="post" action="/logout"', body)


if __name__ == "__main__":
    unittest.main()
