from html.parser import HTMLParser
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service
from edupass.modules.auth import usuarios_service
from edupass.persistence import database_manager
from edupass.web import create_app


class InputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []
        self._capture_manual_token = False
        self._manual_token_parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input":
            self.inputs.append(attributes)
        if attributes.get("id") == "manual-token":
            self._capture_manual_token = True

    def handle_data(self, data):
        if self._capture_manual_token:
            self._manual_token_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "code" and self._capture_manual_token:
            self._capture_manual_token = False

    def manual_token(self):
        return "".join(self._manual_token_parts).strip() or None

    def value(self, *, name=None, element_id=None):
        for attributes in self.inputs:
            if name is not None and attributes.get("name") != name:
                continue
            if element_id is not None and attributes.get("id") != element_id:
                continue
            return attributes.get("value")
        return None


class TestWebCredencial(unittest.TestCase):
    PASSWORD = "ClaveWebSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "web_credencial.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        usuarios_service.crear_usuario_demo(
            "Administradora Web", "admin@edupass.test", self.PASSWORD,
            "administrador", self.database_path,
        )
        usuarios_service.crear_usuario_demo(
            "Escaner Web", "scanner@edupass.test", self.PASSWORD,
            "escaner", self.database_path,
        )
        self.activo = alumnos_service.registrar_alumno(
            "Ana Credencial Demo", "CRED-1234", "3", "A",
            fotografia="C:/privada/ana.png", estado="activo",
            database_path=self.database_path,
        )
        self.inactivo = alumnos_service.registrar_alumno(
            "Luis Inactivo Demo", "INAC-5678", "4", "B",
            estado="inactivo", database_path=self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _login(self, email="admin@edupass.test", client=None):
        selected = client or self.client
        return selected.post("/login", data={
            "correo": email,
            "password": self.PASSWORD,
        })

    def _generate(self, alumno_id=None):
        selected = alumno_id or self.activo["alumno_id"]
        return self.client.post("/admin/credencial", data={"alumno_id": selected})

    def _parse(self, response):
        parser = InputParser()
        parser.feed(response.get_data(as_text=True))
        return parser

    def _token(self, response):
        return self._parse(response).manual_token()

    def _count(self, table):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
        finally:
            connection.close()

    def test_admin_ve_accion_credencial_en_listado(self):
        self._login()
        body = self.client.get("/admin/alumnos").get_data(as_text=True)
        self.assertIn("Credencial", body)
        self.assertIn("Generar credencial", body)

    def test_visitante_no_genera_credencial(self):
        response = self._generate()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_escaner_recibe_403(self):
        self._login("scanner@edupass.test")
        self.assertEqual(self._generate().status_code, 403)

    def test_get_generacion_devuelve_405(self):
        self._login()
        self.assertEqual(self.client.get("/admin/credencial").status_code, 405)

    def test_post_valido_genera_credencial(self):
        self._login()
        self.assertEqual(self._generate().status_code, 200)

    def test_respuesta_muestra_nombre(self):
        self._login()
        self.assertIn("Ana Credencial Demo", self._generate().get_data(as_text=True))

    def test_respuesta_muestra_matricula_enmascarada(self):
        self._login()
        body = self._generate().get_data(as_text=True)
        self.assertIn("*****1234", body)

    def test_respuesta_no_muestra_matricula_completa(self):
        self._login()
        self.assertNotIn("CRED-1234", self._generate().get_data(as_text=True))

    def test_respuesta_no_muestra_fotografia(self):
        self._login()
        body = self._generate().get_data(as_text=True)
        self.assertNotIn("C:/privada/ana.png", body)
        self.assertNotIn("fotografia", body.lower())

    def test_respuesta_no_muestra_token_hash(self):
        self._login()
        response = self._generate()
        token = self._token(response)
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        self.assertNotIn(token_hash, response.get_data(as_text=True))
        self.assertNotIn("token_hash", response.get_data(as_text=True))

    def test_muestra_token_manual(self):
        self._login()
        token = self._token(self._generate())
        self.assertIsNotNone(token)
        self.assertEqual(len(token), 43)

    def test_muestra_data_uri_svg(self):
        self._login()
        body = self._generate().get_data(as_text=True)
        self.assertIn("data:image/svg+xml;base64,", body)

    def test_muestra_vigencia_de_30_segundos(self):
        self._login()
        body = self._generate().get_data(as_text=True)
        self.assertIn("Vigencia de 30 segundos", body)

    def test_muestra_contador(self):
        self._login()
        body = self._generate().get_data(as_text=True)
        self.assertIn("data-credential-countdown", body)
        self.assertIn("Tiempo restante", (PROJECT_ROOT / "src/edupass/web/static/js/credencial.js").read_text(encoding="utf-8"))

    def test_muestra_boton_renovar(self):
        self._login()
        body = self._generate().get_data(as_text=True)
        self.assertIn("Renovar credencial", body)
        self.assertIn("/admin/credencial/renovar", body)

    def test_muestra_nota_de_vista_administrativa(self):
        self._login()
        body = self._generate().get_data(as_text=True)
        self.assertIn("Vista administrativa de demostración", body)
        self.assertIn("No es un portal autónomo del alumno", body)

    def test_alumno_inexistente_devuelve_404(self):
        self._login()
        response = self._generate(999999)
        self.assertEqual(response.status_code, 404)
        self.assertIn("No se encontro el alumno", response.get_data(as_text=True))

    def test_alumno_inactivo_devuelve_409(self):
        self._login()
        response = self._generate(self.inactivo["alumno_id"])
        self.assertEqual(response.status_code, 409)
        self.assertIn("inactivo", response.get_data(as_text=True))

    def test_post_sin_csrf_devuelve_400(self):
        csrf_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "csrf-test-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": True,
        })
        client = csrf_app.test_client()
        login_page = client.get("/login")
        csrf_token = self._parse(login_page).value(name="csrf_token")
        client.post("/login", data={
            "correo": "admin@edupass.test",
            "password": self.PASSWORD,
            "csrf_token": csrf_token,
        })
        response = client.post("/admin/credencial", data={
            "alumno_id": self.activo["alumno_id"],
        })
        self.assertEqual(response.status_code, 400)

    def test_renovacion_produce_token_distinto(self):
        self._login()
        first = self._generate()
        first_token = self._token(first)
        second = self.client.post("/admin/credencial/renovar", data={
            "alumno_id": self.activo["alumno_id"],
        })
        self.assertNotEqual(first_token, self._token(second))

    def test_renovacion_invalida_token_anterior(self):
        self._login()
        old_token = self._token(self._generate())
        self.client.post("/admin/credencial/renovar", data={
            "alumno_id": self.activo["alumno_id"],
        })
        old_hash = hashlib.sha256(old_token.encode("ascii")).hexdigest()
        connection = database_manager.get_connection(self.database_path)
        try:
            state = connection.execute(
                "SELECT estado FROM qr_tokens WHERE token_hash = ?;",
                (old_hash,),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(state, "invalidado")

    def test_get_renovacion_devuelve_405(self):
        self._login()
        self.assertEqual(self.client.get("/admin/credencial/renovar").status_code, 405)

    def test_respuesta_incluye_no_store(self):
        self._login()
        self.assertIn("no-store", self._generate().headers["Cache-Control"])

    def test_respuesta_incluye_no_referrer(self):
        self._login()
        self.assertEqual(self._generate().headers["Referrer-Policy"], "no-referrer")

    def test_no_crea_archivos_qr(self):
        self._login()
        static_root = PROJECT_ROOT / "src/edupass/web/static"
        before = {path.relative_to(static_root) for path in static_root.rglob("*") if path.is_file()}
        self._generate()
        after = {path.relative_to(static_root) for path in static_root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_no_registra_movimientos(self):
        self._login()
        self._generate()
        self.assertEqual(self._count("movimientos"), 0)

    def test_no_registra_intentos_rechazados(self):
        self._login()
        self._generate(self.inactivo["alumno_id"])
        self.assertEqual(self._count("intentos_rechazados"), 0)

    def test_contenido_html_queda_escapado(self):
        unsafe = alumnos_service.registrar_alumno(
            "<script>alert('x')</script>", "SAFE-0001", "1", "C",
            estado="activo", database_path=self.database_path,
        )
        self._login()
        body = self._generate(unsafe["alumno_id"]).get_data(as_text=True)
        self.assertNotIn("<script>alert", body)
        self.assertIn("&lt;script&gt;", body)

    def test_script_de_renovacion_es_local(self):
        self._login()
        body = self._generate().get_data(as_text=True)
        self.assertIn("/static/js/credencial.js", body)
        self.assertNotIn("cdn", body.lower())

    def test_no_existen_urls_publicas_de_credencial(self):
        rules = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertNotIn("/credencial/<clave_opaca>", rules)
        self.assertTrue(all(not rule.startswith("/credencial/") for rule in rules))


if __name__ == "__main__":
    unittest.main()