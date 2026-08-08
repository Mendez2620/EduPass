from datetime import datetime, timedelta, timezone
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
from edupass.modules.credencial_qr import credencial_service
from edupass.persistence import database_manager
from edupass.web import create_app


class InputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.inputs.append(dict(attrs))

    def value(self, name):
        for attributes in self.inputs:
            if attributes.get("name") == name:
                return attributes.get("value")
        return None


class TestWebQrValidation(unittest.TestCase):
    PASSWORD = "ClaveWebSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "web_qr_validation.sqlite"
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
        self.alumno = alumnos_service.registrar_alumno(
            "Alumno QR Demo", "QR-0001", "3", "A",
            estado="activo", database_path=self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _login(self, email="scanner@edupass.test", client=None):
        selected = client or self.client
        return selected.post("/login", data={
            "correo": email,
            "password": self.PASSWORD,
        })

    def _generate(self, alumno_id=None, clock=None):
        return credencial_service.generar_credencial(
            alumno_id or self.alumno["alumno_id"],
            self.database_path,
            clock,
        )["token"]

    def _post(self, token, movement_type=None):
        preview = self.client.post("/scanner/validar", data={
            "token": token,
            "preview_submit": "Detectar movimiento",
        })
        parser = InputParser()
        parser.feed(preview.get_data(as_text=True))
        preview_id = parser.value("preview_id")
        if preview_id is None:
            return preview
        return self.client.post("/scanner/validar", data={
            "preview_id": preview_id,
            "tipo_esperado": (
                movement_type
                if movement_type is not None
                else parser.value("tipo_esperado")
            ),
            "confirm_submit": "1",
        })

    def _count(self, table):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
        finally:
            connection.close()

    def _last_movement_type(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            row = connection.execute(
                "SELECT tipo_movimiento FROM movimientos ORDER BY movimiento_id DESC;"
            ).fetchone()
            return row[0]
        finally:
            connection.close()

    def _state(self, token):
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        connection = database_manager.get_connection(self.database_path)
        try:
            row = connection.execute(
                "SELECT estado FROM qr_tokens WHERE token_hash = ?;",
                (token_hash,),
            ).fetchone()
            return row[0]
        finally:
            connection.close()

    def test_visitante_es_redirigido(self):
        response = self.client.get("/scanner/validar")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_administrador_recibe_403(self):
        self._login("admin@edupass.test")
        self.assertEqual(self.client.get("/scanner/validar").status_code, 403)

    def test_escaner_obtiene_formulario(self):
        self._login()
        response = self.client.get("/scanner/validar")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Captura manual", response.get_data(as_text=True))

    def test_formulario_incluye_csrf(self):
        csrf_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "csrf-test-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": True,
        })
        client = csrf_app.test_client()
        login_page = client.get("/login")
        parser = InputParser()
        parser.feed(login_page.get_data(as_text=True))
        client.post("/login", data={
            "correo": "scanner@edupass.test",
            "password": self.PASSWORD,
            "csrf_token": parser.value("csrf_token"),
        })
        body = client.get("/scanner/validar").get_data(as_text=True)
        self.assertIn('name="csrf_token"', body)

    def test_token_valido_es_consumido(self):
        token = self._generate()
        self._login()
        response = self._post(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._state(token), "utilizado")

    def test_muestra_mensaje_exacto_de_exito(self):
        token = self._generate()
        self._login()
        body = self._post(token).get_data(as_text=True)
        self.assertIn("Entrada registrada correctamente.", body)
        self.assertEqual(self._count("movimientos"), 1)
        self.assertEqual(self._last_movement_type(), "entrada")

    def test_segundo_uso_muestra_utilizado(self):
        token = self._generate()
        self._login()
        self._post(token)
        response = self._post(token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Token ya utilizado.", response.get_data(as_text=True))

    def test_token_vencido_muestra_vencido(self):
        old = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = self._generate(clock=lambda: old)
        self._login()
        response = self._post(token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Token vencido.", response.get_data(as_text=True))

    def test_token_invalido_muestra_invalido(self):
        self._login()
        response = self._post("Z" * 43)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Token inválido.", response.get_data(as_text=True))

    def test_token_alterado_muestra_invalido(self):
        token = self._generate()
        altered = token[:-1] + ("A" if token[-1] != "A" else "B")
        self._login()
        body = self._post(altered).get_data(as_text=True)
        self.assertIn("Token inválido.", body)

    def test_alumno_desactivado_muestra_inactivo(self):
        token = self._generate()
        alumnos_service.desactivar_alumno(self.alumno["alumno_id"], self.database_path)
        self._login()
        response = self._post(token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Alumno inactivo.", response.get_data(as_text=True))

    def test_token_vacio_muestra_validacion_controlada(self):
        self._login()
        response = self._post("")
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Ingresa un token QR válido de 43 caracteres.",
            response.get_data(as_text=True),
        )

    def test_post_sin_csrf_devuelve_400(self):
        csrf_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "csrf-test-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": True,
        })
        client = csrf_app.test_client()
        login_page = client.get("/login")
        parser = InputParser()
        parser.feed(login_page.get_data(as_text=True))
        client.post("/login", data={
            "correo": "scanner@edupass.test",
            "password": self.PASSWORD,
            "csrf_token": parser.value("csrf_token"),
        })
        response = client.post("/scanner/validar", data={
            "tipo_movimiento": "entrada",
            "token": "A" * 43,
        })
        self.assertEqual(response.status_code, 400)

    def test_get_no_consume_token(self):
        token = self._generate()
        self._login()
        self.client.get("/scanner/validar")
        self.assertEqual(self._state(token), "activo")

    def test_respuesta_no_muestra_token(self):
        token = self._generate()
        self._login()
        body = self._post(token).get_data(as_text=True)
        self.assertNotIn(token, body)

    def test_respuesta_no_muestra_hash(self):
        token = self._generate()
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        self._login()
        body = self._post(token).get_data(as_text=True)
        self.assertNotIn(token_hash, body)
        self.assertNotIn("token_hash", body)

    def test_respuesta_no_muestra_alumno_id(self):
        token = self._generate()
        self._login()
        body = self._post(token).get_data(as_text=True)
        self.assertNotIn("alumno_id", body)

    def test_preview_muestra_matricula_enmascarada(self):
        token = self._generate()
        self._login()
        body = self.client.post(
            "/scanner/validar",
            data={"token": token, "preview_submit": "1"},
        ).get_data(as_text=True)
        self.assertNotIn("QR-0001", body)
        self.assertIn("***0001", body)

    def test_respuesta_no_muestra_ruta_sqlite(self):
        token = self._generate()
        self._login()
        body = self._post(token).get_data(as_text=True)
        self.assertNotIn(str(self.database_path), body)
        self.assertNotIn(".sqlite", body)

    def test_respuesta_no_muestra_sql(self):
        self._login()
        body = self._post("Z" * 43).get_data(as_text=True)
        self.assertNotIn("SELECT", body)
        self.assertNotIn("UPDATE", body)

    def test_respuesta_no_muestra_traceback(self):
        self._login()
        body = self._post("Z" * 43).get_data(as_text=True)
        self.assertNotIn("Traceback", body)

    def test_respuesta_incluye_no_store(self):
        self._login()
        response = self.client.get("/scanner/validar")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_respuesta_incluye_no_referrer(self):
        self._login()
        response = self.client.get("/scanner/validar")
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")

    def test_movimiento_de_entrada_es_registrado(self):
        token = self._generate()
        self._login()
        self._post(token)
        self.assertEqual(self._count("movimientos"), 1)
        self.assertEqual(self._last_movement_type(), "entrada")

    def test_intentos_rechazados_permanece_vacio(self):
        self._login()
        self._post("Z" * 43)
        self.assertEqual(self._count("intentos_rechazados"), 0)

    def test_token_anterior_renovado_es_rechazado(self):
        old_token = self._generate()
        credencial_service.renovar_token_qr(
            self.alumno["alumno_id"], self.database_path,
        )
        self._login()
        response = self._post(old_token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Token inválido.", response.get_data(as_text=True))

    def test_existe_interfaz_de_camara_con_respaldo_manual(self):
        self._login()
        body = self.client.get("/scanner/validar").get_data(as_text=True)
        self.assertIn("Escanear mediante cámara", body)
        self.assertIn("Activar cámara", body)
        self.assertIn("<video", body)
        self.assertIn("Captura manual", body)
        self.assertIn("vendor/zxing-browser/0.2.1/zxing-browser.min.js", body)
    def test_no_existe_campo_de_movimiento(self):
        self._login()
        body = self.client.get("/scanner/validar").get_data(as_text=True)
        self.assertNotIn('name="movimiento"', body)

    def test_selector_entrada_salida_fue_eliminado(self):
        self._login()
        body = self.client.get("/scanner/validar").get_data(as_text=True)
        self.assertNotIn("<select", body)
        self.assertNotIn('name="tipo_movimiento"', body)
        self.assertIn("Detectar movimiento", body)

    def test_resultado_de_negocio_usa_http_200(self):
        self._login()
        for token in ("Z" * 43, "Y" * 43):
            with self.subTest(token=token[0]):
                self.assertEqual(self._post(token).status_code, 200)


if __name__ == "__main__":
    unittest.main()
