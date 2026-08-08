from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service, cuentas_alumno_service
from edupass.modules.auth import usuarios_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import usuario_alumno_repository
from edupass.shared.errors import AuthenticationError, RepositoryError
from edupass.web import create_app
from edupass.web.forms import CuentaAlumnoCrearForm, EstadoUsuarioForm


class TestWebCuentasAlumno(unittest.TestCase):
    PASSWORD = "Password123!"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "web_cuentas.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.admin = usuarios_service.crear_usuario_demo(
            "Admin Web", "admin@edupass.test", self.PASSWORD,
            "administrador", self.database_path,
        )
        self.scanner = usuarios_service.crear_usuario_demo(
            "Scanner Web", "scanner@edupass.test", self.PASSWORD,
            "escaner", self.database_path,
        )
        self.active_student = alumnos_service.registrar_alumno(
            "Alumno Activo", "WEB-001", "1", "A", None,
            "activo", self.database_path,
        )
        self.inactive_student = alumnos_service.registrar_alumno(
            "Alumno Inactivo", "WEB-002", "2", "B", None,
            "inactivo", self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _login(self, email="admin@edupass.test", password=None):
        return self.client.post(
            "/login",
            data={"correo": email, "password": password or self.PASSWORD},
        )

    def _create_account(self, student=None, email="student@edupass.test"):
        return cuentas_alumno_service.crear_cuenta_alumno(
            (student or self.active_student)["alumno_id"],
            email, self.PASSWORD, self.admin["usuario_id"], self.database_path,
        )

    def _create_post(self, student=None, email="student@edupass.test", password=None, confirmation=None):
        return self.client.post(
            "/admin/cuentas-alumnos/nueva",
            data={
                "alumno_id": (student or self.active_student)["alumno_id"],
                "correo": email,
                "password": password or self.PASSWORD,
                "confirmar_password": confirmation or password or self.PASSWORD,
            },
            follow_redirects=False,
        )

    def test_visitor_is_redirected_from_all_account_routes(self):
        for path in (
            "/admin/cuentas-alumnos",
            "/admin/cuentas-alumnos/nueva",
            "/admin/cuentas-alumnos/999/editar",
            "/admin/cuentas-alumnos/999/password",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_scanner_gets_403_and_no_navigation_link(self):
        self._login("scanner@edupass.test")
        response = self.client.get("/admin/cuentas-alumnos")
        self.assertEqual(response.status_code, 403)
        scanner_page = self.client.get("/scanner").get_data(as_text=True)
        self.assertNotIn("/admin/cuentas-alumnos", scanner_page)

    def test_admin_access_navigation_and_dashboard_card(self):
        self._login()
        dashboard = self.client.get("/admin").get_data(as_text=True)
        listing = self.client.get("/admin/cuentas-alumnos")
        self.assertEqual(listing.status_code, 200)
        self.assertIn("Cuentas de alumnos", dashboard)
        self.assertIn("Administrar cuentas de alumnos", dashboard)
        self.assertIn("/admin/cuentas-alumnos", dashboard)

    def test_listing_shows_student_accounts_not_other_roles(self):
        account = self._create_account()
        self._login()
        body = self.client.get("/admin/cuentas-alumnos").get_data(as_text=True)
        self.assertIn(account["correo"], body)
        self.assertIn("Alumno Activo", body)
        self.assertNotIn("admin@edupass.test", body)
        self.assertNotIn("scanner@edupass.test", body)
        self.assertIn("El acceso del alumno se habilitará en el siguiente incremento.", body)

    def test_listing_shows_unlinked_students_and_hides_linked_from_section(self):
        self._create_account()
        self._login()
        body = self.client.get("/admin/cuentas-alumnos").get_data(as_text=True)
        section = body.split("Alumnos sin cuenta", 1)[1]
        self.assertIn("Alumno Inactivo", section)
        self.assertNotIn("Alumno Activo", section)

    def test_creation_form_has_csrf_and_only_unlinked_options(self):
        csrf_app = create_app({"TESTING": True, "SECRET_KEY": "csrf", "DATABASE_PATH": Path(self.temporary_directory.name) / "csrf.sqlite"})
        with csrf_app.test_request_context("/admin/cuentas-alumnos/nueva"):
            form_html = CuentaAlumnoCrearForm(choices=[]).hidden_tag()
        self.assertIn('name="csrf_token"', form_html)
        self._create_account()
        self._login()
        body = self.client.get("/admin/cuentas-alumnos/nueva").get_data(as_text=True)
        self.assertNotIn("Alumno Activo — WEB-001", body)
        self.assertIn("Alumno Inactivo — WEB-002 — inactivo", body)

    def test_valid_creation_uses_prg_active_role_link_and_normalized_email(self):
        self._login()
        response = self._create_post(email="  STUDENT@EDUPASS.TEST  ")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/cuentas-alumnos"))
        account = usuario_alumno_repository.obtener_por_alumno(self.active_student["alumno_id"], self.database_path)
        self.assertEqual(account["correo"], "student@edupass.test")
        self.assertEqual(account["rol_nombre"], "alumno")
        self.assertEqual(account["usuario_estado"], "activo")

    def test_inactive_student_creation_returns_409(self):
        self._login()
        response = self._create_post(self.inactive_student, "inactive@edupass.test")
        self.assertEqual(response.status_code, 409)
        self.assertIn("No se puede activar una cuenta para un alumno inactivo.", response.get_data(as_text=True))

    def test_already_linked_student_returns_409(self):
        self._create_account()
        self._login()
        response = self._create_post(email="second@edupass.test")
        self.assertEqual(response.status_code, 409)
        self.assertIn("El alumno ya tiene una cuenta vinculada.", response.get_data(as_text=True))

    def test_duplicate_email_returns_409(self):
        self._login()
        response = self._create_post(email="admin@edupass.test")
        self.assertEqual(response.status_code, 409)
        self.assertIn("El correo ya está registrado.", response.get_data(as_text=True))

    def test_incomplete_or_mismatched_form_returns_400(self):
        self._login()
        incomplete = self.client.post("/admin/cuentas-alumnos/nueva", data={})
        mismatch = self._create_post(password="Password123!", confirmation="Different123!")
        self.assertEqual(incomplete.status_code, 400)
        self.assertEqual(mismatch.status_code, 400)

    def test_edit_is_preloaded_and_only_email_is_editable(self):
        account = self._create_account()
        self._login()
        body = self.client.get(f'/admin/cuentas-alumnos/{account["usuario_id"]}/editar').get_data(as_text=True)
        self.assertIn(account["correo"], body)
        self.assertIn("Alumno Activo", body)
        self.assertNotIn('name="alumno_id"', body)
        self.assertNotIn('name="rol"', body)
        self.assertNotIn('name="estado"', body)
        self.assertNotIn('name="nombre"', body)

    def test_valid_edit_prg_own_email_and_duplicate_handling(self):
        account = self._create_account()
        self._login()
        own = self.client.post(f'/admin/cuentas-alumnos/{account["usuario_id"]}/editar', data={"correo": "STUDENT@EDUPASS.TEST"})
        self.assertEqual(own.status_code, 302)
        duplicate = self.client.post(f'/admin/cuentas-alumnos/{account["usuario_id"]}/editar', data={"correo": "admin@edupass.test"})
        self.assertEqual(duplicate.status_code, 409)
        updated = self.client.post(f'/admin/cuentas-alumnos/{account["usuario_id"]}/editar', data={"correo": "new@edupass.test"})
        self.assertEqual(updated.status_code, 302)
        result = cuentas_alumno_service.consultar_cuenta_alumno(account["usuario_id"], self.database_path)
        self.assertEqual(result["alumno_id"], account["alumno_id"])
        self.assertEqual(result["rol_nombre"], account["rol_nombre"])
        self.assertEqual(result["usuario_estado"], account["usuario_estado"])

    def test_password_regeneration_shows_temporary_once_and_sets_flag(self):
        account = self._create_account()
        self._login()
        page = self.client.get(f'/admin/cuentas-alumnos/{account["usuario_id"]}/password')
        self.assertEqual(page.status_code, 200)
        secret = "NuevaWebClave123!"
        with patch.object(
            cuentas_alumno_service,
            "generar_password_temporal",
            return_value=secret,
        ):
            response = self.client.post(
                f'/admin/cuentas-alumnos/{account["usuario_id"]}/password',
                data={},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(secret, response.get_data(as_text=True))
        self.assertIn("no-store", response.headers["Cache-Control"])
        connection = database_manager.get_connection(self.database_path)
        try:
            stored, flag = connection.execute("SELECT password_hash, requiere_cambio_password FROM usuarios WHERE usuario_id = ?;", (account["usuario_id"],)).fetchone()
        finally:
            connection.close()
        self.assertTrue(check_password_hash(stored, secret))
        self.assertEqual(flag, 1)

    def test_activate_deactivate_are_post_prg_and_preserve_link(self):
        account = self._create_account()
        self._login()
        deactivate = self.client.post(f'/admin/cuentas-alumnos/{account["usuario_id"]}/desactivar')
        self.assertEqual(deactivate.status_code, 302)
        self.assertEqual(self.client.get(f'/admin/cuentas-alumnos/{account["usuario_id"]}/activar').status_code, 405)
        self.assertEqual(self.client.get(f'/admin/cuentas-alumnos/{account["usuario_id"]}/desactivar').status_code, 405)
        activate = self.client.post(f'/admin/cuentas-alumnos/{account["usuario_id"]}/activar')
        self.assertEqual(activate.status_code, 302)
        self.assertEqual(usuario_alumno_repository.obtener_por_usuario(account["usuario_id"], self.database_path)["usuario_alumno_id"], account["usuario_alumno_id"])

    def test_activation_rejects_inactive_student(self):
        account = self._create_account()
        cuentas_alumno_service.desactivar_cuenta_alumno(account["usuario_id"], self.admin["usuario_id"], self.database_path)
        alumnos_service.desactivar_alumno(self.active_student["alumno_id"], self.database_path)
        self._login()
        response = self.client.post(f'/admin/cuentas-alumnos/{account["usuario_id"]}/activar')
        self.assertEqual(response.status_code, 409)
        self.assertIn("No se puede activar una cuenta para un alumno inactivo.", response.get_data(as_text=True))

    def test_templates_offer_no_delete_unlink_role_or_student_change(self):
        account = self._create_account()
        self._login()
        listing = self.client.get("/admin/cuentas-alumnos").get_data(as_text=True)
        edit = self.client.get(f'/admin/cuentas-alumnos/{account["usuario_id"]}/editar').get_data(as_text=True)
        for body in (listing, edit):
            self.assertNotIn("Eliminar", body)
            self.assertNotIn("Desvincular", body)
            self.assertNotIn('name="rol"', body)
        self.assertNotIn('name="alumno_id"', edit)

    def test_wrong_role_and_missing_targets_return_404(self):
        self._login()
        for target in (self.admin["usuario_id"], self.scanner["usuario_id"], 999999):
            with self.subTest(target=target):
                response = self.client.get(f"/admin/cuentas-alumnos/{target}/editar")
                self.assertEqual(response.status_code, 404)
                self.assertIn("No se encontró la cuenta de alumno solicitada.", response.get_data(as_text=True))

    def test_technical_errors_do_not_expose_internal_details(self):
        self._login()
        for detail in ("SELECT secreto", str(self.database_path), "Traceback privado"):
            with self.subTest(detail=detail), patch.object(cuentas_alumno_service, "listar_cuentas_alumno", side_effect=RepositoryError(detail)):
                response = self.client.get("/admin/cuentas-alumnos")
                body = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn(detail, body)
                self.assertIn("No fue posible completar la operación en este momento.", body)

    def test_html_is_escaped(self):
        alumnos_service.registrar_alumno("<script>alert(1)</script>", "WEB-XSS", "1", "A", None, "activo", self.database_path)
        self._login()
        body = self.client.get("/admin/cuentas-alumnos").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)

    def test_responsive_styles_and_csrf_actions_exist(self):
        css = (SRC_PATH / "edupass" / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
        template = (SRC_PATH / "edupass" / "web" / "templates" / "admin" / "cuentas_alumnos_list.html").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 390px)", css)
        self.assertIn("student-accounts-table", css)
        self.assertIn("estado_form.hidden_tag()", template)
        with self.app.test_request_context("/admin/cuentas-alumnos"):
            self.assertIn('name="csrf_token"', EstadoUsuarioForm(meta={"csrf": True}).hidden_tag())

    def test_student_login_redirects_to_personal_portal(self):
        account = self._create_account()
        response = self._login(account["correo"])
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/alumno"))
        authenticated = usuarios_service.autenticar_usuario(
            account["correo"], self.PASSWORD, self.database_path
        )
        self.assertEqual(authenticated["rol_nombre"], "alumno")

    def test_existing_crud_pages_still_work(self):
        self._login()
        for path in ("/admin/alumnos", "/admin/administradores", "/admin/escaneres"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
