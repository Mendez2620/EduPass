from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumno_portal_service, alumnos_service, cuentas_alumno_service
from edupass.modules.auth import roles_service, usuarios_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import usuario_repository
from edupass.shared.errors import RepositoryError
from edupass.web import create_app


class TestWebAlumnoPortal(unittest.TestCase):
    PASSWORD = "Password123!"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "web_portal.sqlite"
        self.app = create_app({"TESTING": True, "SECRET_KEY": "portal-test", "DATABASE_PATH": self.database_path, "WTF_CSRF_ENABLED": False})
        self.client = self.app.test_client()
        self.admin = usuarios_service.crear_usuario_demo("Admin", "admin@edupass.test", self.PASSWORD, "administrador", self.database_path)
        self.scanner = usuarios_service.crear_usuario_demo("Scanner", "scanner@edupass.test", self.PASSWORD, "escaner", self.database_path)
        self.student = alumnos_service.registrar_alumno("Alumno Uno", "WEB-PORTAL-001", "3", "A", "C:/privado/foto.png", "activo", self.database_path)
        self.other = alumnos_service.registrar_alumno("Alumno Dos", "WEB-PORTAL-002", "4", "B", None, "activo", self.database_path)
        self.account = cuentas_alumno_service.crear_cuenta_alumno(self.student["alumno_id"], "student@edupass.test", self.PASSWORD, self.admin["usuario_id"], self.database_path)

    def tearDown(self):
        self.temp.cleanup()

    def _login(self, email="student@edupass.test", password=None):
        return self.client.post("/login", data={"correo": email, "password": password or self.PASSWORD})

    def _movement(self, student_id=None, minute=0):
        connection = database_manager.get_connection(self.database_path)
        try:
            cursor = connection.execute(
                "INSERT INTO movimientos (alumno_id, tipo_movimiento, fecha_hora, area_id, punto_plantel, usuario_id, dispositivo_id) VALUES (?, 'entrada', ?, NULL, 'acceso_principal', ?, NULL)",
                (student_id or self.student["alumno_id"], f"2026-07-31T18:{minute:02d}:00.000000Z", self.scanner["usuario_id"]),
            )
            connection.commit()
            return int(cursor.lastrowid)
        finally:
            connection.close()

    def _assert_security_headers(self, response, credential=False):
        self.assertEqual(response.headers["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
        if credential:
            self.assertEqual(response.headers["Content-Security-Policy"], "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'")

    def test_visitante_es_redirigido_de_todas_las_rutas(self):
        for method, path in (("get", "/alumno"), ("get", "/alumno/credencial"), ("post", "/alumno/credencial/generar"), ("post", "/alumno/credencial/renovar"), ("get", "/alumno/historial"), ("get", "/alumno/historial/movimientos/1")):
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_admin_y_escaner_reciben_403(self):
        for email in ("admin@edupass.test", "scanner@edupass.test"):
            with self.subTest(email=email):
                self._login(email)
                self.assertEqual(self.client.get("/alumno").status_code, 403)
                self.client.post("/logout")

    def test_login_alumno_y_raiz_redirigen_al_panel(self):
        login = self._login()
        self.assertEqual(login.status_code, 302)
        self.assertTrue(login.headers["Location"].endswith("/alumno"))
        root = self.client.get("/")
        self.assertTrue(root.headers["Location"].endswith("/alumno"))

    def test_panel_muestra_solo_datos_propios_y_solo_lectura(self):
        self._login()
        response = self.client.get("/alumno")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        for value in ("Mi panel", "Alumno Uno", "WEB-PORTAL-001", "3", "A", "student@edupass.test", "solo lectura", "/alumno/credencial", "/alumno/historial"):
            self.assertIn(value, body)
        self.assertNotIn("Alumno Dos", body)
        self.assertNotIn("WEB-PORTAL-002", body)
        for forbidden in ("password_hash", "fotografia", "C:/privado/foto.png", "rol_id"):
            self.assertNotIn(forbidden, body)
        self._assert_security_headers(response)

    def test_navegacion_es_exclusiva_del_alumno(self):
        self._login()
        body = self.client.get("/alumno").get_data(as_text=True)
        for value in ("Mi panel", "Mi credencial", "Mi historial", "Cerrar sesi"):
            self.assertIn(value, body)
        for forbidden in ("Administracion", "/admin/alumnos", "/admin/administradores", "/admin/escaneres", "/admin/cuentas-alumnos", "Escaneo", "/scanner"):
            self.assertNotIn(forbidden, body)

    def test_credencial_get_formulario_csrf_y_metodos(self):
        self._login()
        response = self.client.get("/alumno/credencial")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("vigencia de 30 segundos", body)
        self.assertIn('method="post"', body)
        self.assertIn("/alumno/credencial/generar", body)
        template = (SRC_PATH / "edupass" / "web" / "templates" / "alumno" / "credencial.html").read_text(encoding="utf-8")
        self.assertIn("generar_form.hidden_tag()", template)
        self.assertIn("renovar_form.hidden_tag()", template)
        self.assertEqual(self.client.get("/alumno/credencial/generar").status_code, 405)
        self._assert_security_headers(response, credential=True)

    def test_generacion_renderiza_svg_sin_exponer_token(self):
        self._login()
        token = "T" * 43
        generated = {"alumno_id": self.student["alumno_id"], "token": token, "matricula_enmascarada": "********L-001", "generado_en": "2026-07-31T18:00:00.000000Z", "expira_en": "2026-07-31T18:00:30.000000Z", "vigencia_segundos": 30, "estado": "activo"}
        with patch.object(alumno_portal_service, "generar_credencial_propia", return_value=generated):
            response = self.client.post("/alumno/credencial/generar", data={"alumno_id": self.other["alumno_id"]})
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("data:image/svg+xml;base64,", body)
        self.assertNotIn(token, body)
        self.assertNotIn(token, response.request.url)
        self.assertNotIn("token=", response.request.url)
        self.assertNotIn(token, " ".join(response.headers.values()))
        with self.client.session_transaction() as session:
            self.assertNotIn(token, repr(dict(session)))
        self._assert_security_headers(response, credential=True)

    def test_renovacion_invalida_token_anterior(self):
        self._login()
        first = self.client.post("/alumno/credencial/generar")
        second = self.client.post("/alumno/credencial/renovar")
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        connection = database_manager.get_connection(self.database_path)
        try:
            states = [row[0] for row in connection.execute("SELECT estado FROM qr_tokens ORDER BY qr_id")]
        finally:
            connection.close()
        self.assertEqual(states, ["invalidado", "activo"])

    def test_historial_vacio_y_sin_selector(self):
        self._login()
        response = self.client.get("/alumno/historial")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("No hay movimientos registrados en tu historial.", body)
        self.assertNotIn("select", body.lower())
        self.assertNotIn('name="alumno_id"', body)
        self._assert_security_headers(response)

    def test_historial_propio_orden_detalle_y_aislamiento(self):
        own_old = self._movement(minute=1)
        own_new = self._movement(minute=2)
        foreign = self._movement(self.other["alumno_id"], minute=3)
        self._login()
        body = self.client.get(f"/alumno/historial?alumno_id={self.other['alumno_id']}").get_data(as_text=True)
        self.assertIn("WEB-PORTAL-001", body)
        self.assertNotIn("WEB-PORTAL-002", body)
        self.assertLess(body.index("2026-07-31T18:02:00.000000Z"), body.index("2026-07-31T18:01:00.000000Z"))
        detail = self.client.get(f"/alumno/historial/movimientos/{own_new}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("WEB-PORTAL-001", detail.get_data(as_text=True))
        for movement_id in (foreign, 999999):
            hidden = self.client.get(f"/alumno/historial/movimientos/{movement_id}")
            self.assertEqual(hidden.status_code, 404)
            self.assertIn("No se encontr", hidden.get_data(as_text=True))
            self.assertNotIn("Alumno Dos", hidden.get_data(as_text=True))

    def test_historial_paginacion_e_invalidos(self):
        for minute in range(51):
            self._movement(minute=minute)
        self._login()
        first = self.client.get("/alumno/historial")
        second = self.client.get("/alumno/historial?page=2")
        self.assertIn("Siguiente", first.get_data(as_text=True))
        self.assertIn("Anterior", second.get_data(as_text=True))
        for page in ("0", "-1", "abc", "1.5"):
            response = self.client.get(f"/alumno/historial?page={page}")
            self.assertEqual(response.status_code, 400)
            self.assertIn("no es v", response.get_data(as_text=True))
        missing = self.client.get("/alumno/historial?page=3")
        self.assertEqual(missing.status_code, 404)
        self.assertIn("No se encontr", missing.get_data(as_text=True))

    def test_alumno_no_accede_a_admin_scanner_ni_registro(self):
        self._login()
        for path in ("/admin", "/admin/alumnos", "/admin/administradores", "/admin/escaneres", "/admin/cuentas-alumnos", "/scanner"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post("/scanner/validar", data={}).status_code, 403)

    def test_sesion_se_invalida_al_desactivar_cuenta(self):
        self._login()
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE usuarios SET estado = 'inactivo' WHERE usuario_id = ?", (self.account["usuario_id"],))
            connection.commit()
        finally:
            connection.close()
        response = self.client.get("/alumno")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_sesion_se_invalida_al_desactivar_alumno(self):
        self._login()
        alumnos_service.desactivar_alumno(self.student["alumno_id"], self.database_path)
        response = self.client.get("/alumno")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_login_rechaza_cuenta_alumno_inactiva_alumno_inactivo_y_sin_vinculo(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE usuarios SET estado = 'inactivo' WHERE usuario_id = ?", (self.account["usuario_id"],))
            connection.commit()
        finally:
            connection.close()
        self.assertIn("No fue posible iniciar sesion", self._login().get_data(as_text=True))
        role = next(item for item in roles_service.asegurar_roles_autenticacion(self.database_path) if item["nombre"] == "alumno")
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE usuarios SET estado = 'activo' WHERE usuario_id = ?", (self.account["usuario_id"],))
            connection.execute("UPDATE alumnos SET estado = 'inactivo' WHERE alumno_id = ?", (self.student["alumno_id"],))
            connection.commit()
        finally:
            connection.close()
        usuario_repository.crear("Sin vinculo", "unlinked@edupass.test", generate_password_hash(self.PASSWORD), "activo", role["rol_id"], self.database_path)
        self.assertIn("No fue posible iniciar sesion", self._login().get_data(as_text=True))
        self.assertIn("No fue posible iniciar sesion", self._login("unlinked@edupass.test").get_data(as_text=True))

    def test_logout_funciona(self):
        self._login()
        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", self.client.get("/alumno").headers["Location"])

    def test_error_tecnico_no_expone_detalles(self):
        self._login()
        for detail in ("SELECT secreto", str(self.database_path), "Traceback privado"):
            with self.subTest(detail=detail), patch.object(alumno_portal_service, "obtener_perfil_propio", side_effect=RepositoryError(detail)):
                response = self.client.get("/alumno")
                body = response.get_data(as_text=True)
                self.assertEqual(response.status_code, 500)
                self.assertNotIn(detail, body)
                self.assertNotIn("password_hash", body)
                self.assertIn("No fue posible completar la operaci", body)

    def test_escape_html_y_responsive(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE alumnos SET nombre = '<script>alert(1)</script>' WHERE alumno_id = ?", (self.student["alumno_id"],))
            connection.commit()
        finally:
            connection.close()
        self._login()
        body = self.client.get("/alumno").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", body)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", body)
        css = (SRC_PATH / "edupass" / "web" / "static" / "css" / "app.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 390px)", css)
        self.assertIn("student-qr-image", css)

    def test_rutas_no_contienen_alumno_id(self):
        rules = [rule.rule for rule in self.app.url_map.iter_rules() if rule.endpoint.startswith("alumno.")]
        self.assertEqual(sorted(rules), sorted(["/alumno", "/alumno/cambiar-password", "/alumno/credencial", "/alumno/credencial/generar", "/alumno/credencial/renovar", "/alumno/historial", "/alumno/historial/movimientos/<int:movimiento_id>"]))
        self.assertTrue(all("alumno_id" not in rule for rule in rules))

    def test_admin_scanner_camara_https_y_crud_sin_regresion(self):
        self._login("admin@edupass.test")
        self.assertEqual(self.client.get("/admin").status_code, 200)
        self.assertEqual(self.client.get("/admin/cuentas-alumnos").status_code, 200)
        self.client.post("/logout")
        self._login("scanner@edupass.test")
        scanner = self.client.get("/scanner")
        self.assertEqual(scanner.status_code, 200)
        self.assertIn("Escanear o registrar movimiento", scanner.get_data(as_text=True))
        self.assertIn("HTTPS_MODE", self.app.config)


if __name__ == "__main__":
    unittest.main()
