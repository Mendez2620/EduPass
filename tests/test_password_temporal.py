import inspect
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import re

from werkzeug.security import check_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import cuentas_alumno_service
from edupass.modules.auth import roles_service, usuarios_service
from edupass.persistence import database_manager
from edupass.shared.errors import AuthenticationError
from edupass.web import create_app


class TestMigracionPasswordTemporal(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_base_nueva_incluye_flag(self):
        path = self.root / "new.sqlite"
        database_manager.initialize_database(path, SCHEMA_PATH)
        connection = sqlite3.connect(path)
        try:
            columns = {row[1]: row for row in connection.execute("PRAGMA table_info(usuarios);")}
        finally:
            connection.close()
        self.assertIn("requiere_cambio_password", columns)
        self.assertEqual(columns["requiere_cambio_password"][4], "0")

    def test_base_historica_migra_preserva_usuario_y_es_idempotente(self):
        path = self.root / "historic.sqlite"
        connection = sqlite3.connect(path)
        try:
            connection.executescript("""
                CREATE TABLE roles (rol_id INTEGER PRIMARY KEY, nombre TEXT UNIQUE, descripcion TEXT);
                CREATE TABLE usuarios (
                    usuario_id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
                    correo TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                    estado TEXT NOT NULL, rol_id INTEGER NOT NULL
                );
                INSERT INTO roles VALUES (1, 'administrador', NULL);
                INSERT INTO usuarios VALUES (7, 'Historico', 'h@test', 'hash', 'activo', 1);
            """)
            connection.commit()
        finally:
            connection.close()
        database_manager.initialize_database(path, SCHEMA_PATH)
        database_manager.initialize_database(path, SCHEMA_PATH)
        connection = sqlite3.connect(path)
        try:
            row = connection.execute(
                "SELECT usuario_id, correo, requiere_cambio_password FROM usuarios WHERE usuario_id = 7;"
            ).fetchone()
            count = sum(
                column[1] == "requiere_cambio_password"
                for column in connection.execute("PRAGMA table_info(usuarios);")
            )
        finally:
            connection.close()
        self.assertEqual(row, (7, "h@test", 0))
        self.assertEqual(count, 1)


class TestPasswordTemporalFlow(unittest.TestCase):
    ADMIN_PASSWORD = "ClaveAdmin123!"
    NEW_PASSWORD = "ClaveAlumnoNueva456!"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "flow.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "temporary-flow-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        roles_service.asegurar_roles_sistema(self.database_path)
        self.admin = usuarios_service.crear_usuario_demo(
            "Admin", "admin.temp@edupass.test", self.ADMIN_PASSWORD,
            "administrador", self.database_path,
        )
        self.scanner = usuarios_service.crear_usuario_demo(
            "Scanner", "scanner.temp@edupass.test", self.ADMIN_PASSWORD,
            "escaner", self.database_path,
        )
        self.account, self.temporary = cuentas_alumno_service.crear_alumno_con_cuenta(
            "Alumno Temporal", "TMP-001", "3", "A", None, "activo",
            "alumno.temp@edupass.test", "activo", self.admin["usuario_id"],
            self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _login(self, client, email, password):
        return client.post("/login", data={"correo": email, "password": password})

    def _stored(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(
                "SELECT password_hash, requiere_cambio_password, correo, rol_id "
                "FROM usuarios WHERE usuario_id = ?;",
                (self.account["usuario_id"],),
            ).fetchone()
        finally:
            connection.close()

    def test_generador_usa_secrets_cumple_politica_y_varia(self):
        source = inspect.getsource(cuentas_alumno_service.generar_password_temporal)
        self.assertIn("secrets.", source)
        self.assertNotIn("random", source)
        first = cuentas_alumno_service.generar_password_temporal()
        second = cuentas_alumno_service.generar_password_temporal()
        self.assertGreaterEqual(len(first), 8)
        self.assertLessEqual(len(first), 256)
        self.assertNotEqual(first, second)

    def test_alta_guarda_hash_y_flag_uno(self):
        stored_hash, flag, _correo, _rol_id = self._stored()
        self.assertEqual(flag, 1)
        self.assertNotEqual(stored_hash, self.temporary)
        self.assertTrue(check_password_hash(stored_hash, self.temporary))

    def test_login_temporal_redirige_y_bloquea_portal(self):
        client = self.app.test_client()
        response = self._login(client, self.account["correo"], self.temporary)
        self.assertTrue(response.headers["Location"].endswith("/alumno/cambiar-password"))
        for path in ("/alumno", "/alumno/credencial", "/alumno/historial"):
            with self.subTest(path=path):
                blocked = client.get(path)
                self.assertEqual(blocked.status_code, 302)
                self.assertTrue(blocked.headers["Location"].endswith("/alumno/cambiar-password"))
        self.assertEqual(client.get("/alumno/cambiar-password").status_code, 200)

    def test_cambio_incorrecto_conserva_flag(self):
        client = self.app.test_client()
        self._login(client, self.account["correo"], self.temporary)
        response = client.post("/alumno/cambiar-password", data={
            "password_actual": "TemporalIncorrecta123!",
            "password_nuevo": self.NEW_PASSWORD,
            "confirmar_password": self.NEW_PASSWORD,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._stored()[1], 1)

    def test_cambio_correcto_desactiva_flag_y_reemplaza_temporal(self):
        client = self.app.test_client()
        self._login(client, self.account["correo"], self.temporary)
        response = client.post("/alumno/cambiar-password", data={
            "password_actual": self.temporary,
            "password_nuevo": self.NEW_PASSWORD,
            "confirmar_password": self.NEW_PASSWORD,
        })
        self.assertTrue(response.headers["Location"].endswith("/alumno"))
        self.assertEqual(self._stored()[1], 0)
        with self.assertRaises(AuthenticationError):
            usuarios_service.autenticar_usuario(
                self.account["correo"], self.temporary, self.database_path
            )
        self.assertEqual(
            usuarios_service.autenticar_usuario(
                self.account["correo"], self.NEW_PASSWORD, self.database_path
            )["usuario_id"],
            self.account["usuario_id"],
        )
        self.assertEqual(client.get("/alumno").status_code, 200)
        self.assertEqual(client.get("/alumno/credencial").status_code, 200)
        self.assertEqual(client.get("/alumno/historial").status_code, 200)

    def test_nueva_password_no_puede_ser_igual_a_temporal(self):
        client = self.app.test_client()
        self._login(client, self.account["correo"], self.temporary)
        response = client.post("/alumno/cambiar-password", data={
            "password_actual": self.temporary,
            "password_nuevo": self.temporary,
            "confirmar_password": self.temporary,
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._stored()[1], 1)

    def test_admin_y_escaner_no_usan_cambio_alumno(self):
        for email in ("admin.temp@edupass.test", "scanner.temp@edupass.test"):
            client = self.app.test_client()
            self._login(client, email, self.ADMIN_PASSWORD)
            self.assertEqual(client.get("/alumno/cambiar-password").status_code, 403)

    def test_regeneracion_bloquea_sesion_existente_y_preserva_cuenta(self):
        client = self.app.test_client()
        self._login(client, self.account["correo"], self.temporary)
        client.post("/alumno/cambiar-password", data={
            "password_actual": self.temporary,
            "password_nuevo": self.NEW_PASSWORD,
            "confirmar_password": self.NEW_PASSWORD,
        })
        before = self._stored()
        _account, regenerated = cuentas_alumno_service.generar_password_temporal_cuenta_alumno(
            self.account["usuario_id"], self.admin["usuario_id"], self.database_path
        )
        after = self._stored()
        self.assertEqual(before[2:], after[2:])
        self.assertEqual(after[1], 1)
        self.assertTrue(client.get("/alumno").headers["Location"].endswith("/alumno/cambiar-password"))
        wrong = client.post("/alumno/cambiar-password", data={
            "password_actual": self.NEW_PASSWORD,
            "password_nuevo": "OtraClaveNueva789!",
            "confirmar_password": "OtraClaveNueva789!",
        })
        self.assertEqual(wrong.status_code, 400)
        self.assertTrue(check_password_hash(after[0], regenerated))

    def test_cuenta_inactiva_con_temporal_sigue_sin_autenticar(self):
        cuentas_alumno_service.desactivar_cuenta_alumno(
            self.account["usuario_id"], self.admin["usuario_id"], self.database_path
        )
        _account, regenerated = (
            cuentas_alumno_service.generar_password_temporal_cuenta_alumno(
                self.account["usuario_id"], self.admin["usuario_id"],
                self.database_path,
            )
        )
        with self.assertRaises(AuthenticationError):
            usuarios_service.autenticar_usuario(
                self.account["correo"], regenerated, self.database_path
            )

    def test_respuesta_temporal_no_guarda_clave_en_sesion_o_url(self):
        client = self.app.test_client()
        self._login(client, "admin.temp@edupass.test", self.ADMIN_PASSWORD)
        fixed = "TemporalMostrada123!"
        with patch.object(cuentas_alumno_service, "generar_password_temporal", return_value=fixed):
            response = client.post(
                f'/admin/cuentas-alumnos/{self.account["usuario_id"]}/password'
            )
        self.assertIn(fixed, response.get_data(as_text=True))
        self.assertNotIn(fixed, response.request.url)
        self.assertIn("no-store", response.headers["Cache-Control"])
        with client.session_transaction() as session_data:
            self.assertNotIn(fixed, repr(dict(session_data)))
        get_again = client.get(
            f'/admin/cuentas-alumnos/{self.account["usuario_id"]}/password'
        )
        self.assertNotIn(fixed, get_again.get_data(as_text=True))

    def test_regeneracion_exige_csrf(self):
        csrf_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "csrf-temporary-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": True,
        })
        client = csrf_app.test_client()
        login_page = client.get("/login").get_data(as_text=True)
        token = re.search(
            r'name="csrf_token"[^>]*value="([^"]+)"', login_page
        ).group(1)
        client.post("/login", data={
            "correo": "admin.temp@edupass.test",
            "password": self.ADMIN_PASSWORD,
            "csrf_token": token,
        })
        response = client.post(
            f'/admin/cuentas-alumnos/{self.account["usuario_id"]}/password'
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
