from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.persistence import database_manager
from edupass.persistence.repositories import (
    rol_repository,
    usuario_repository,
)
from edupass.shared.errors import (
    ConsultaSqlError,
    DuplicateUserError,
    RepositoryError,
)


class TestUsuarioRepository(unittest.TestCase):
    PASSWORD = "ClaveSegura123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "usuarios_test.sqlite"
        )
        database_manager.initialize_database(
            self.database_path,
            SCHEMA_PATH,
        )
        self.rol = rol_repository.crear_si_no_existe(
            "administrador",
            database_path=self.database_path,
        )
        self.password_hash = generate_password_hash(self.PASSWORD)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _crear_usuario(self, **changes):
        data = {
            "nombre": "Administrador Demo",
            "correo": "admin@edupass.test",
            "password_hash": self.password_hash,
            "estado": "activo",
            "rol_id": self.rol["rol_id"],
        }
        data.update(changes)
        return usuario_repository.crear(
            database_path=self.database_path,
            **data,
        )

    def test_crear_usuario_valido(self):
        usuario_id = self._crear_usuario()
        usuario = usuario_repository.obtener_por_id(
            usuario_id,
            self.database_path,
        )

        self.assertGreater(usuario_id, 0)
        self.assertEqual(usuario["nombre"], "Administrador Demo")
        self.assertEqual(usuario["correo"], "admin@edupass.test")
        self.assertEqual(usuario["estado"], "activo")

    def test_contrasena_se_guarda_en_password_hash(self):
        usuario_id = self._crear_usuario()
        usuario = usuario_repository.obtener_por_id(
            usuario_id,
            self.database_path,
        )

        self.assertNotEqual(usuario["password_hash"], self.PASSWORD)
        self.assertTrue(
            check_password_hash(usuario["password_hash"], self.PASSWORD)
        )

    def test_obtener_por_correo(self):
        usuario_id = self._crear_usuario()

        usuario = usuario_repository.obtener_por_correo(
            "admin@edupass.test",
            self.database_path,
        )

        self.assertEqual(usuario["usuario_id"], usuario_id)

    def test_obtener_por_correo_normalizado(self):
        self._crear_usuario(correo="  ADMIN@EDUPASS.TEST  ")

        usuario = usuario_repository.obtener_por_correo(
            "  Admin@EduPass.Test ",
            self.database_path,
        )

        self.assertEqual(usuario["correo"], "admin@edupass.test")

    def test_obtener_por_id(self):
        usuario_id = self._crear_usuario()

        usuario = usuario_repository.obtener_por_id(
            usuario_id,
            self.database_path,
        )

        self.assertEqual(usuario["usuario_id"], usuario_id)

    def test_usuario_inexistente_devuelve_none(self):
        self.assertIsNone(
            usuario_repository.obtener_por_id(9999, self.database_path)
        )
        self.assertIsNone(
            usuario_repository.obtener_por_correo(
                "noexiste@edupass.test",
                self.database_path,
            )
        )

    def test_correo_duplicado_genera_error_controlado(self):
        self._crear_usuario()

        with self.assertRaises(DuplicateUserError):
            self._crear_usuario(nombre="Otro Administrador")

    def test_rol_inexistente_viola_fk_de_forma_controlada(self):
        with self.assertRaises(RepositoryError) as context:
            self._crear_usuario(rol_id=9999)

        self.assertIsInstance(context.exception.__cause__, sqlite3.IntegrityError)

    def test_consultas_incluyen_datos_del_rol(self):
        usuario_id = self._crear_usuario()

        usuario = usuario_repository.obtener_por_id(
            usuario_id,
            self.database_path,
        )

        self.assertEqual(usuario["rol_id"], self.rol["rol_id"])
        self.assertEqual(usuario["rol_nombre"], "administrador")
        self.assertEqual(
            set(usuario),
            {
                "usuario_id",
                "nombre",
                "correo",
                "password_hash",
                "estado",
                "rol_id",
                "rol_nombre",
            },
        )

    def test_commit_conserva_el_usuario_en_otra_conexion(self):
        usuario_id = self._crear_usuario()

        connection = database_manager.get_connection(self.database_path)
        try:
            row = connection.execute(
                "SELECT correo FROM usuarios WHERE usuario_id = ?;",
                (usuario_id,),
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(row[0], "admin@edupass.test")

    def test_rollback_no_agrega_usuario_duplicado(self):
        self._crear_usuario()
        with self.assertRaises(DuplicateUserError):
            self._crear_usuario(nombre="Duplicado")

        connection = database_manager.get_connection(self.database_path)
        try:
            cantidad = connection.execute(
                "SELECT COUNT(*) FROM usuarios;"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual(cantidad, 1)

    def test_error_sqlite_se_traduce_a_repository_error(self):
        original = sqlite3.OperationalError("fallo controlado")
        with patch.object(
            usuario_repository.database_manager,
            "get_connection",
            side_effect=original,
        ):
            with self.assertRaises(RepositoryError) as context:
                usuario_repository.obtener_por_id(1, self.database_path)

        self.assertIs(context.exception.__cause__, original)
        self.assertNotIn("SELECT", str(context.exception).upper())

    def test_sql_faltante_se_traduce_segun_patron_existente(self):
        with patch.object(
            usuario_repository,
            "_SELECT_BY_ID_FILE",
            "consulta_inexistente.sql",
        ):
            with self.assertRaises(ConsultaSqlError):
                usuario_repository.obtener_por_id(1, self.database_path)

    def test_repositorio_rechaza_contrasena_en_texto_plano(self):
        with self.assertRaises(RepositoryError):
            self._crear_usuario(password_hash=self.PASSWORD)

        connection = database_manager.get_connection(self.database_path)
        try:
            cantidad = connection.execute(
                "SELECT COUNT(*) FROM usuarios;"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(cantidad, 0)


if __name__ == "__main__":
    unittest.main()
