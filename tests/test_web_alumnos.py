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
from edupass.shared.errors import RepositoryError
from edupass.web import create_app


class TestWebAlumnos(unittest.TestCase):
    PASSWORD = "ClaveWebSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "web_alumnos.sqlite"
        )
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-only-secret",
                "DATABASE_PATH": self.database_path,
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        usuarios_service.crear_usuario_demo(
            "Administradora Web",
            "admin@edupass.test",
            self.PASSWORD,
            "administrador",
            self.database_path,
        )
        usuarios_service.crear_usuario_demo(
            "Escaner Web",
            "scanner@edupass.test",
            self.PASSWORD,
            "escaner",
            self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _login(self, email="admin@edupass.test"):
        self.client.post(
            "/login",
            data={"correo": email, "password": self.PASSWORD},
        )

    def _sample_rows(self):
        return [
            {
                "alumno_id": 1,
                "nombre": "Ana Demo",
                "matricula": "EDU-001",
                "grado": "3",
                "grupo": "A",
                "fotografia": "C:/privado/ana.png",
                "estado": "activo",
            },
            {
                "alumno_id": 2,
                "nombre": "Luis Demo",
                "matricula": "EDU-002",
                "grado": "4",
                "grupo": "B",
                "fotografia": None,
                "estado": "inactivo",
            },
        ]

    def test_admin_list_calls_service_with_exact_database_path(self):
        self._login()
        with patch.object(
            alumnos_service,
            "listar_alumnos",
            return_value=self._sample_rows(),
        ) as mocked:
            response = self.client.get("/admin/alumnos")

        self.assertEqual(response.status_code, 200)
        mocked.assert_called_once_with(self.database_path)

    def test_list_shows_only_six_approved_columns_and_both_states(self):
        self._login()
        with patch.object(
            alumnos_service,
            "listar_alumnos",
            return_value=self._sample_rows(),
        ):
            body = self.client.get("/admin/alumnos").get_data(as_text=True)

        for heading in (
            "Nombre", "Matricula", "Grado / Grupo",
            "Estado escolar", "Acceso EduPass", "Acciones",
            "Credencial", "Historial",
        ):
            self.assertIn(f">{heading}<", body)
        self.assertNotIn(">ID<", body)
        self.assertNotIn(">Cuenta EduPass<", body)
        self.assertIn("Ana Demo", body)
        self.assertIn("activo", body)
        self.assertIn("inactivo", body)
        self.assertNotIn("fotografia", body.lower())
        self.assertNotIn("C:/privado/ana.png", body)

    def test_empty_list_has_clear_message(self):
        self._login()
        with patch.object(
            alumnos_service,
            "listar_alumnos",
            return_value=[],
        ):
            body = self.client.get("/admin/alumnos").get_data(as_text=True)

        self.assertIn("No hay alumnos registrados para mostrar.", body)

    def test_repository_error_has_controlled_message_without_details(self):
        self._login()
        with patch.object(
            alumnos_service,
            "listar_alumnos",
            side_effect=RepositoryError(
                "SELECT secreto FROM alumnos C:/base/privada.sqlite"
            ),
        ):
            response = self.client.get("/admin/alumnos")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "No fue posible consultar los alumnos en este momento.",
            body,
        )
        self.assertNotIn("SELECT secreto", body)
        self.assertNotIn("privada.sqlite", body)
        self.assertNotIn("Traceback", body)

    def test_list_offers_crud_actions_without_sensitive_fields(self):
        self._login()
        with patch.object(
            alumnos_service,
            "listar_alumnos",
            return_value=self._sample_rows(),
        ):
            body = self.client.get("/admin/alumnos").get_data(as_text=True)

        for expected in (
            "Registrar alumno",
            "Editar",
            "Activar",
            "Desactivar",
        ):
            self.assertIn(expected, body)
        for forbidden in (
            "password_hash",
            "SECRET_KEY",
            "C:/privado/ana.png",
            "Eliminar",
        ):
            self.assertNotIn(forbidden, body)

    def test_student_content_is_html_escaped(self):
        self._login()
        rows = self._sample_rows()
        rows[0]["nombre"] = "<script>alert('x')</script>"
        with patch.object(
            alumnos_service,
            "listar_alumnos",
            return_value=rows,
        ):
            body = self.client.get("/admin/alumnos").get_data(as_text=True)

        self.assertNotIn("<script>alert", body)
        self.assertIn("&lt;script&gt;", body)

    def test_scanner_cannot_access_student_list(self):
        self._login("scanner@edupass.test")

        response = self.client.get("/admin/alumnos")

        self.assertEqual(response.status_code, 403)

    def test_real_service_sqlite_route_integration(self):
        alumnos_service.registrar_alumno(
            "Ana Integracion",
            "INT-001",
            "3",
            "A",
            estado="activo",
            database_path=self.database_path,
        )
        alumnos_service.registrar_alumno(
            "Luis Integracion",
            "INT-002",
            "4",
            "B",
            estado="inactivo",
            database_path=self.database_path,
        )
        self._login()

        body = self.client.get("/admin/alumnos").get_data(as_text=True)

        self.assertIn("Ana Integracion", body)
        self.assertIn("Luis Integracion", body)
        self.assertIn("INT-001", body)
        self.assertIn("INT-002", body)
        self.assertNotIn("fotografia", body.lower())


if __name__ == "__main__":
    unittest.main()
