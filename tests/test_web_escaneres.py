from pathlib import Path
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
from edupass.shared.errors import RepositoryError
from edupass.web import create_app
from edupass.web.forms import EscanerCrearForm, EstadoUsuarioForm


class TestWebEscaneres(unittest.TestCase):
    PASSWORD = "ClaveWebEscaner123"
    NEW_PASSWORD = "NuevaClaveEscaner456"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "web_escaneres.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.admin = usuarios_service.crear_administrador(
            "Administradora Principal", "admin@edupass.test",
            self.PASSWORD, self.database_path,
        )
        self.scanner = self._create_scanner(
            "Escaner Principal", "scanner@edupass.test"
        )
        self.other_scanner = self._create_scanner(
            "Escaner Secundario", "scanner2@edupass.test"
        )

    def tearDown(self):
        self.temp.cleanup()

    def _create_scanner(self, name, email, password=None):
        return usuarios_service.crear_escaner(
            name, email, password or self.PASSWORD, self.database_path
        )

    def _login(self, email="admin@edupass.test", password=None):
        return self.client.post("/login", data={
            "correo": email, "password": password or self.PASSWORD
        })

    def _logout(self):
        return self.client.post("/logout")

    def _create_post(self, **changes):
        data = {
            "nombre": "Nuevo Escaner", "correo": "nuevo@edupass.test",
            "password": self.NEW_PASSWORD,
            "confirmar_password": self.NEW_PASSWORD,
        }
        data.update(changes)
        return self.client.post("/admin/escaneres/nuevo", data=data)

    def _edit_post(self, user_id, **changes):
        data = {"nombre": "Escaner Editado", "correo": "editado@edupass.test"}
        data.update(changes)
        return self.client.post(f"/admin/escaneres/{user_id}/editar", data=data)

    def _password_post(self, user_id, password=None, confirmation=None):
        chosen = password or self.NEW_PASSWORD
        return self.client.post(f"/admin/escaneres/{user_id}/password", data={
            "password": chosen, "confirmar_password": confirmation or chosen
        })

    def test_01_visitante_redirigido(self):
        for route in ("/admin/escaneres", "/admin/escaneres/nuevo"):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login", response.headers["Location"])

    def test_02_escaner_recibe_403(self):
        self._login("scanner@edupass.test")
        self.assertEqual(self.client.get("/admin/escaneres").status_code, 403)

    def test_03_administrador_accede_listado(self):
        self._login()
        response = self.client.get("/admin/escaneres")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Personal de escaneo", response.get_data(as_text=True))

    def test_04_navegacion_contiene_escaneres(self):
        self._login()
        body = self.client.get("/admin").get_data(as_text=True)
        self.assertIn('href="/admin/escaneres"', body)
        self.assertIn("Escáneres", body)

    def test_05_panel_contiene_personal_escaneo(self):
        self._login()
        body = self.client.get("/admin").get_data(as_text=True)
        self.assertIn("Personal de escaneo", body)
        self.assertIn("Administrar escáneres", body)

    def test_06_listado_muestra_solo_escaneres(self):
        self._login()
        body = self.client.get("/admin/escaneres").get_data(as_text=True)
        self.assertIn("Escaner Principal", body)
        self.assertIn("Escaner Secundario", body)

    def test_07_listado_no_muestra_administradores(self):
        self._login()
        body = self.client.get("/admin/escaneres").get_data(as_text=True)
        self.assertNotIn("Administradora Principal", body)
        self.assertNotIn("admin@edupass.test", body)

    def test_08_listado_no_muestra_hash(self):
        self._login()
        body = self.client.get("/admin/escaneres").get_data(as_text=True)
        saved = usuario_repository.obtener_por_id(
            self.scanner["usuario_id"], self.database_path
        )["password_hash"]
        self.assertNotIn("password_hash", body)
        self.assertNotIn(saved, body)

    def test_09_formulario_alta(self):
        self._login()
        body = self.client.get("/admin/escaneres/nuevo").get_data(as_text=True)
        for field in ("nombre", "correo", "password", "confirmar_password"):
            self.assertIn(f'name="{field}"', body)

    def test_10_csrf_presente(self):
        csrf_app = create_app({
            "TESTING": True, "SECRET_KEY": "csrf-secret",
            "DATABASE_PATH": self.database_path, "WTF_CSRF_ENABLED": True,
        })
        with csrf_app.test_request_context("/admin/escaneres/nuevo"):
            html = EscanerCrearForm().hidden_tag()
        self.assertIn('name="csrf_token"', html)

    def test_11_alta_valida(self):
        self._login()
        self.assertEqual(self._create_post().status_code, 302)
        self.assertIsNotNone(usuario_repository.obtener_por_correo(
            "nuevo@edupass.test", self.database_path
        ))

    def test_12_cuenta_creada_activa(self):
        self._login(); self._create_post()
        row = usuario_repository.obtener_por_correo("nuevo@edupass.test", self.database_path)
        self.assertEqual(row["estado"], "activo")

    def test_13_rol_escaner_fijado(self):
        self._login(); self._create_post(rol="administrador")
        row = usuario_repository.obtener_por_correo("nuevo@edupass.test", self.database_path)
        self.assertEqual(row["rol_nombre"], "escaner")

    def test_14_correo_normalizado(self):
        self._login(); self._create_post(correo="  NUEVO@EDUPASS.TEST  ")
        self.assertIsNotNone(usuario_repository.obtener_por_correo(
            "nuevo@edupass.test", self.database_path
        ))

    def test_15_correo_duplicado(self):
        self._login()
        response = self._create_post(correo="scanner@edupass.test")
        self.assertEqual(response.status_code, 409)

    def test_16_correo_de_administrador_rechazado(self):
        self._login()
        response = self._create_post(correo="admin@edupass.test")
        self.assertEqual(response.status_code, 409)

    def test_17_formulario_incompleto(self):
        self._login()
        response = self._create_post(nombre="")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Revisa los datos obligatorios", response.get_data(as_text=True))

    def test_18_confirmacion_incorrecta(self):
        self._login()
        self.assertEqual(self._create_post(
            confirmar_password="NoCoincide123").status_code, 400)

    def test_19_post_redirect_get(self):
        self._login(); response = self._create_post()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/escaneres"))
        self.assertIn("Escáner registrado correctamente.", self.client.get(
            response.headers["Location"]).get_data(as_text=True))

    def test_20_edicion_precargada(self):
        self._login()
        body = self.client.get(f"/admin/escaneres/{self.scanner['usuario_id']}/editar").get_data(as_text=True)
        self.assertIn("Escaner Principal", body)
        self.assertIn("scanner@edupass.test", body)

    def test_21_edicion_valida(self):
        self._login(); response = self._edit_post(self.scanner["usuario_id"])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(usuario_repository.obtener_por_id(
            self.scanner["usuario_id"], self.database_path)["nombre"], "Escaner Editado")

    def test_22_correo_propio_permitido(self):
        self._login()
        response = self._edit_post(
            self.scanner["usuario_id"], correo="SCANNER@EDUPASS.TEST")
        self.assertEqual(response.status_code, 302)

    def test_23_correo_otro_usuario_rechazado(self):
        self._login()
        response = self._edit_post(
            self.scanner["usuario_id"], correo="scanner2@edupass.test")
        self.assertEqual(response.status_code, 409)

    def test_24_estado_conservado_al_editar(self):
        usuarios_service.desactivar_escaner(
            self.scanner["usuario_id"], self.admin["usuario_id"], self.database_path)
        self._login(); self._edit_post(self.scanner["usuario_id"])
        self.assertEqual(usuario_repository.obtener_por_id(
            self.scanner["usuario_id"], self.database_path)["estado"], "inactivo")

    def test_25_rol_conservado_al_editar(self):
        self._login(); self._edit_post(self.scanner["usuario_id"], rol="administrador")
        self.assertEqual(usuario_repository.obtener_por_id(
            self.scanner["usuario_id"], self.database_path)["rol_nombre"], "escaner")

    def test_26_password_conservado_al_editar(self):
        before = usuario_repository.obtener_por_id(
            self.scanner["usuario_id"], self.database_path)["password_hash"]
        self._login(); self._edit_post(self.scanner["usuario_id"], password="Manipulada123")
        after = usuario_repository.obtener_por_id(
            self.scanner["usuario_id"], self.database_path)["password_hash"]
        self.assertEqual(after, before)

    def test_27_restablecimiento_password(self):
        self._login(); response = self._password_post(self.scanner["usuario_id"])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(usuarios_service.autenticar_usuario(
            "scanner@edupass.test", self.NEW_PASSWORD, self.database_path)["usuario_id"],
            self.scanner["usuario_id"])

    def test_28_password_nunca_aparece(self):
        self._login()
        response = self._password_post(
            self.scanner["usuario_id"], confirmation="NoCoincide123")
        body = response.get_data(as_text=True)
        self.assertNotIn(self.NEW_PASSWORD, body)
        self.assertNotIn("NoCoincide123", body)

    def test_29_activacion_valida(self):
        usuarios_service.desactivar_escaner(
            self.scanner["usuario_id"], self.admin["usuario_id"], self.database_path)
        self._login(); response = self.client.post(
            f"/admin/escaneres/{self.scanner['usuario_id']}/activar")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(usuario_repository.obtener_por_id(
            self.scanner["usuario_id"], self.database_path)["estado"], "activo")

    def test_30_desactivacion_valida(self):
        self._login(); response = self.client.post(
            f"/admin/escaneres/{self.scanner['usuario_id']}/desactivar")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(usuario_repository.obtener_por_id(
            self.scanner["usuario_id"], self.database_path)["estado"], "inactivo")

    def test_31_administrador_objetivo_404(self):
        self._login()
        self.assertEqual(self.client.get(
            f"/admin/escaneres/{self.admin['usuario_id']}/editar").status_code, 404)

    def test_32_usuario_inexistente_404(self):
        self._login()
        self.assertEqual(self.client.get("/admin/escaneres/99999/editar").status_code, 404)

    def test_33_get_activar_405(self):
        self._login()
        self.assertEqual(self.client.get(
            f"/admin/escaneres/{self.scanner['usuario_id']}/activar").status_code, 405)

    def test_34_get_desactivar_405(self):
        self._login()
        self.assertEqual(self.client.get(
            f"/admin/escaneres/{self.scanner['usuario_id']}/desactivar").status_code, 405)

    def test_35_sin_boton_eliminar(self):
        self._login(); body = self.client.get("/admin/escaneres").get_data(as_text=True)
        self.assertNotIn("Eliminar", body)
        self.assertNotIn("DELETE", body)

    def test_36_sin_selector_rol(self):
        self._login(); body = self.client.get("/admin/escaneres/nuevo").get_data(as_text=True)
        self.assertNotIn('name="rol"', body)
        self.assertNotIn("<select", body)

    def test_37_error_repositorio_controlado(self):
        self._login()
        with patch.object(usuarios_service, "listar_escaneres",
                          side_effect=RepositoryError("detalle secreto")):
            response = self.client.get("/admin/escaneres")
        self.assertEqual(response.status_code, 500)
        self.assertIn("No fue posible completar la operación", response.get_data(as_text=True))

    def test_38_sql_no_expuesto(self):
        self._login()
        with patch.object(usuarios_service, "listar_escaneres",
                          side_effect=RepositoryError("SELECT * FROM usuarios")):
            body = self.client.get("/admin/escaneres").get_data(as_text=True)
        self.assertNotIn("SELECT", body)

    def test_39_ruta_sqlite_no_expuesta(self):
        self._login()
        with patch.object(usuarios_service, "listar_escaneres",
                          side_effect=RepositoryError(str(self.database_path))):
            body = self.client.get("/admin/escaneres").get_data(as_text=True)
        self.assertNotIn(str(self.database_path), body)

    def test_40_traceback_no_expuesto(self):
        self._login()
        with patch.object(usuarios_service, "listar_escaneres",
                          side_effect=RepositoryError("Traceback secreto")):
            body = self.client.get("/admin/escaneres").get_data(as_text=True)
        self.assertNotIn("Traceback", body)

    def test_41_hash_no_expuesto(self):
        self._login(); body = self.client.get(
            f"/admin/escaneres/{self.scanner['usuario_id']}/password").get_data(as_text=True)
        saved = usuario_repository.obtener_por_id(
            self.scanner["usuario_id"], self.database_path)["password_hash"]
        self.assertNotIn(saved, body)
        self.assertNotIn("password_hash", body)

    def test_42_escape_html(self):
        self._create_scanner("<script>alert(1)</script>", "escape@edupass.test")
        self._login(); body = self.client.get("/admin/escaneres").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)

    def test_43_vista_responsive(self):
        self._login(); body = self.client.get("/admin/escaneres").get_data(as_text=True)
        css = (SRC_PATH / "edupass" / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
        self.assertIn('name="viewport"', body)
        self.assertIn("@media (max-width: 390px)", css)
        self.assertIn("table-scroll", body)

    def test_44_acciones_csrf(self):
        with self.app.test_request_context("/admin/escaneres"):
            html = EstadoUsuarioForm(meta={"csrf": True}).hidden_tag()
        self.assertIn('name="csrf_token"', html)
        template = (SRC_PATH / "edupass" / "web" / "templates" / "admin" /
                    "escaneres_list.html").read_text(encoding="utf-8")
        self.assertIn("estado_form.hidden_tag()", template)

    def test_45_desactivado_no_inicia_sesion(self):
        self._login(); self.client.post(
            f"/admin/escaneres/{self.scanner['usuario_id']}/desactivar"); self._logout()
        response = self._login("scanner@edupass.test")
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)

    def test_46_reactivado_vuelve_a_iniciar_sesion(self):
        usuarios_service.desactivar_escaner(
            self.scanner["usuario_id"], self.admin["usuario_id"], self.database_path)
        usuarios_service.activar_escaner(
            self.scanner["usuario_id"], self.admin["usuario_id"], self.database_path)
        self.assertEqual(self._login("scanner@edupass.test").status_code, 302)
        self.assertEqual(self.client.get("/scanner").status_code, 200)

    def test_47_movimientos_historicos_conservados(self):
        connection = sqlite3.connect(self.database_path)
        try:
            alumno = connection.execute(
                "INSERT INTO alumnos (nombre, matricula, grado, grupo, estado) VALUES (?, ?, ?, ?, ?);",
                ("Alumno", "MAT-W13-S", "1", "A", "activo"),
            ).lastrowid
            connection.execute(
                "INSERT INTO movimientos (alumno_id, tipo_movimiento, fecha_hora, usuario_id) VALUES (?, ?, ?, ?);",
                (alumno, "entrada", "2026-07-31T18:00:00", self.scanner["usuario_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        self._login(); self.client.post(
            f"/admin/escaneres/{self.scanner['usuario_id']}/desactivar")
        connection = sqlite3.connect(self.database_path)
        try:
            total = connection.execute(
                "SELECT COUNT(*) FROM movimientos WHERE usuario_id = ?;",
                (self.scanner["usuario_id"],),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(total, 1)

    def test_48_no_borrado_fisico(self):
        before = len(usuarios_service.listar_escaneres(self.database_path))
        self._login(); response = self.client.open(
            f"/admin/escaneres/{self.scanner['usuario_id']}", method="DELETE")
        self.assertIn(response.status_code, (404, 405))
        self.assertEqual(len(usuarios_service.listar_escaneres(self.database_path)), before)

    def test_49_escaner_no_puede_administrar_cuentas(self):
        self._login("scanner@edupass.test")
        routes = (
            "/admin/escaneres", "/admin/escaneres/nuevo",
            f"/admin/escaneres/{self.other_scanner['usuario_id']}/editar",
            f"/admin/escaneres/{self.other_scanner['usuario_id']}/password",
        )
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 403)

    def test_50_crud_administradores_sigue_funcionando(self):
        self._login()
        self.assertEqual(self.client.get("/admin/administradores").status_code, 200)
        response = self.client.post("/admin/administradores/nuevo", data={
            "nombre": "Segundo Admin", "correo": "admin2@edupass.test",
            "password": self.NEW_PASSWORD, "confirmar_password": self.NEW_PASSWORD,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(usuario_repository.obtener_por_correo(
            "admin2@edupass.test", self.database_path)["rol_nombre"], "administrador")


if __name__ == "__main__":
    unittest.main()