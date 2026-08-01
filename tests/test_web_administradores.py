from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.auth import usuarios_service
from edupass.persistence.repositories import usuario_repository
from edupass.shared.errors import (
    RepositoryError,
    UltimoAdministradorActivoError,
)
from edupass.web import create_app
from edupass.web.forms import AdministradorCrearForm, EstadoUsuarioForm


class TestWebAdministradores(unittest.TestCase):
    PASSWORD = "ClaveWebAdministrativa123"
    NEW_PASSWORD = "NuevaClaveWeb456"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "web_admins.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.primary = self._create_admin(
            "Administradora Principal", "principal@edupass.test"
        )
        self.secondary = self._create_admin(
            "Administrador Secundario", "secundario@edupass.test"
        )
        self.scanner = usuarios_service.crear_usuario_demo(
            "Escaner Interno", "scanner@edupass.test", self.PASSWORD,
            "escaner", self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _create_admin(self, name, email, password=None):
        return usuarios_service.crear_administrador(
            name, email, password or self.PASSWORD, self.database_path
        )

    def _login(self, email="principal@edupass.test", password=None):
        return self.client.post("/login", data={
            "correo": email,
            "password": password or self.PASSWORD,
        })

    def _logout(self):
        return self.client.post("/logout")

    def _create_post(self, **changes):
        data = {
            "nombre": "Nueva Administradora",
            "correo": "nueva@edupass.test",
            "password": self.NEW_PASSWORD,
            "confirmar_password": self.NEW_PASSWORD,
        }
        data.update(changes)
        return self.client.post("/admin/administradores/nuevo", data=data)

    def _edit_post(self, user_id, **changes):
        data = {"nombre": "Nombre Editado", "correo": "editado@edupass.test"}
        data.update(changes)
        return self.client.post(
            f"/admin/administradores/{user_id}/editar", data=data
        )

    def _password_post(self, user_id, password=None, confirmation=None):
        chosen = password or self.NEW_PASSWORD
        return self.client.post(
            f"/admin/administradores/{user_id}/password",
            data={
                "password": chosen,
                "confirmar_password": confirmation or chosen,
            },
        )

    def test_01_visitor_is_redirected(self):
        for route in ("/admin/administradores", "/admin/administradores/nuevo"):
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_02_scanner_receives_403(self):
        self._login("scanner@edupass.test")
        self.assertEqual(self.client.get("/admin/administradores").status_code, 403)

    def test_03_admin_accesses_listing(self):
        self._login()
        response = self.client.get("/admin/administradores")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Administradores", response.get_data(as_text=True))

    def test_04_navigation_contains_administrators(self):
        self._login()
        body = self.client.get("/admin").get_data(as_text=True)
        self.assertIn('href="/admin/administradores"', body)

    def test_05_dashboard_contains_administrators_card(self):
        self._login()
        body = self.client.get("/admin").get_data(as_text=True)
        self.assertIn("Gestiona las cuentas administrativas y su estado.", body)
        self.assertIn("Administrar cuentas", body)

    def test_06_listing_shows_only_administrators(self):
        self._login()
        body = self.client.get("/admin/administradores").get_data(as_text=True)
        self.assertIn("Administradora Principal", body)
        self.assertIn("Administrador Secundario", body)

    def test_07_listing_does_not_show_scanners(self):
        self._login()
        body = self.client.get("/admin/administradores").get_data(as_text=True)
        self.assertNotIn("Escaner Interno", body)
        self.assertNotIn("scanner@edupass.test", body)

    def test_08_listing_does_not_show_password_hash(self):
        self._login()
        body = self.client.get("/admin/administradores").get_data(as_text=True)
        internal = usuario_repository.obtener_por_id(
            self.primary["usuario_id"], self.database_path
        )
        self.assertNotIn("password_hash", body)
        self.assertNotIn(internal["password_hash"], body)

    def test_09_create_form_is_available(self):
        self._login()
        body = self.client.get("/admin/administradores/nuevo").get_data(as_text=True)
        for field in ('name="nombre"', 'name="correo"', 'name="password"',
                      'name="confirmar_password"'):
            self.assertIn(field, body)

    def test_10_csrf_is_present_when_enabled(self):
        csrf_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "csrf-test-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": True,
        })
        with csrf_app.test_request_context("/admin/administradores/nuevo"):
            html = AdministradorCrearForm().hidden_tag()
        self.assertIn('name="csrf_token"', html)

    def test_11_valid_create(self):
        self._login()
        response = self._create_post()
        self.assertEqual(response.status_code, 302)
        created = usuarios_service.autenticar_usuario(
            "nueva@edupass.test", self.NEW_PASSWORD, self.database_path
        )
        self.assertEqual(created["nombre"], "Nueva Administradora")

    def test_12_created_account_is_active(self):
        self._login()
        self._create_post()
        created = usuario_repository.obtener_por_correo(
            "nueva@edupass.test", self.database_path
        )
        self.assertEqual(created["estado"], "activo")

    def test_13_created_role_is_administrator(self):
        self._login()
        self._create_post(rol="escaner")
        created = usuario_repository.obtener_por_correo(
            "nueva@edupass.test", self.database_path
        )
        self.assertEqual(created["rol_nombre"], "administrador")

    def test_14_created_email_is_normalized(self):
        self._login()
        self._create_post(correo="  NUEVA@EDUPASS.TEST  ")
        self.assertIsNotNone(usuario_repository.obtener_por_correo(
            "nueva@edupass.test", self.database_path
        ))

    def test_15_duplicate_email_returns_409(self):
        self._login()
        response = self._create_post(correo="principal@edupass.test")
        self.assertEqual(response.status_code, 409)
        self.assertIn("El correo ya está registrado.", response.get_data(as_text=True))

    def test_16_incomplete_form_returns_400(self):
        self._login()
        response = self._create_post(nombre="")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Revisa los datos obligatorios", response.get_data(as_text=True))

    def test_17_password_confirmation_mismatch_returns_400(self):
        self._login()
        response = self._create_post(confirmar_password="NoCoincide123")
        self.assertEqual(response.status_code, 400)

    def test_18_create_uses_post_redirect_get(self):
        self._login()
        response = self._create_post()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/administradores"))
        body = self.client.get(response.headers["Location"]).get_data(as_text=True)
        self.assertIn("Administrador registrado correctamente.", body)

    def test_19_edit_form_is_prefilled(self):
        self._login()
        body = self.client.get(
            f"/admin/administradores/{self.secondary['usuario_id']}/editar"
        ).get_data(as_text=True)
        self.assertIn("Administrador Secundario", body)
        self.assertIn("secundario@edupass.test", body)

    def test_20_valid_edit(self):
        self._login()
        response = self._edit_post(self.secondary["usuario_id"])
        self.assertEqual(response.status_code, 302)
        updated = usuario_repository.obtener_por_id(
            self.secondary["usuario_id"], self.database_path
        )
        self.assertEqual(updated["nombre"], "Nombre Editado")

    def test_21_own_email_is_allowed(self):
        self._login()
        response = self._edit_post(
            self.secondary["usuario_id"], correo="SECUNDARIO@EDUPASS.TEST"
        )
        self.assertEqual(response.status_code, 302)

    def test_22_other_users_email_is_rejected(self):
        self._login()
        response = self._edit_post(
            self.secondary["usuario_id"], correo="principal@edupass.test"
        )
        self.assertEqual(response.status_code, 409)

    def test_23_edit_preserves_status(self):
        usuarios_service.desactivar_administrador(
            self.secondary["usuario_id"], self.primary["usuario_id"], self.database_path
        )
        self._login()
        self._edit_post(self.secondary["usuario_id"])
        updated = usuario_repository.obtener_por_id(
            self.secondary["usuario_id"], self.database_path
        )
        self.assertEqual(updated["estado"], "inactivo")

    def test_24_edit_preserves_role(self):
        self._login()
        self._edit_post(self.secondary["usuario_id"], rol="escaner")
        updated = usuario_repository.obtener_por_id(
            self.secondary["usuario_id"], self.database_path
        )
        self.assertEqual(updated["rol_nombre"], "administrador")

    def test_25_edit_preserves_password(self):
        before = usuario_repository.obtener_por_id(
            self.secondary["usuario_id"], self.database_path
        )["password_hash"]
        self._login()
        self._edit_post(self.secondary["usuario_id"], password="Manipulada123")
        after = usuario_repository.obtener_por_id(
            self.secondary["usuario_id"], self.database_path
        )["password_hash"]
        self.assertEqual(after, before)

    def test_26_reset_password(self):
        self._login()
        response = self._password_post(self.secondary["usuario_id"])
        self.assertEqual(response.status_code, 302)
        self._logout()
        authenticated = usuarios_service.autenticar_usuario(
            "secundario@edupass.test", self.NEW_PASSWORD, self.database_path
        )
        self.assertEqual(authenticated["usuario_id"], self.secondary["usuario_id"])

    def test_27_password_never_appears_in_response(self):
        self._login()
        response = self._password_post(
            self.secondary["usuario_id"], confirmation="NoCoincide123"
        )
        body = response.get_data(as_text=True)
        self.assertNotIn(self.NEW_PASSWORD, body)
        self.assertNotIn("NoCoincide123", body)

    def test_28_self_password_reset_logs_out(self):
        self._login()
        response = self._password_post(self.primary["usuario_id"])
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        protected = self.client.get("/admin/administradores")
        self.assertEqual(protected.status_code, 302)

    def test_29_valid_activation(self):
        usuarios_service.desactivar_administrador(
            self.secondary["usuario_id"], self.primary["usuario_id"], self.database_path
        )
        self._login()
        response = self.client.post(
            f"/admin/administradores/{self.secondary['usuario_id']}/activar"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(usuario_repository.obtener_por_id(
            self.secondary["usuario_id"], self.database_path)["estado"], "activo")

    def test_30_valid_deactivation(self):
        self._login()
        response = self.client.post(
            f"/admin/administradores/{self.secondary['usuario_id']}/desactivar"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(usuario_repository.obtener_por_id(
            self.secondary["usuario_id"], self.database_path)["estado"], "inactivo")

    def test_31_self_deactivation_is_rejected(self):
        self._login()
        response = self.client.post(
            f"/admin/administradores/{self.primary['usuario_id']}/desactivar"
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("No puedes desactivar tu propia cuenta.", response.get_data(as_text=True))

    def test_32_last_active_administrator_is_rejected(self):
        self._login()
        with patch.object(
            usuarios_service, "desactivar_administrador",
            side_effect=UltimoAdministradorActivoError("controlado"),
        ):
            response = self.client.post(
                f"/admin/administradores/{self.secondary['usuario_id']}/desactivar"
            )
        self.assertEqual(response.status_code, 409)
        self.assertIn("último administrador activo", response.get_data(as_text=True))

    def test_33_two_administrators_allow_deactivating_one(self):
        self._login()
        self.client.post(
            f"/admin/administradores/{self.secondary['usuario_id']}/desactivar"
        )
        self.assertEqual(usuario_repository.contar_activos_por_rol(
            "administrador", self.database_path), 1)

    def test_34_unknown_user_returns_404(self):
        self._login()
        self.assertEqual(self.client.get(
            "/admin/administradores/99999/editar").status_code, 404)

    def test_35_scanner_as_target_returns_404(self):
        self._login()
        self.assertEqual(self.client.get(
            f"/admin/administradores/{self.scanner['usuario_id']}/editar"
        ).status_code, 404)

    def test_36_get_activate_returns_405(self):
        self._login()
        self.assertEqual(self.client.get(
            f"/admin/administradores/{self.secondary['usuario_id']}/activar"
        ).status_code, 405)

    def test_37_get_deactivate_returns_405(self):
        self._login()
        self.assertEqual(self.client.get(
            f"/admin/administradores/{self.secondary['usuario_id']}/desactivar"
        ).status_code, 405)

    def test_38_delete_button_does_not_exist(self):
        self._login()
        body = self.client.get("/admin/administradores").get_data(as_text=True)
        self.assertNotIn("Eliminar", body)
        self.assertNotIn("DELETE", body)

    def test_39_role_selector_does_not_exist(self):
        self._login()
        body = self.client.get("/admin/administradores/nuevo").get_data(as_text=True)
        self.assertNotIn('name="rol"', body)
        self.assertNotIn("<select", body)

    def test_40_repository_error_is_controlled(self):
        self._login()
        with patch.object(
            usuarios_service, "listar_administradores",
            side_effect=RepositoryError("SELECT secreto FROM usuarios"),
        ):
            response = self.client.get("/admin/administradores")
        self.assertEqual(response.status_code, 500)
        self.assertIn("No fue posible completar la operación", response.get_data(as_text=True))

    def test_41_sql_is_not_exposed(self):
        self._login()
        with patch.object(usuarios_service, "listar_administradores",
                          side_effect=RepositoryError("SELECT * FROM usuarios")):
            body = self.client.get("/admin/administradores").get_data(as_text=True)
        self.assertNotIn("SELECT", body)

    def test_42_sqlite_path_is_not_exposed(self):
        self._login()
        with patch.object(usuarios_service, "listar_administradores",
                          side_effect=RepositoryError(str(self.database_path))):
            body = self.client.get("/admin/administradores").get_data(as_text=True)
        self.assertNotIn(str(self.database_path), body)

    def test_43_traceback_is_not_exposed(self):
        self._login()
        with patch.object(usuarios_service, "listar_administradores",
                          side_effect=RepositoryError("Traceback secreto")):
            body = self.client.get("/admin/administradores").get_data(as_text=True)
        self.assertNotIn("Traceback", body)

    def test_44_hash_is_not_exposed_in_forms(self):
        self._login()
        body = self.client.get(
            f"/admin/administradores/{self.secondary['usuario_id']}/password"
        ).get_data(as_text=True)
        saved_hash = usuario_repository.obtener_por_id(
            self.secondary["usuario_id"], self.database_path)["password_hash"]
        self.assertNotIn(saved_hash, body)
        self.assertNotIn("password_hash", body)

    def test_45_html_is_escaped(self):
        self._create_admin("<script>alert(1)</script>", "escape@edupass.test")
        self._login()
        body = self.client.get("/admin/administradores").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)

    def test_46_responsive_viewport_and_css(self):
        self._login()
        body = self.client.get("/admin/administradores").get_data(as_text=True)
        css = (SRC_PATH / "edupass" / "web" / "static" / "css" / "app.css").read_text(
            encoding="utf-8"
        )
        self.assertIn('name="viewport"', body)
        self.assertIn("@media (max-width: 390px)", css)
        self.assertIn("table-scroll", body)

    def test_47_state_actions_use_csrf_capable_forms(self):
        with self.app.test_request_context("/admin/administradores"):
            html = EstadoUsuarioForm(meta={"csrf": True}).hidden_tag()
        self.assertIn('name="csrf_token"', html)
        template = (SRC_PATH / "edupass" / "web" / "templates" / "admin" /
                    "administradores_list.html").read_text(encoding="utf-8")
        self.assertIn("estado_form.hidden_tag()", template)

    def test_48_inactive_administrator_cannot_login(self):
        self._login()
        self.client.post(
            f"/admin/administradores/{self.secondary['usuario_id']}/desactivar"
        )
        self._logout()
        response = self._login("secundario@edupass.test")
        self.assertEqual(response.status_code, 200)
        self.assertIn("No fue posible iniciar sesion", response.get_data(as_text=True))
        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)

    def test_49_historical_movements_are_preserved(self):
        connection = sqlite3.connect(self.database_path)
        try:
            alumno_id = connection.execute(
                "INSERT INTO alumnos (nombre, matricula, grado, grupo, estado) "
                "VALUES (?, ?, ?, ?, ?);",
                ("Alumno", "MAT-W13", "1", "A", "activo"),
            ).lastrowid
            connection.execute(
                "INSERT INTO movimientos "
                "(alumno_id, tipo_movimiento, fecha_hora, usuario_id) "
                "VALUES (?, ?, ?, ?);",
                (alumno_id, "entrada", "2026-07-31T12:00:00", self.secondary["usuario_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        self._login()
        self.client.post(
            f"/admin/administradores/{self.secondary['usuario_id']}/desactivar"
        )
        connection = sqlite3.connect(self.database_path)
        try:
            total = connection.execute(
                "SELECT COUNT(*) FROM movimientos WHERE usuario_id = ?;",
                (self.secondary["usuario_id"],),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(total, 1)

    def test_50_no_physical_delete_exists(self):
        before = len(usuarios_service.listar_administradores(self.database_path))
        self._login()
        response = self.client.open(
            f"/admin/administradores/{self.secondary['usuario_id']}",
            method="DELETE",
        )
        after = len(usuarios_service.listar_administradores(self.database_path))
        self.assertIn(response.status_code, (404, 405))
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()