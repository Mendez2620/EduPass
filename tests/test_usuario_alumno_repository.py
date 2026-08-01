from concurrent.futures import ThreadPoolExecutor
import inspect
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
SCHEMA_PATH = SRC_PATH / "edupass" / "persistence" / "schema.sql"
sys.path.insert(0, str(SRC_PATH))

from edupass.modules.auth import roles_service
from edupass.persistence import database_manager
from edupass.persistence.repositories import (
    alumno_repository,
    usuario_alumno_repository,
    usuario_repository,
)
from edupass.shared.constants import (
    ESTADO_ACTIVO,
    ESTADO_INACTIVO,
    ROL_ADMINISTRADOR,
    ROL_ALUMNO,
    ROL_ESCANER,
)
from edupass.shared.errors import (
    AlumnoNoEncontradoError,
    AlumnoYaTieneUsuarioError,
    ConsultaSqlError,
    RepositoryError,
    UsuarioAlumnoYaVinculadoError,
    UsuarioNoEncontradoError,
    UsuarioNoEsAlumnoError,
    ValidationError,
)


class TestUsuarioAlumnoRepository(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "usuario_alumno.sqlite"
        )
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        roles = roles_service.asegurar_roles_sistema(self.database_path)
        self.role_ids = {item["nombre"]: item["rol_id"] for item in roles}
        self.sequence = 0
        self.user_id = self._create_user(ROL_ALUMNO)
        self.student_id = self._create_student()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _create_user(self, role=ROL_ALUMNO, state=ESTADO_ACTIVO):
        self.sequence += 1
        return usuario_repository.crear(
            f"Usuario {self.sequence}",
            f"usuario{self.sequence}@edupass.test",
            generate_password_hash("Password123!"),
            state,
            self.role_ids[role],
            self.database_path,
        )

    def _create_student(self, state=ESTADO_ACTIVO):
        self.sequence += 1
        return alumno_repository.crear_alumno(
            f"Alumno {self.sequence}",
            f"MAT-{self.sequence:04d}",
            "1",
            "A",
            "foto-privada.png",
            state,
            self.database_path,
        )

    def _count_links(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(
                "SELECT COUNT(*) FROM usuario_alumno;"
            ).fetchone()[0]
        finally:
            connection.close()

    def _concurrent_results(self, calls):
        barrier = threading.Barrier(len(calls) + 1)

        def execute(call):
            barrier.wait()
            try:
                return usuario_alumno_repository.vincular(
                    call[0], call[1], self.database_path
                )
            except Exception as exc:
                return exc

        with ThreadPoolExecutor(max_workers=len(calls)) as executor:
            futures = [executor.submit(execute, call) for call in calls]
            barrier.wait()
            return [future.result(timeout=10) for future in futures]

    def test_valid_link(self):
        result = usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        self.assertEqual(result["usuario_id"], self.user_id)
        self.assertEqual(result["alumno_id"], self.student_id)

    def test_safe_result_has_only_approved_fields(self):
        result = usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        self.assertEqual(
            set(result),
            {
                "usuario_alumno_id", "usuario_id", "alumno_id",
                "usuario_nombre", "correo", "usuario_estado", "rol_nombre",
                "alumno_nombre", "matricula", "grado", "grupo", "alumno_estado",
            },
        )

    def test_get_by_user(self):
        created = usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        self.assertEqual(
            usuario_alumno_repository.obtener_por_usuario(
                self.user_id, self.database_path
            ),
            created,
        )

    def test_get_by_student(self):
        created = usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        self.assertEqual(
            usuario_alumno_repository.obtener_por_alumno(
                self.student_id, self.database_path
            ),
            created,
        )

    def test_missing_user(self):
        with self.assertRaisesRegex(
            UsuarioNoEncontradoError, "No se encontro el usuario solicitado"
        ):
            usuario_alumno_repository.vincular(
                999999, self.student_id, self.database_path
            )

    def test_missing_student(self):
        with self.assertRaisesRegex(
            AlumnoNoEncontradoError, "No se encontro el alumno solicitado"
        ):
            usuario_alumno_repository.vincular(
                self.user_id, 999999, self.database_path
            )

    def test_administrator_is_rejected(self):
        admin_id = self._create_user(ROL_ADMINISTRADOR)
        with self.assertRaisesRegex(
            UsuarioNoEsAlumnoError, "El usuario no tiene el rol alumno"
        ):
            usuario_alumno_repository.vincular(
                admin_id, self.student_id, self.database_path
            )

    def test_scanner_is_rejected(self):
        scanner_id = self._create_user(ROL_ESCANER)
        with self.assertRaises(UsuarioNoEsAlumnoError):
            usuario_alumno_repository.vincular(
                scanner_id, self.student_id, self.database_path
            )

    def test_student_role_is_allowed(self):
        result = usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        self.assertEqual(result["rol_nombre"], ROL_ALUMNO)

    def test_same_user_cannot_be_linked_twice(self):
        usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        with self.assertRaisesRegex(
            UsuarioAlumnoYaVinculadoError,
            "El usuario ya está vinculado a un alumno",
        ):
            usuario_alumno_repository.vincular(
                self.user_id, self._create_student(), self.database_path
            )

    def test_same_student_cannot_be_linked_twice(self):
        usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        with self.assertRaisesRegex(
            AlumnoYaTieneUsuarioError,
            "El alumno ya tiene una cuenta vinculada",
        ):
            usuario_alumno_repository.vincular(
                self._create_user(), self.student_id, self.database_path
            )

    def test_two_distinct_pairs_can_be_linked(self):
        usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        usuario_alumno_repository.vincular(
            self._create_user(), self._create_student(), self.database_path
        )
        self.assertEqual(self._count_links(), 2)

    def test_zero_ids_are_rejected(self):
        for values in ((0, self.student_id), (self.user_id, 0)):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                usuario_alumno_repository.vincular(*values, self.database_path)

    def test_negative_ids_are_rejected(self):
        for values in ((-1, self.student_id), (self.user_id, -1)):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                usuario_alumno_repository.vincular(*values, self.database_path)

    def test_boolean_ids_are_rejected(self):
        for values in ((True, self.student_id), (self.user_id, False)):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                usuario_alumno_repository.vincular(*values, self.database_path)

    def test_non_integer_ids_are_rejected(self):
        for value in ("1", 1.0, None, object()):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                usuario_alumno_repository.obtener_por_usuario(
                    value, self.database_path
                )

    def test_failure_after_insert_rolls_back(self):
        original = usuario_alumno_repository._load_query

        def load_query(file_name):
            if file_name == "select_usuario_alumno_detail.sql":
                return "SELECT dato FROM tabla_inexistente WHERE dato = ?;"
            return original(file_name)

        with patch.object(
            usuario_alumno_repository, "_load_query", side_effect=load_query
        ):
            with self.assertRaises(RepositoryError):
                usuario_alumno_repository.vincular(
                    self.user_id, self.student_id, self.database_path
                )
        self.assertEqual(self._count_links(), 0)

    def test_no_link_remains_after_role_failure(self):
        with self.assertRaises(UsuarioNoEsAlumnoError):
            usuario_alumno_repository.vincular(
                self._create_user(ROL_ADMINISTRADOR),
                self.student_id,
                self.database_path,
            )
        self.assertEqual(self._count_links(), 0)

    def test_concurrency_same_user_has_one_success(self):
        results = self._concurrent_results(
            [
                (self.user_id, self.student_id),
                (self.user_id, self._create_student()),
            ]
        )
        self.assertEqual(sum(isinstance(item, dict) for item in results), 1)
        self.assertEqual(
            sum(isinstance(item, UsuarioAlumnoYaVinculadoError) for item in results),
            1,
        )

    def test_concurrency_same_student_has_one_success(self):
        results = self._concurrent_results(
            [
                (self.user_id, self.student_id),
                (self._create_user(), self.student_id),
            ]
        )
        self.assertEqual(sum(isinstance(item, dict) for item in results), 1)
        self.assertEqual(
            sum(isinstance(item, AlumnoYaTieneUsuarioError) for item in results),
            1,
        )

    def test_concurrency_persists_exactly_one_link(self):
        self._concurrent_results(
            [
                (self.user_id, self.student_id),
                (self.user_id, self._create_student()),
            ]
        )
        self.assertEqual(self._count_links(), 1)

    def test_result_has_no_password_hash(self):
        result = usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        self.assertNotIn("password_hash", result)

    def test_result_has_no_photograph(self):
        result = usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        self.assertNotIn("fotografia", result)

    def test_result_has_no_token_or_qr(self):
        result = usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        for key in result:
            self.assertNotIn("token", key.lower())
            self.assertNotIn("qr", key.lower())

    def test_sql_files_are_parameterized_and_explicit(self):
        sql_directory = usuario_alumno_repository._SQL_DIRECTORY
        for path in sql_directory.glob("*.sql"):
            with self.subTest(path=path.name):
                query = path.read_text(encoding="utf-8")
                self.assertNotIn("SELECT *", query.upper())
                self.assertNotIn("%s", query)
                self.assertIn("?", query)

    def test_missing_sql_file_is_controlled(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                usuario_alumno_repository, "_SQL_DIRECTORY", Path(directory)
            ):
                with self.assertRaises(ConsultaSqlError):
                    usuario_alumno_repository.obtener_por_usuario(
                        self.user_id, self.database_path
                    )

    def test_empty_sql_file_is_controlled(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "select_usuario_alumno_by_usuario.sql"
            path.write_text("   ", encoding="utf-8")
            with patch.object(
                usuario_alumno_repository, "_SQL_DIRECTORY", Path(directory)
            ):
                with self.assertRaises(ConsultaSqlError):
                    usuario_alumno_repository.obtener_por_usuario(
                        self.user_id, self.database_path
                    )

    def test_database_failure_becomes_repository_error(self):
        error = database_manager.DatabaseManagerError("detalle privado")
        with patch.object(
            database_manager, "get_connection", side_effect=error
        ):
            with self.assertRaisesRegex(
                RepositoryError, "No se pudo consultar la vinculacion"
            ):
                usuario_alumno_repository.obtener_por_usuario(
                    self.user_id, self.database_path
                )

    def test_cursor_is_closed(self):
        real_connection = database_manager.get_connection(self.database_path)
        cursors = []

        class CursorProxy:
            def __init__(self, cursor):
                self.cursor = cursor
                self.closed = False
            def __getattr__(self, name):
                return getattr(self.cursor, name)
            def close(self):
                self.closed = True
                self.cursor.close()

        class ConnectionProxy:
            def __init__(self, connection):
                object.__setattr__(self, "connection", connection)
                object.__setattr__(self, "closed", False)
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def __setattr__(self, name, value):
                if name in {"connection", "closed"}:
                    object.__setattr__(self, name, value)
                else:
                    setattr(self.connection, name, value)
            def execute(self, *args):
                cursor = CursorProxy(self.connection.execute(*args))
                cursors.append(cursor)
                return cursor
            def close(self):
                self.closed = True
                self.connection.close()

        proxy = ConnectionProxy(real_connection)
        with patch.object(database_manager, "get_connection", return_value=proxy):
            usuario_alumno_repository.obtener_por_usuario(
                self.user_id, self.database_path
            )
        self.assertTrue(cursors)
        self.assertTrue(all(cursor.closed for cursor in cursors))

    def test_connection_is_closed(self):
        real_connection = database_manager.get_connection(self.database_path)

        class ConnectionProxy:
            def __init__(self, connection):
                object.__setattr__(self, "connection", connection)
                object.__setattr__(self, "closed", False)
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def __setattr__(self, name, value):
                if name in {"connection", "closed"}:
                    object.__setattr__(self, name, value)
                else:
                    setattr(self.connection, name, value)
            def close(self):
                self.closed = True
                self.connection.close()

        proxy = ConnectionProxy(real_connection)
        with patch.object(database_manager, "get_connection", return_value=proxy):
            usuario_alumno_repository.obtener_por_usuario(
                self.user_id, self.database_path
            )
        self.assertTrue(proxy.closed)

    def test_inactive_student_can_be_linked(self):
        student_id = self._create_student(ESTADO_INACTIVO)
        result = usuario_alumno_repository.vincular(
            self.user_id, student_id, self.database_path
        )
        self.assertEqual(result["alumno_estado"], ESTADO_INACTIVO)

    def test_inactive_user_can_be_linked(self):
        user_id = self._create_user(ROL_ALUMNO, ESTADO_INACTIVO)
        result = usuario_alumno_repository.vincular(
            user_id, self.student_id, self.database_path
        )
        self.assertEqual(result["usuario_estado"], ESTADO_INACTIVO)

    def test_no_delete_or_unlink_api_exists(self):
        for name in ("borrar", "eliminar", "desvincular", "cambiar_alumno", "cambiar_usuario"):
            self.assertFalse(hasattr(usuario_alumno_repository, name))

    def test_link_does_not_modify_movements(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute(
                "INSERT INTO movimientos "
                "(alumno_id, tipo_movimiento, fecha_hora, usuario_id) "
                "VALUES (?, ?, ?, ?);",
                (self.student_id, "entrada", "2026-01-01", self.user_id),
            )
            connection.commit()
        finally:
            connection.close()
        usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        connection = database_manager.get_connection(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM movimientos;").fetchone()[0],
                1,
            )
        finally:
            connection.close()

    def test_link_does_not_modify_qr(self):
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute(
                "INSERT INTO qr_tokens "
                "(alumno_id, token_hash, generado_en, expira_en, estado) "
                "VALUES (?, ?, ?, ?, ?);",
                (self.student_id, "hash-qr", "2026-01-01", "2026-01-02", "activo"),
            )
            connection.commit()
        finally:
            connection.close()
        usuario_alumno_repository.vincular(
            self.user_id, self.student_id, self.database_path
        )
        connection = database_manager.get_connection(self.database_path)
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM qr_tokens;").fetchone()[0],
                1,
            )
        finally:
            connection.close()

    def test_link_uses_begin_immediate_without_sleep(self):
        source = inspect.getsource(usuario_alumno_repository.vincular)
        self.assertIn('connection.execute("BEGIN IMMEDIATE;")', source)
        self.assertNotIn("sleep(", source)

    def test_link_uses_one_connection_and_one_commit(self):
        real_connection = database_manager.get_connection(self.database_path)

        class ConnectionProxy:
            def __init__(self, connection):
                object.__setattr__(self, "connection", connection)
                object.__setattr__(self, "commits", 0)
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def __setattr__(self, name, value):
                if name in {"connection", "commits"}:
                    object.__setattr__(self, name, value)
                else:
                    setattr(self.connection, name, value)
            def commit(self):
                self.commits += 1
                self.connection.commit()

        proxy = ConnectionProxy(real_connection)
        with patch.object(
            database_manager, "get_connection", return_value=proxy
        ) as get_connection:
            usuario_alumno_repository.vincular(
                self.user_id, self.student_id, self.database_path
            )
        self.assertEqual(get_connection.call_count, 1)
        self.assertEqual(proxy.commits, 1)

    def test_repository_uses_only_temporary_database(self):
        self.assertNotEqual(
            self.database_path.resolve(),
            database_manager.get_database_path().resolve(),
        )


if __name__ == "__main__":
    unittest.main()