from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import alumnos_service, cuentas_alumno_service
from edupass.modules.auth import usuarios_service
from edupass.modules.credencial_qr import credencial_service
from edupass.modules.movimientos import movimientos_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import movimiento_repository
from edupass.shared.errors import (
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    RepositoryError,
)
from edupass.web import create_app


class TestNotificacionesAlumno(unittest.TestCase):
    PASSWORD = "Password123!"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "notificaciones.sqlite"
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "notifications-test",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.admin = usuarios_service.crear_administrador(
            "Admin", "admin.notifications@edupass.test", self.PASSWORD,
            self.database_path,
        )
        self.scanner = usuarios_service.crear_escaner(
            "Scanner", "scanner.notifications@edupass.test", self.PASSWORD,
            self.database_path,
        )
        self.student = alumnos_service.registrar_alumno(
            "Alumno Notificado", "NOT-001", "3", "A", estado="activo",
            database_path=self.database_path,
        )
        self.other = alumnos_service.registrar_alumno(
            "Alumno Ajeno", "NOT-002", "4", "B", estado="activo",
            database_path=self.database_path,
        )
        self.account = cuentas_alumno_service.crear_cuenta_alumno(
            self.student["alumno_id"], "student.notifications@edupass.test",
            self.PASSWORD, self.admin["usuario_id"], self.database_path,
        )
        self.other_account = cuentas_alumno_service.crear_cuenta_alumno(
            self.other["alumno_id"], "other.notifications@edupass.test",
            self.PASSWORD, self.admin["usuario_id"], self.database_path,
        )

    def tearDown(self):
        self.temp.cleanup()

    def _login(self, email="student.notifications@edupass.test"):
        return self.client.post(
            "/login", data={"correo": email, "password": self.PASSWORD}
        )

    def _token(self, alumno_id=None, clock=None):
        return credencial_service.generar_credencial(
            alumno_id or self.student["alumno_id"], self.database_path, clock
        )["token"]

    def _register(self, token):
        return movimientos_service.registrar_movimiento_automatico_directo(
            token, self.scanner["usuario_id"], database_path=self.database_path
        )

    def _rows(self, sql, parameters=()):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def test_schema_new_contains_internal_notifications(self):
        columns = {
            row[1]: row for row in self._rows("PRAGMA table_info(notificaciones_alumno);")
        }
        self.assertEqual(
            set(columns),
            {"notificacion_id", "alumno_id", "movimiento_id", "leida", "creada_en"},
        )
        self.assertEqual(columns["leida"][4], "0")

    def test_historical_database_upgrade_is_idempotent_and_preserves_data(self):
        historical = Path(self.temp.name) / "historical.sqlite"
        connection = sqlite3.connect(historical)
        connection.executescript("""
            CREATE TABLE alumnos (
                alumno_id INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
                matricula TEXT NOT NULL UNIQUE, grado TEXT NOT NULL,
                grupo TEXT NOT NULL, fotografia TEXT, estado TEXT NOT NULL
            );
            INSERT INTO alumnos VALUES (7, 'Histórico', 'HIST-7', '2', 'C', NULL, 'activo');
        """)
        connection.commit(); connection.close()
        database_manager.initialize_database(historical)
        database_manager.initialize_database(historical)
        connection = sqlite3.connect(historical)
        try:
            self.assertEqual(connection.execute(
                "SELECT nombre FROM alumnos WHERE alumno_id = 7;"
            ).fetchone()[0], "Histórico")
            self.assertIsNotNone(connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='notificaciones_alumno';"
            ).fetchone())
        finally:
            connection.close()

    def test_entry_and_exit_each_create_one_notification(self):
        entry = self._register(self._token())
        exit_movement = self._register(self._token())
        rows = self._rows(
            "SELECT movimiento_id, leida FROM notificaciones_alumno ORDER BY notificacion_id;"
        )
        self.assertEqual([row[0] for row in rows], [entry["movimiento_id"], exit_movement["movimiento_id"]])
        self.assertEqual([row[1] for row in rows], [0, 0])

    def test_rejected_tokens_do_not_create_notifications(self):
        expired = self._token(clock=lambda: datetime.now(timezone.utc) - timedelta(minutes=1))
        with self.assertRaises(QRVencidoError):
            self._register(expired)
        used = self._token(); self._register(used)
        with self.assertRaises(QRUtilizadoError):
            self._register(used)
        with self.assertRaises(QRInvalidoError):
            self._register("Z" * 43)
        self.assertEqual(len(self._rows("SELECT * FROM notificaciones_alumno;")), 1)

    def test_camera_json_and_manual_form_create_same_notification_kind(self):
        self._login("scanner.notifications@edupass.test")
        camera = self.client.post(
            "/scanner/validar", json={"token": self._token()}
        )
        manual = self.client.post(
            "/scanner/validar", data={"token": self._token()}
        )
        self.assertEqual(camera.status_code, 200)
        self.assertEqual(manual.status_code, 200)
        rows = self._rows(
            "SELECT alumno_id, leida FROM notificaciones_alumno ORDER BY notificacion_id;"
        )
        self.assertEqual(rows, [
            (self.student["alumno_id"], 0),
            (self.student["alumno_id"], 0),
        ])

    def test_notification_failure_rolls_back_movement_and_qr_consumption(self):
        token = self._token()
        original = movimiento_repository._load_query

        def broken(file_name):
            if file_name == "insert_notificacion_alumno.sql":
                return "INSERT INTO tabla_inexistente VALUES (?, ?, ?);"
            return original(file_name)

        with patch.object(movimiento_repository, "_load_query", side_effect=broken):
            with self.assertRaises(RepositoryError):
                self._register(token)
        self.assertEqual(len(self._rows("SELECT * FROM movimientos;")), 0)
        self.assertEqual(len(self._rows("SELECT * FROM notificaciones_alumno;")), 0)
        self.assertEqual(self._rows("SELECT estado FROM qr_tokens;")[0][0], "activo")

    def test_movement_is_unique_in_notifications(self):
        movement = self._register(self._token())
        connection = database_manager.get_connection(self.database_path)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO notificaciones_alumno (alumno_id, movimiento_id, leida, creada_en) VALUES (?, ?, 0, ?);",
                    (self.student["alumno_id"], movement["movimiento_id"], movement["fecha_hora"]),
                )
        finally:
            connection.close()

    def test_student_lists_only_own_notifications_with_counter_and_states(self):
        self._register(self._token())
        self._register(self._token(self.other["alumno_id"]))
        self._login()
        response = self.client.get("/alumno/notificaciones")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Notificaciones (1)", body)
        self.assertIn("No leída", body)
        self.assertNotIn("Alumno Ajeno", body)
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_notifications_are_newest_first_and_link_to_owned_movement(self):
        first = self._register(self._token())
        second = self._register(self._token())
        self._login()
        body = self.client.get("/alumno/notificaciones").get_data(as_text=True)
        second_link = f'/alumno/historial/movimientos/{second["movimiento_id"]}'
        first_link = f'/alumno/historial/movimientos/{first["movimiento_id"]}'
        self.assertLess(body.index(second_link), body.index(first_link))
        self.assertIn(f'/alumno/historial/movimientos/{second["movimiento_id"]}', body)

    def test_mark_read_and_mark_all_require_post(self):
        movement = self._register(self._token())
        notification_id = self._rows(
            "SELECT notificacion_id FROM notificaciones_alumno WHERE movimiento_id = ?;",
            (movement["movimiento_id"],),
        )[0][0]
        self._login()
        self.assertEqual(self.client.get(f"/alumno/notificaciones/{notification_id}/leer").status_code, 405)
        response = self.client.post(f"/alumno/notificaciones/{notification_id}/leer")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self._rows(
            "SELECT leida FROM notificaciones_alumno WHERE notificacion_id = ?;",
            (notification_id,),
        )[0][0], 1)
        self.assertEqual(self.client.get("/alumno/notificaciones/marcar-todas-leidas").status_code, 405)

    def test_mark_all_updates_only_authenticated_students_notifications(self):
        self._register(self._token())
        self._register(self._token())
        self._register(self._token(self.other["alumno_id"]))
        self._login()
        response = self.client.post("/alumno/notificaciones/marcar-todas-leidas")
        self.assertEqual(response.status_code, 302)
        own_states = self._rows(
            "SELECT leida FROM notificaciones_alumno WHERE alumno_id = ?;",
            (self.student["alumno_id"],),
        )
        other_state = self._rows(
            "SELECT leida FROM notificaciones_alumno WHERE alumno_id = ?;",
            (self.other["alumno_id"],),
        )
        self.assertEqual(own_states, [(1,), (1,)])
        self.assertEqual(other_state, [(0,)])

    def test_marking_another_students_notification_is_blocked(self):
        movement = self._register(self._token(self.other["alumno_id"]))
        notification_id = self._rows(
            "SELECT notificacion_id FROM notificaciones_alumno WHERE movimiento_id = ?;",
            (movement["movimiento_id"],),
        )[0][0]
        self._login()
        self.assertEqual(
            self.client.post(f"/alumno/notificaciones/{notification_id}/leer").status_code,
            404,
        )
        self.assertEqual(self._rows(
            "SELECT leida FROM notificaciones_alumno WHERE notificacion_id = ?;",
            (notification_id,),
        )[0][0], 0)

    def test_admin_and_scanner_cannot_use_student_notifications(self):
        for email in ("admin.notifications@edupass.test", "scanner.notifications@edupass.test"):
            with self.subTest(email=email):
                self._login(email)
                self.assertEqual(self.client.get("/alumno/notificaciones").status_code, 403)
                self.client.post("/logout")

    def test_csrf_is_required_for_mutation(self):
        movement = self._register(self._token())
        notification_id = self._rows(
            "SELECT notificacion_id FROM notificaciones_alumno WHERE movimiento_id = ?;",
            (movement["movimiento_id"],),
        )[0][0]
        csrf_app = create_app({
            "TESTING": True,
            "SECRET_KEY": "notifications-csrf",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": True,
        })
        client = csrf_app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(self.account["usuario_id"])
            session["_fresh"] = True
        self.assertEqual(
            client.post(f"/alumno/notificaciones/{notification_id}/leer").status_code,
            400,
        )

    def test_empty_state_is_clear(self):
        self._login()
        body = self.client.get("/alumno/notificaciones").get_data(as_text=True)
        self.assertIn("Todavía no tienes notificaciones de movimientos.", body)

    def test_camera_contract_remains_persistent_and_local(self):
        js = (SRC_PATH / "edupass" / "web" / "static" / "js" / "scanner_validation.js").read_text(encoding="utf-8")
        template = (SRC_PATH / "edupass" / "web" / "templates" / "scanner" / "validar_qr.html").read_text(encoding="utf-8")
        self.assertIn("if (processing) return", js)
        self.assertIn("sendCameraToken(token)", js)
        self.assertIn("Cancelar cámara", template)
        self.assertIn("vendor/zxing-browser/0.2.1", template)


if __name__ == "__main__":
    unittest.main()
