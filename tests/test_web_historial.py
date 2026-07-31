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
from edupass.persistence import database_manager
from edupass.shared.errors import RepositoryError
from edupass.web import create_app


class TestWebHistorial(unittest.TestCase):
    PASSWORD = "ClaveWebSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "web_historial.sqlite"
        )
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-only-secret",
            "DATABASE_PATH": self.database_path,
            "WTF_CSRF_ENABLED": False,
        })
        self.client = self.app.test_client()
        self.admin = usuarios_service.crear_usuario_demo(
            "Administradora Historial",
            "admin.historial@edupass.test",
            self.PASSWORD,
            "administrador",
            self.database_path,
        )
        self.scanner = usuarios_service.crear_usuario_demo(
            "Escaner Responsable",
            "scanner.secreto@edupass.test",
            self.PASSWORD,
            "escaner",
            self.database_path,
        )
        self.alumno = alumnos_service.registrar_alumno(
            "Alumno Historial",
            "HIS-WEB-0001",
            "3",
            "A",
            estado="activo",
            database_path=self.database_path,
        )
        self.otro_alumno = alumnos_service.registrar_alumno(
            "Otro Alumno",
            "HIS-WEB-0002",
            "4",
            "B",
            estado="activo",
            database_path=self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _login(self, role="admin"):
        email = (
            "admin.historial@edupass.test"
            if role == "admin"
            else "scanner.secreto@edupass.test"
        )
        return self.client.post("/login", data={
            "correo": email,
            "password": self.PASSWORD,
        })

    def _history_url(self, alumno_id=None, page=None):
        selected = alumno_id or self.alumno["alumno_id"]
        url = f"/admin/historial/{selected}"
        return f"{url}?page={page}" if page is not None else url

    def _insert_movements(self, count, alumno_id=None):
        selected = alumno_id or self.alumno["alumno_id"]
        connection = database_manager.get_connection(self.database_path)
        try:
            movement_ids = []
            for index in range(count):
                movement_type = "entrada" if index % 2 == 0 else "salida"
                cursor = connection.execute(
                    """
                    INSERT INTO movimientos (
                        alumno_id, tipo_movimiento, fecha_hora, area_id,
                        punto_plantel, usuario_id, dispositivo_id
                    ) VALUES (?, ?, ?, NULL, ?, ?, NULL);
                    """,
                    (
                        selected,
                        movement_type,
                        f"2026-07-30T18:{index:02d}:00.000000Z",
                        "acceso_principal",
                        self.scanner["usuario_id"],
                    ),
                )
                movement_ids.append(int(cursor.lastrowid))
            connection.commit()
            return movement_ids
        finally:
            connection.close()

    def test_01_visitante_es_redirigido(self):
        response = self.client.get("/admin/historial")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_02_escaner_recibe_403(self):
        self._login("scanner")
        self.assertEqual(self.client.get("/admin/historial").status_code, 403)

    def test_03_administrador_accede(self):
        self._login()
        response = self.client.get("/admin/historial")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Historial de movimientos", response.get_data(as_text=True))

    def test_04_navegacion_contiene_historial(self):
        self._login()
        body = self.client.get("/admin").get_data(as_text=True)
        self.assertIn('href="/admin/historial"', body)
        self.assertIn(">Historial</a>", body)

    def test_05_selector_muestra_alumnos(self):
        self._login()
        body = self.client.get("/admin/historial").get_data(as_text=True)
        self.assertIn("Alumno Historial", body)
        self.assertIn("HIS-WEB-0001", body)
        self.assertIn("Ver historial", body)

    def test_06_alumno_existente_sin_movimientos(self):
        self._login()
        response = self.client.get(self._history_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Alumno Historial", response.get_data(as_text=True))

    def test_07_mensaje_vacio_exacto(self):
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertIn("No hay movimientos registrados para este alumno.", body)

    def test_08_alumno_con_entrada(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertIn(">Entrada<", body)

    def test_09_alumno_con_salida(self):
        self._insert_movements(2)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertIn(">Salida<", body)

    def test_10_orden_mas_reciente_primero(self):
        self._insert_movements(2)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertLess(body.find("18:01:00"), body.find("18:00:00"))

    def test_11_tipo_presentado_correctamente(self):
        self._insert_movements(2)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertIn(">Entrada<", body)
        self.assertIn(">Salida<", body)
        self.assertNotIn(">entrada<", body)

    def test_12_punto_presentado_correctamente(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertIn("Acceso principal", body)
        self.assertNotIn("acceso_principal", body)

    def test_13_responsable_presentado(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertIn("Escaner Responsable", body)

    def test_14_detalle_valido(self):
        movement_id = self._insert_movements(1)[0]
        self._login()
        response = self.client.get(
            f"{self._history_url()}/movimientos/{movement_id}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn(f"Movimiento {movement_id}", body)
        self.assertIn("Escaner Responsable", body)

    def test_15_movimiento_inexistente_404(self):
        self._login()
        response = self.client.get(
            f"{self._history_url()}/movimientos/999999"
        )
        self.assertEqual(response.status_code, 404)

    def test_16_alumno_inexistente_404(self):
        self._login()
        self.assertEqual(
            self.client.get("/admin/historial/999999").status_code,
            404,
        )

    def test_17_movimiento_de_otro_alumno_404(self):
        movement_id = self._insert_movements(
            1,
            self.otro_alumno["alumno_id"],
        )[0]
        self._login()
        response = self.client.get(
            f"{self._history_url()}/movimientos/{movement_id}"
        )
        self.assertEqual(response.status_code, 404)

    def test_18_pagina_cero_400(self):
        self._login()
        self.assertEqual(
            self.client.get(self._history_url(page=0)).status_code,
            400,
        )

    def test_19_pagina_inexistente_404(self):
        self._insert_movements(51)
        self._login()
        self.assertEqual(
            self.client.get(self._history_url(page=3)).status_code,
            404,
        )

    def test_20_paginacion_con_51_registros(self):
        self._insert_movements(51)
        self._login()
        first = self.client.get(self._history_url()).get_data(as_text=True)
        second = self.client.get(self._history_url(page=2)).get_data(as_text=True)
        self.assertIn("Pagina 1 de 2", first)
        self.assertIn("Siguiente", first)
        self.assertIn("Pagina 2 de 2", second)
        self.assertIn("Anterior", second)

    def test_21_error_de_repositorio_controlado(self):
        self._login()
        with patch(
            "edupass.web.admin_routes.historial_service."
            "consultar_historial_alumno",
            side_effect=RepositoryError("SELECT secreto"),
        ):
            response = self.client.get(self._history_url())
        self.assertEqual(response.status_code, 500)
        body = response.get_data(as_text=True)
        self.assertIn("No fue posible consultar el historial.", body)
        self.assertNotIn("SELECT secreto", body)

    def test_22_no_token(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertNotIn("token", body.lower())

    def test_23_no_hash(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertNotIn("hash", body.lower())

    def test_24_no_password_hash(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertNotIn("password_hash", body)

    def test_25_no_correo_del_escaner(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertNotIn("scanner.secreto@edupass.test", body)

    def test_26_no_fotografia(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertNotIn("fotografia", body.lower())

    def test_27_no_sql(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertNotIn("SELECT ", body)
        self.assertNotIn("INSERT ", body)

    def test_28_no_ruta_sqlite(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertNotIn(str(self.database_path), body)
        self.assertNotIn(".sqlite", body)

    def test_29_no_traceback(self):
        self._login()
        with patch(
            "edupass.web.admin_routes.historial_service."
            "consultar_historial_alumno",
            side_effect=RepositoryError("fallo interno"),
        ):
            body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertNotIn("Traceback", body)
        self.assertNotIn("fallo interno", body)

    def test_30_encabezado_cache_control_no_store(self):
        self._login()
        response = self.client.get(self._history_url())
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_31_tabla_responsive(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertIn('class="table-scroll history-table"', body)

    def test_32_sin_botones_editar_o_eliminar(self):
        self._insert_movements(1)
        self._login()
        body = self.client.get(self._history_url()).get_data(as_text=True)
        self.assertNotIn(">Editar<", body)
        self.assertNotIn(">Eliminar<", body)

    def test_33_enlace_desde_listado_de_alumnos(self):
        self._login()
        body = self.client.get("/admin/alumnos").get_data(as_text=True)
        self.assertIn(self._history_url(), body)
        self.assertIn("Ver historial", body)

    def test_34_enlace_desde_panel_administrador(self):
        self._login()
        body = self.client.get("/admin").get_data(as_text=True)
        self.assertIn("Historial de movimientos", body)
        self.assertIn('href="/admin/historial"', body)

    def test_35_rol_administrador_obligatorio(self):
        movement_id = self._insert_movements(1)[0]
        self._login("scanner")
        routes = (
            "/admin/historial",
            self._history_url(),
            f"{self._history_url()}/movimientos/{movement_id}",
        )
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 403)


if __name__ == "__main__":
    unittest.main()
