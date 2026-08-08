from html.parser import HTMLParser
from pathlib import Path
import re
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
from edupass.persistence import database_manager
from edupass.shared.errors import RepositoryError
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


class TestWebAlumnosCrud(unittest.TestCase):
    PASSWORD = "ClaveWebSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "web_alumnos_crud.sqlite"
        )
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.admin = usuarios_service.crear_usuario_demo(
            "Administradora CRUD",
            "admin.crud@edupass.test",
            self.PASSWORD,
            "administrador",
            self.database_path,
        )
        usuarios_service.crear_usuario_demo(
            "Escaner CRUD",
            "scanner.crud@edupass.test",
            self.PASSWORD,
            "escaner",
            self.database_path,
        )
        self.activo = alumnos_service.registrar_alumno(
            "Alumno Activo",
            "CRUD-001",
            "3",
            "A",
            fotografia="C:/privado/alumno-activo.png",
            estado="activo",
            database_path=self.database_path,
        )
        self.inactivo = alumnos_service.registrar_alumno(
            "Alumno Inactivo",
            "CRUD-002",
            "4",
            "B",
            estado="inactivo",
            database_path=self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _login(self, correo="admin.crud@edupass.test", client=None):
        selected = client or self.client
        return selected.post(
            "/login",
            data={"correo": correo, "password": self.PASSWORD},
        )

    def _new_data(self, **overrides):
        data = {
            "nombre": "Nueva Alumna",
            "matricula": "crud-003",
            "grado": "5",
            "grupo": "C",
            "correo": "nueva.alumna@edupass.test",
            "estado_acceso": "activo",
        }
        data.update(overrides)
        return data

    def _edit_data(self, **overrides):
        data = {
            "nombre": "Alumno Actualizado",
            "matricula": "CRUD-001",
            "grado": "6",
            "grupo": "D",
        }
        data.update(overrides)
        return data

    def _query_one(self, sql, parameters=()):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(sql, parameters).fetchone()
        finally:
            connection.close()

    def _count(self, table):
        return self._query_one(f"SELECT COUNT(*) FROM {table};")[0]

    def _csrf_client(self):
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "csrf-test-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": True,
        })
        client = app.test_client()
        page = client.get("/login")
        parser = InputParser()
        parser.feed(page.get_data(as_text=True))
        client.post("/login", data={
            "correo": "admin.crud@edupass.test",
            "password": self.PASSWORD,
            "csrf_token": parser.value("csrf_token"),
        })
        return client

    def _insert_movement(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO movimientos (
                    alumno_id, tipo_movimiento, fecha_hora, area_id,
                    punto_plantel, usuario_id, dispositivo_id
                )
                VALUES (?, 'entrada', '2026-07-31T12:00:00+00:00',
                        NULL, 'acceso_principal', ?, NULL);
                """,
                (self.activo["alumno_id"], self.admin["usuario_id"]),
            )
            connection.commit()
        finally:
            connection.close()

    def test_01_visitante_es_redirigido(self):
        for method, path in (
            ("get", "/admin/alumnos/nuevo"),
            ("get", f"/admin/alumnos/{self.activo['alumno_id']}/editar"),
            ("post", f"/admin/alumnos/{self.activo['alumno_id']}/activar"),
            ("post", f"/admin/alumnos/{self.activo['alumno_id']}/desactivar"),
        ):
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

    def test_02_escaner_recibe_403(self):
        self._login("scanner.crud@edupass.test")
        for method, path in (
            ("get", "/admin/alumnos/nuevo"),
            ("get", f"/admin/alumnos/{self.activo['alumno_id']}/editar"),
            ("post", f"/admin/alumnos/{self.activo['alumno_id']}/activar"),
            ("post", f"/admin/alumnos/{self.activo['alumno_id']}/desactivar"),
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    getattr(self.client, method)(path).status_code,
                    403,
                )

    def test_03_administrador_abre_formulario_nuevo(self):
        self._login()
        response = self.client.get("/admin/alumnos/nuevo")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Registrar alumno", body)
        for field in (
            "nombre", "matricula", "grado", "grupo", "correo",
            "estado_acceso",
        ):
            self.assertIn(f'name="{field}"', body)
        self.assertIn("Datos escolares", body)
        self.assertIn("Acceso a EduPass", body)
        self.assertNotIn('name="rol"', body)
        self.assertNotIn('name="estado"', body)
        self.assertNotIn('name="fotografia"', body)

    def test_04_csrf_presente(self):
        client = self._csrf_client()
        body = client.get("/admin/alumnos/nuevo").get_data(as_text=True)
        self.assertIn('name="csrf_token"', body)

    def test_05_alta_valida(self):
        self._login()
        response = self.client.post("/admin/alumnos/nuevo", data=self._new_data())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count("alumnos"), 3)
        self.assertEqual(self._count("usuario_alumno"), 1)

    def test_06_estado_inicial_activo(self):
        self._login()
        self.client.post("/admin/alumnos/nuevo", data=self._new_data())
        row = self._query_one(
            "SELECT estado, fotografia FROM alumnos WHERE matricula = ?;",
            ("CRUD-003",),
        )
        self.assertEqual(row[0], "activo")
        self.assertIsNone(row[1])

    def test_07_matricula_normalizada_a_mayusculas(self):
        self._login()
        self.client.post("/admin/alumnos/nuevo", data=self._new_data())
        self.assertIsNotNone(
            self._query_one(
                "SELECT alumno_id FROM alumnos WHERE matricula = ?;",
                ("CRUD-003",),
            )
        )

    def test_08_campos_obligatorios(self):
        self._login()
        response = self.client.post(
            "/admin/alumnos/nuevo",
            data={"nombre": "", "matricula": "", "grado": "", "grupo": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Revisa los datos obligatorios del alumno.",
            response.get_data(as_text=True),
        )

    def test_09_matricula_duplicada(self):
        self._login()
        response = self.client.post(
            "/admin/alumnos/nuevo",
            data=self._new_data(matricula=" crud-001 "),
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn(
            "La matrícula ya está registrada.",
            response.get_data(as_text=True),
        )

    def test_10_mensaje_de_alta(self):
        self._login()
        response = self.client.post(
            "/admin/alumnos/nuevo",
            data=self._new_data(),
            follow_redirects=True,
        )
        self.assertIn(
            "Alumno y cuenta EduPass creados correctamente",
            response.get_data(as_text=True),
        )

    def test_11_alta_muestra_temporal_solo_en_respuesta(self):
        self._login()
        response = self.client.post("/admin/alumnos/nuevo", data=self._new_data())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Contraseña temporal", response.get_data(as_text=True))
        self.assertEqual(response.headers["Cache-Control"].split(",")[0], "no-store")
        self.assertEqual(self._count("alumnos"), 3)

    def test_12_formulario_edicion_precargado(self):
        self._login()
        response = self.client.get(
            f"/admin/alumnos/{self.activo['alumno_id']}/editar"
        )
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        for value in ("Alumno Activo", "CRUD-001", 'value="3"', 'value="A"'):
            self.assertIn(value, body)
        self.assertNotIn("alumno-activo.png", body)
        self.assertNotIn('name="estado"', body)

    def test_13_edicion_valida(self):
        self._login()
        response = self.client.post(
            f"/admin/alumnos/{self.activo['alumno_id']}/editar",
            data=self._edit_data(),
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Alumno actualizado correctamente.", response.get_data(as_text=True))
        row = self._query_one(
            "SELECT nombre, grado, grupo FROM alumnos WHERE alumno_id = ?;",
            (self.activo["alumno_id"],),
        )
        self.assertEqual(tuple(row), ("Alumno Actualizado", "6", "D"))

    def test_14_matricula_propia_permitida(self):
        self._login()
        response = self.client.post(
            f"/admin/alumnos/{self.activo['alumno_id']}/editar",
            data=self._edit_data(matricula=" crud-001 "),
        )
        self.assertEqual(response.status_code, 302)

    def test_15_matricula_otro_alumno_rechazada(self):
        self._login()
        response = self.client.post(
            f"/admin/alumnos/{self.activo['alumno_id']}/editar",
            data=self._edit_data(matricula="crud-002"),
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn(
            "La matrícula ya está registrada.",
            response.get_data(as_text=True),
        )

    def test_16_alumno_inexistente_404(self):
        self._login()
        response = self.client.get("/admin/alumnos/999999/editar")
        self.assertEqual(response.status_code, 404)
        self.assertIn(
            "No se encontró el alumno solicitado.",
            response.get_data(as_text=True),
        )

    def test_17_edicion_conserva_estado(self):
        self._login()
        self.client.post(
            f"/admin/alumnos/{self.inactivo['alumno_id']}/editar",
            data={
                "nombre": "Inactivo Editado",
                "matricula": "CRUD-002",
                "grado": "5",
                "grupo": "E",
            },
        )
        estado = self._query_one(
            "SELECT estado FROM alumnos WHERE alumno_id = ?;",
            (self.inactivo["alumno_id"],),
        )[0]
        self.assertEqual(estado, "inactivo")

    def test_18_edicion_conserva_fotografia_existente(self):
        self._login()
        response = self.client.post(
            f"/admin/alumnos/{self.activo['alumno_id']}/editar",
            data=self._edit_data(),
        )
        self.assertEqual(response.status_code, 302)
        fotografia = self._query_one(
            "SELECT fotografia FROM alumnos WHERE alumno_id = ?;",
            (self.activo["alumno_id"],),
        )[0]
        self.assertEqual(fotografia, "C:/privado/alumno-activo.png")

    def test_19_desactivacion_valida(self):
        self._login()
        response = self.client.post(
            f"/admin/alumnos/{self.activo['alumno_id']}/desactivar",
            follow_redirects=True,
        )
        self.assertIn("Alumno desactivado correctamente.", response.get_data(as_text=True))
        self.assertEqual(
            self._query_one(
                "SELECT estado FROM alumnos WHERE alumno_id = ?;",
                (self.activo["alumno_id"],),
            )[0],
            "inactivo",
        )

    def test_20_activacion_valida(self):
        self._login()
        response = self.client.post(
            f"/admin/alumnos/{self.inactivo['alumno_id']}/activar",
            follow_redirects=True,
        )
        self.assertIn("Alumno activado correctamente.", response.get_data(as_text=True))
        self.assertEqual(
            self._query_one(
                "SELECT estado FROM alumnos WHERE alumno_id = ?;",
                (self.inactivo["alumno_id"],),
            )[0],
            "activo",
        )

    def test_21_get_activar_devuelve_405(self):
        self._login()
        response = self.client.get(
            f"/admin/alumnos/{self.inactivo['alumno_id']}/activar"
        )
        self.assertEqual(response.status_code, 405)

    def test_22_get_desactivar_devuelve_405(self):
        self._login()
        response = self.client.get(
            f"/admin/alumnos/{self.activo['alumno_id']}/desactivar"
        )
        self.assertEqual(response.status_code, 405)

    def test_23_historial_conservado_al_desactivar(self):
        self._insert_movement()
        self._login()
        self.client.post(
            f"/admin/alumnos/{self.activo['alumno_id']}/desactivar"
        )
        response = self.client.get(
            f"/admin/historial/{self.activo['alumno_id']}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("entrada", response.get_data(as_text=True))

    def test_24_movimientos_conservados(self):
        self._insert_movement()
        self._login()
        self.client.post(
            f"/admin/alumnos/{self.activo['alumno_id']}/desactivar"
        )
        self.assertEqual(self._count("movimientos"), 1)

    def test_25_qr_y_datos_relacionados_no_se_eliminan(self):
        credencial_service.generar_credencial(
            self.activo["alumno_id"],
            self.database_path,
        )
        self._insert_movement()
        self._login()
        self.client.post(
            f"/admin/alumnos/{self.activo['alumno_id']}/desactivar"
        )
        self.assertEqual(self._count("alumnos"), 2)
        self.assertEqual(self._count("qr_tokens"), 1)
        self.assertEqual(self._count("movimientos"), 1)

    def test_26_no_existe_borrado_fisico(self):
        rules = list(self.app.url_map.iter_rules())
        self.assertTrue(all("DELETE" not in rule.methods for rule in rules))
        self._login()
        body = self.client.get("/admin/alumnos").get_data(as_text=True)
        self.assertNotIn("Eliminar", body)

    def test_27_error_repositorio_controlado(self):
        self._login()
        with patch.object(
            cuentas_alumno_service,
            "crear_alumno_con_cuenta",
            side_effect=RepositoryError("detalle privado"),
        ):
            response = self.client.post(
                "/admin/alumnos/nuevo",
                data=self._new_data(),
            )
        self.assertEqual(response.status_code, 500)
        self.assertIn(
            "No fue posible completar la operación en este momento.",
            response.get_data(as_text=True),
        )

    def test_28_sql_no_expuesto(self):
        self._login()
        with patch.object(
            cuentas_alumno_service,
            "crear_alumno_con_cuenta",
            side_effect=RepositoryError("SELECT secreto FROM alumnos"),
        ):
            body = self.client.post(
                "/admin/alumnos/nuevo",
                data=self._new_data(),
            ).get_data(as_text=True)
        self.assertNotIn("SELECT secreto", body)

    def test_29_ruta_sqlite_no_expuesta(self):
        self._login()
        with patch.object(
            cuentas_alumno_service,
            "crear_alumno_con_cuenta",
            side_effect=RepositoryError(str(self.database_path)),
        ):
            body = self.client.post(
                "/admin/alumnos/nuevo",
                data=self._new_data(),
            ).get_data(as_text=True)
        self.assertNotIn(str(self.database_path), body)
        self.assertNotIn(".sqlite", body)

    def test_30_traceback_no_expuesto(self):
        self._login()
        with patch.object(
            cuentas_alumno_service,
            "crear_alumno_con_cuenta",
            side_effect=RepositoryError("Traceback: dato privado"),
        ):
            body = self.client.post(
                "/admin/alumnos/nuevo",
                data=self._new_data(),
            ).get_data(as_text=True)
        self.assertNotIn("Traceback", body)

    def test_31_fotografia_no_expuesta(self):
        self._login()
        list_body = self.client.get("/admin/alumnos").get_data(as_text=True)
        edit_body = self.client.get(
            f"/admin/alumnos/{self.activo['alumno_id']}/editar"
        ).get_data(as_text=True)
        for body in (list_body, edit_body):
            self.assertNotIn("C:/privado/alumno-activo.png", body)
            self.assertNotIn('name="fotografia"', body)

    def test_32_escape_html(self):
        self._login()
        response = self.client.post(
            "/admin/alumnos/nuevo",
            data=self._new_data(
                nombre="<script>alert('x')</script>",
                matricula="SAFE-003",
            ),
            follow_redirects=True,
        )
        body = response.get_data(as_text=True)
        self.assertNotIn("<script>alert", body)
        self.assertNotIn("<script>alert", body)

    def test_33_vista_responsive(self):
        base = (
            PROJECT_ROOT / "src/edupass/web/templates/base.html"
        ).read_text(encoding="utf-8")
        css = (
            PROJECT_ROOT / "src/edupass/web/static/css/app.css"
        ).read_text(encoding="utf-8")
        self.assertIn('name="viewport"', base)
        self.assertIn("@media (max-width: 390px)", css)
        self.assertIn(".student-form-grid", css)
        self.assertIn(".student-row-actions", css)

    def test_34_acciones_usan_csrf(self):
        client = self._csrf_client()
        body = client.get("/admin/alumnos").get_data(as_text=True)
        for action in (
            f"/admin/alumnos/{self.activo['alumno_id']}/desactivar",
            f"/admin/alumnos/{self.inactivo['alumno_id']}/activar",
        ):
            pattern = (
                rf'<form method="post" action="{re.escape(action)}"'
                rf'.*?name="csrf_token"'
            )
            self.assertRegex(body, re.compile(pattern, re.DOTALL))

    def test_35_csrf_invalido_devuelve_400(self):
        client = self._csrf_client()
        response = client.post(
            "/admin/alumnos/nuevo",
            data=self._new_data(),
        )
        self.assertEqual(response.status_code, 400)

    def test_36_formulario_edicion_no_expone_identificador_editable(self):
        self._login()
        body = self.client.get(
            f"/admin/alumnos/{self.activo['alumno_id']}/editar"
        ).get_data(as_text=True)
        self.assertNotIn('name="alumno_id"', body)

    def test_37_estado_inexistente_devuelve_404(self):
        self._login()
        response = self.client.post("/admin/alumnos/999999/desactivar")
        self.assertEqual(response.status_code, 404)
        self.assertIn(
            "No se encontró el alumno solicitado.",
            response.get_data(as_text=True),
        )

    def test_38_edicion_aplica_post_redirect_get(self):
        self._login()
        response = self.client.post(
            f"/admin/alumnos/{self.activo['alumno_id']}/editar",
            data=self._edit_data(),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/alumnos"))

    def test_39_rol_manipulado_se_ignora_y_login_funciona(self):
        self._login()
        with patch.object(
            cuentas_alumno_service,
            "generar_password_temporal",
            return_value=self.PASSWORD,
        ):
            response = self.client.post(
                "/admin/alumnos/nuevo",
                data=self._new_data(rol="administrador"),
            )
        self.assertEqual(response.status_code, 200)
        row = self._query_one(
            """
            SELECT usuarios.correo, usuarios.estado, roles.nombre
            FROM usuarios
            INNER JOIN roles ON roles.rol_id = usuarios.rol_id
            WHERE usuarios.correo = ?;
            """,
            ("nueva.alumna@edupass.test",),
        )
        self.assertEqual(tuple(row), ("nueva.alumna@edupass.test", "activo", "alumno"))
        login_client = self.app.test_client()
        self.assertEqual(
            self._login(
                "nueva.alumna@edupass.test", client=login_client
            ).status_code,
            302,
        )
        self.assertEqual(
            login_client.get("/admin/alumnos/nuevo").status_code,
            403,
        )

    def test_40_rol_escaner_manipulado_se_ignora(self):
        self._login()
        self.client.post(
            "/admin/alumnos/nuevo",
            data=self._new_data(rol="escaner"),
        )
        role = self._query_one(
            """
            SELECT roles.nombre FROM usuarios
            INNER JOIN roles ON roles.rol_id = usuarios.rol_id
            WHERE usuarios.correo = ?;
            """,
            ("nueva.alumna@edupass.test",),
        )[0]
        self.assertEqual(role, "alumno")

    def test_41_cuenta_inactiva_no_inicia_sesion(self):
        self._login()
        with patch.object(
            cuentas_alumno_service,
            "generar_password_temporal",
            return_value=self.PASSWORD,
        ):
            self.client.post(
                "/admin/alumnos/nuevo",
                data=self._new_data(estado_acceso="inactivo"),
            )
        response = self._login(
            "nueva.alumna@edupass.test", client=self.app.test_client()
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "No fue posible iniciar sesion con las credenciales proporcionadas.",
            response.get_data(as_text=True),
        )

    def test_42_correo_duplicado_revierte_alumno(self):
        self._login()
        before = self._count("alumnos")
        response = self.client.post(
            "/admin/alumnos/nuevo",
            data=self._new_data(correo="admin.crud@edupass.test"),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self._count("alumnos"), before)

    def test_43_matricula_duplicada_no_crea_usuario(self):
        self._login()
        before = self._count("usuarios")
        response = self.client.post(
            "/admin/alumnos/nuevo",
            data=self._new_data(matricula="CRUD-001"),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self._count("usuarios"), before)


if __name__ == "__main__":
    unittest.main()
