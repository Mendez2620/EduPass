from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service
from edupass.modules.auth import usuarios_service
from edupass.modules.credencial_qr import credencial_service
from edupass.persistence import database_manager
from edupass.shared.errors import RepositoryError, UsuarioEscanerInvalidoError
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


class TestWebMovimientos(unittest.TestCase):
    PASSWORD = "ClaveWebSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "web_movimientos.sqlite"
        )
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.admin = usuarios_service.crear_usuario_demo(
            "Administradora Web",
            "admin@edupass.test",
            self.PASSWORD,
            "administrador",
            self.database_path,
        )
        self.scanner = usuarios_service.crear_usuario_demo(
            "Escaner Web",
            "scanner@edupass.test",
            self.PASSWORD,
            "escaner",
            self.database_path,
        )
        self.alumno = alumnos_service.registrar_alumno(
            "Alumno Movimiento",
            "MOV-0001",
            "3",
            "A",
            estado="activo",
            database_path=self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _login(self, email="scanner@edupass.test", client=None):
        selected = client or self.client
        return selected.post("/login", data={
            "correo": email,
            "password": self.PASSWORD,
        })

    def _generate(self, clock=None):
        return credencial_service.generar_credencial(
            self.alumno["alumno_id"],
            self.database_path,
            clock,
        )["token"]

    def _post(self, token, tipo="entrada", client=None):
        selected = client or self.client
        return selected.post(
            "/scanner/validar",
            data={"tipo_movimiento": tipo, "token": token},
        )

    def _query_one(self, sql, parameters=()):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(sql, parameters).fetchone()
        finally:
            connection.close()

    def _count(self, table):
        return self._query_one(f"SELECT COUNT(*) FROM {table};")[0]

    def _token_state(self, token):
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        return self._query_one(
            "SELECT estado FROM qr_tokens WHERE token_hash = ?;",
            (token_hash,),
        )[0]

    def _register_entry_and_exit(self):
        self._post(self._generate(), "entrada")
        self._post(self._generate(), "salida")

    def test_01_visitante_es_redirigido(self):
        response = self.client.get("/scanner/validar")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_02_administrador_recibe_403(self):
        self._login("admin@edupass.test")
        self.assertEqual(self.client.get("/scanner/validar").status_code, 403)

    def test_03_escaner_recibe_formulario(self):
        self._login()
        response = self.client.get("/scanner/validar")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Captura manual", response.get_data(as_text=True))

    def test_04_selector_entrada_salida_presente(self):
        self._login()
        body = self.client.get("/scanner/validar").get_data(as_text=True)
        self.assertIn('name="tipo_movimiento"', body)
        self.assertIn("Entrada", body)
        self.assertIn("Salida", body)

    def test_05_csrf_presente(self):
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

    def test_06_post_sin_csrf_devuelve_400(self):
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
        response = self._post("A" * 43, client=client)
        self.assertEqual(response.status_code, 400)

    def test_07_primera_entrada_exitosa(self):
        self._login()
        response = self._post(self._generate())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Movimiento registrado", response.get_data(as_text=True))

    def test_08_movimiento_insertado(self):
        self._login()
        self._post(self._generate())
        self.assertEqual(self._count("movimientos"), 1)

    def test_09_qr_utilizado_tras_entrada(self):
        token = self._generate()
        self._login()
        self._post(token)
        self.assertEqual(self._token_state(token), "utilizado")

    def test_10_mensaje_exacto_de_entrada(self):
        self._login()
        body = self._post(self._generate()).get_data(as_text=True)
        self.assertIn("Entrada registrada correctamente.", body)

    def test_11_salida_valida(self):
        self._login()
        self._post(self._generate(), "entrada")
        response = self._post(self._generate(), "salida")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count("movimientos"), 2)

    def test_12_mensaje_exacto_de_salida(self):
        self._login()
        self._post(self._generate(), "entrada")
        body = self._post(self._generate(), "salida").get_data(as_text=True)
        self.assertIn("Salida registrada correctamente.", body)

    def test_13_doble_entrada_rechazada(self):
        self._login()
        self._post(self._generate(), "entrada")
        body = self._post(self._generate(), "entrada").get_data(as_text=True)
        self.assertIn(
            "No se puede registrar otra entrada sin una salida previa.",
            body,
        )
        self.assertEqual(self._count("movimientos"), 1)

    def test_14_qr_activo_tras_doble_entrada(self):
        self._login()
        self._post(self._generate(), "entrada")
        token = self._generate()
        self._post(token, "entrada")
        self.assertEqual(self._token_state(token), "activo")

    def test_15_salida_sin_entrada_rechazada(self):
        self._login()
        body = self._post(self._generate(), "salida").get_data(as_text=True)
        self.assertIn(
            "No se puede registrar una salida sin una entrada previa.",
            body,
        )

    def test_16_qr_activo_tras_salida_invalida(self):
        token = self._generate()
        self._login()
        self._post(token, "salida")
        self.assertEqual(self._token_state(token), "activo")

    def test_17_doble_salida_rechazada(self):
        self._login()
        self._register_entry_and_exit()
        token = self._generate()
        body = self._post(token, "salida").get_data(as_text=True)
        self.assertIn(
            "No se puede registrar otra salida sin una nueva entrada.",
            body,
        )
        self.assertEqual(self._token_state(token), "activo")

    def test_18_nueva_entrada_despues_de_salida(self):
        self._login()
        self._register_entry_and_exit()
        response = self._post(self._generate(), "entrada")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count("movimientos"), 3)

    def test_19_qr_vencido(self):
        old = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = self._generate(clock=lambda: old)
        self._login()
        body = self._post(token).get_data(as_text=True)
        self.assertIn("Token vencido.", body)

    def test_20_qr_utilizado(self):
        token = self._generate()
        self._login()
        self._post(token)
        body = self._post(token, "salida").get_data(as_text=True)
        self.assertIn("Token ya utilizado.", body)

    def test_21_qr_alterado(self):
        token = self._generate()
        altered = token[:-1] + ("A" if token[-1] != "A" else "B")
        self._login()
        body = self._post(altered).get_data(as_text=True)
        self.assertIn("Token inv\u00e1lido.", body)

    def test_22_qr_inexistente(self):
        self._login()
        body = self._post("Z" * 43).get_data(as_text=True)
        self.assertIn("Token inv\u00e1lido.", body)

    def test_23_alumno_inactivo(self):
        token = self._generate()
        alumnos_service.desactivar_alumno(
            self.alumno["alumno_id"],
            self.database_path,
        )
        self._login()
        body = self._post(token).get_data(as_text=True)
        self.assertIn("Alumno inactivo.", body)

    def test_24_usuario_escaner_desactivado_durante_operacion(self):
        self._login()
        with patch(
            "edupass.web.scanner_routes.movimientos_service."
            "registrar_movimiento_con_token",
            side_effect=UsuarioEscanerInvalidoError(),
        ):
            response = self._post(self._generate())
        self.assertEqual(response.status_code, 403)

    def test_25_formulario_sin_tipo(self):
        self._login()
        response = self._post(self._generate(), "")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Selecciona un tipo de movimiento", response.get_data(as_text=True))

    def test_26_formulario_sin_token(self):
        self._login()
        response = self._post("", "entrada")
        self.assertEqual(response.status_code, 400)
        self.assertIn("ingresa un token QR", response.get_data(as_text=True))

    def test_27_tipo_manipulado(self):
        self._login()
        response = self._post(self._generate(), "eliminar")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._count("movimientos"), 0)

    def test_28_token_no_aparece_en_respuesta(self):
        token = self._generate()
        self._login()
        body = self._post(token).get_data(as_text=True)
        self.assertNotIn(token, body)

    def test_29_hash_no_aparece_en_respuesta(self):
        token = self._generate()
        token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        self._login()
        body = self._post(token).get_data(as_text=True)
        self.assertNotIn(token_hash, body)
        self.assertNotIn("token_hash", body)

    def test_30_matricula_no_aparece_en_respuesta(self):
        self._login()
        body = self._post(self._generate()).get_data(as_text=True)
        self.assertNotIn("MOV-0001", body)
        self.assertNotIn("Matr\u00edcula", body)

    def test_31_ids_internos_no_aparecen_en_respuesta(self):
        self._login()
        body = self._post(self._generate()).get_data(as_text=True)
        self.assertNotIn("alumno_id", body)
        self.assertNotIn("usuario_id", body)
        self.assertNotIn("movimiento_id", body)

    def test_32_sql_no_aparece_en_respuesta(self):
        self._login()
        body = self._post("Z" * 43).get_data(as_text=True)
        self.assertNotIn("SELECT ", body)
        self.assertNotIn("UPDATE ", body)
        self.assertNotIn("INSERT ", body)

    def test_33_ruta_sqlite_no_aparece_en_respuesta(self):
        self._login()
        body = self._post("Z" * 43).get_data(as_text=True)
        self.assertNotIn(str(self.database_path), body)
        self.assertNotIn(".sqlite", body)

    def test_34_traceback_no_aparece_en_respuesta(self):
        self._login()
        body = self._post("Z" * 43).get_data(as_text=True)
        self.assertNotIn("Traceback", body)

    def test_35_error_tecnico_controlado(self):
        self._login()
        with patch(
            "edupass.web.scanner_routes.movimientos_service."
            "registrar_movimiento_con_token",
            side_effect=RepositoryError("SELECT secreto"),
        ):
            response = self._post(self._generate())
        self.assertEqual(response.status_code, 500)
        body = response.get_data(as_text=True)
        self.assertIn("No fue posible registrar el movimiento.", body)
        self.assertNotIn("SELECT secreto", body)

    def test_36_get_no_consume_ni_registra(self):
        token = self._generate()
        self._login()
        self.client.get("/scanner/validar")
        self.assertEqual(self._token_state(token), "activo")
        self.assertEqual(self._count("movimientos"), 0)

    def test_37_javascript_referenciado(self):
        self._login()
        body = self.client.get("/scanner/validar").get_data(as_text=True)
        self.assertIn("js/scanner_validation.js", body)

    def test_38_formulario_usable_sin_javascript(self):
        self._login()
        response = self._post(self._generate())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count("movimientos"), 1)

    def test_39_boton_muestra_texto_correcto(self):
        self._login()
        body = self.client.get("/scanner/validar").get_data(as_text=True)
        self.assertIn(">Registrar movimiento</button>", body)

    def test_40_area_y_dispositivo_permanecen_null(self):
        self._login()
        self._post(self._generate())
        row = self._query_one(
            "SELECT area_id, dispositivo_id FROM movimientos LIMIT 1;"
        )
        self.assertIsNone(row[0])
        self.assertIsNone(row[1])


if __name__ == "__main__":
    unittest.main()
