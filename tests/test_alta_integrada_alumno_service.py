from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.alumnos import cuentas_alumno_service
from edupass.modules.auth import roles_service, usuarios_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import usuario_alumno_repository
from edupass.shared.errors import (
    AlumnoInactivoError,
    DuplicateUserError,
    MatriculaDuplicadaError,
    RepositoryError,
)


class TestAltaIntegradaAlumnoService(unittest.TestCase):
    PASSWORD = "ClaveIntegrada123!"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "integrada.sqlite"
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        roles_service.asegurar_roles_sistema(self.database_path)
        self.admin = usuarios_service.crear_usuario_demo(
            "Admin", "admin.integrada@edupass.test", self.PASSWORD,
            "administrador", self.database_path,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _create(self, **changes):
        data = {
            "nombre": "Alumna Integrada",
            "matricula": "INT-001",
            "grado": "4",
            "grupo": "B",
            "fotografia": None,
            "alumno_estado": "activo",
            "correo": "alumna.integrada@edupass.test",
            "password": self.PASSWORD,
            "cuenta_estado": "activo",
            "actor_usuario_id": self.admin["usuario_id"],
            "database_path": self.database_path,
        }
        data.update(changes)
        return cuentas_alumno_service.crear_alumno_con_cuenta(**data)

    def _count(self, table):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
        finally:
            connection.close()

    def test_crea_alumno_usuario_y_vinculo_con_rol_fijo(self):
        account = self._create()
        self.assertEqual(account["rol_nombre"], "alumno")
        self.assertEqual(account["usuario_estado"], "activo")
        self.assertEqual(self._count("alumnos"), 1)
        self.assertEqual(self._count("usuario_alumno"), 1)

    def test_password_se_almacena_solo_como_hash(self):
        account = self._create()
        connection = database_manager.get_connection(self.database_path)
        try:
            stored = connection.execute(
                "SELECT password_hash FROM usuarios WHERE usuario_id = ?;",
                (account["usuario_id"],),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertNotEqual(stored, self.PASSWORD)
        self.assertTrue(check_password_hash(stored, self.PASSWORD))
        self.assertNotIn("password_hash", account)

    def test_permite_cuenta_inactiva(self):
        account = self._create(cuenta_estado="inactivo")
        self.assertEqual(account["usuario_estado"], "inactivo")

    def test_rechaza_cuenta_activa_para_alumno_inactivo_sin_escribir(self):
        with self.assertRaises(AlumnoInactivoError):
            self._create(alumno_estado="inactivo")
        self.assertEqual(self._count("alumnos"), 0)

    def test_correo_duplicado_revierte_todo(self):
        with self.assertRaises(DuplicateUserError):
            self._create(correo="admin.integrada@edupass.test")
        self.assertEqual(self._count("alumnos"), 0)
        self.assertEqual(self._count("usuario_alumno"), 0)

    def test_matricula_duplicada_no_deja_usuario_huerfano(self):
        self._create()
        users_before = self._count("usuarios")
        with self.assertRaises(MatriculaDuplicadaError):
            self._create(
                correo="otra@edupass.test",
                matricula=" int-001 ",
            )
        self.assertEqual(self._count("usuarios"), users_before)
        self.assertEqual(self._count("alumnos"), 1)

    def test_error_al_insertar_usuario_revierte_alumno(self):
        original = usuario_alumno_repository._execute

        def fail_user(connection, cursors, query, parameters=()):
            if query.lstrip().startswith("INSERT INTO usuarios"):
                raise sqlite3.OperationalError("fallo simulado")
            return original(connection, cursors, query, parameters)

        with patch.object(usuario_alumno_repository, "_execute", side_effect=fail_user):
            with self.assertRaises(RepositoryError):
                self._create()
        self.assertEqual(self._count("alumnos"), 0)
        self.assertEqual(self._count("usuarios"), 1)

    def test_error_al_vincular_revierte_alumno_y_usuario(self):
        original = usuario_alumno_repository._execute

        def fail_link(connection, cursors, query, parameters=()):
            if query.lstrip().startswith("INSERT INTO usuario_alumno"):
                raise sqlite3.OperationalError("fallo simulado")
            return original(connection, cursors, query, parameters)

        with patch.object(usuario_alumno_repository, "_execute", side_effect=fail_link):
            with self.assertRaises(RepositoryError):
                self._create()
        self.assertEqual(self._count("alumnos"), 0)
        self.assertEqual(self._count("usuarios"), 1)
        self.assertEqual(self._count("usuario_alumno"), 0)

    def test_usa_begin_immediate(self):
        calls = []
        original = usuario_alumno_repository._execute

        def record(connection, cursors, query, parameters=()):
            calls.append(query.strip())
            return original(connection, cursors, query, parameters)

        with patch.object(usuario_alumno_repository, "_execute", side_effect=record):
            self._create()
        self.assertEqual(calls[0], "BEGIN IMMEDIATE;")


if __name__ == "__main__":
    unittest.main()
