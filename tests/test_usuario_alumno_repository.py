from concurrent.futures import ThreadPoolExecutor
import inspect
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash


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
    AlumnoInactivoError,
    AlumnoNoEncontradoError,
    AlumnoYaTieneUsuarioError,
    AuthorizationError,
    DuplicateUserError,
    ConsultaSqlError,
    RepositoryError,
    UsuarioAlumnoYaVinculadoError,
    UsuarioNoEncontradoError,
    UsuarioNoEsAlumnoError,
    ValidationError,
    VinculoUsuarioAlumnoNoEncontradoError,
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


class TestCuentaAlumnoManagementRepository(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "cuentas.sqlite"
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        roles = roles_service.asegurar_roles_sistema(self.database_path)
        self.role_ids = {item["nombre"]: item["rol_id"] for item in roles}
        self.sequence = 0
        self.admin_id = self._user(ROL_ADMINISTRADOR)
        self.student_id = self._student()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _user(self, role=ROL_ALUMNO, state=ESTADO_ACTIVO, email=None):
        self.sequence += 1
        return usuario_repository.crear(
            f"Usuario {self.sequence}",
            email or f"cuenta{self.sequence}@edupass.test",
            generate_password_hash("Password123!"),
            state,
            self.role_ids[role],
            self.database_path,
        )

    def _student(self, state=ESTADO_ACTIVO, name=None):
        self.sequence += 1
        return alumno_repository.crear_alumno(
            name or f"Alumno {self.sequence}",
            f"CTA-{self.sequence}",
            "2", "B", "privada.png", state, self.database_path,
        )

    def _create_account(self, student_id=None, email=None, actor_id=None):
        return usuario_alumno_repository.crear_cuenta_vinculada(
            student_id or self.student_id,
            email or f"alumno{self.sequence}@edupass.test",
            generate_password_hash("Password123!"),
            actor_id or self.admin_id,
            self.database_path,
        )

    def _count_users_by_email(self, email):
        connection = database_manager.get_connection(self.database_path)
        try:
            return connection.execute(
                "SELECT COUNT(*) FROM usuarios WHERE correo = ?;", (email,)
            ).fetchone()[0]
        finally:
            connection.close()

    def test_list_accounts_is_safe_ordered_and_student_only(self):
        second = self._student(name="Alicia")
        self._create_account(self.student_id, "zeta@edupass.test")
        self._create_account(second, "alicia@edupass.test")
        rows = usuario_alumno_repository.listar_cuentas(self.database_path)
        self.assertEqual([row["alumno_nombre"] for row in rows], sorted(row["alumno_nombre"] for row in rows))
        self.assertTrue(all(row["rol_nombre"] == ROL_ALUMNO for row in rows))
        for row in rows:
            for key in ("password_hash", "fotografia", "token", "qr"):
                self.assertNotIn(key, row)

    def test_list_unlinked_students_excludes_linked_student(self):
        other = self._student()
        self._create_account()
        ids = {row["alumno_id"] for row in usuario_alumno_repository.listar_alumnos_sin_cuenta(self.database_path)}
        self.assertNotIn(self.student_id, ids)
        self.assertIn(other, ids)

    def test_create_is_atomic_active_student_role_and_derived_name(self):
        account = self._create_account(email="NORMAL@EDUPASS.TEST")
        self.assertEqual(account["correo"], "normal@edupass.test")
        self.assertEqual(account["rol_nombre"], ROL_ALUMNO)
        self.assertEqual(account["usuario_estado"], ESTADO_ACTIVO)
        self.assertEqual(account["usuario_nombre"], account["alumno_nombre"])
        self.assertIsNotNone(usuario_alumno_repository.obtener_por_alumno(self.student_id, self.database_path))

    def test_link_failure_rolls_back_user_and_link(self):
        original = usuario_alumno_repository._load_query
        def load(file_name):
            if file_name == "insert_usuario_alumno.sql":
                return "INSERT INTO tabla_inexistente (dato) VALUES (?);"
            return original(file_name)
        with patch.object(usuario_alumno_repository, "_load_query", side_effect=load):
            with self.assertRaises(RepositoryError):
                self._create_account(email="rollback@edupass.test")
        self.assertEqual(self._count_users_by_email("rollback@edupass.test"), 0)
        self.assertIsNone(usuario_alumno_repository.obtener_por_alumno(self.student_id, self.database_path))

    def test_create_rejects_invalid_actors(self):
        inactive = self._user(ROL_ADMINISTRADOR, ESTADO_INACTIVO)
        scanner = self._user(ROL_ESCANER)
        for actor in (999999, inactive, scanner):
            with self.subTest(actor=actor), self.assertRaises(AuthorizationError):
                self._create_account(actor_id=actor)

    def test_create_rejects_missing_inactive_or_linked_student(self):
        with self.assertRaises(AlumnoNoEncontradoError):
            self._create_account(999999)
        inactive = self._student(ESTADO_INACTIVO)
        with self.assertRaises(AlumnoInactivoError):
            self._create_account(inactive)
        self._create_account()
        with self.assertRaises(AlumnoYaTieneUsuarioError):
            self._create_account(self.student_id, "otra@edupass.test")

    def test_create_rejects_duplicate_email(self):
        self._user(ROL_ESCANER, email="ocupado@edupass.test")
        with self.assertRaises(DuplicateUserError):
            self._create_account(email=" OCUPADO@EDUPASS.TEST ")

    def test_update_email_syncs_name_and_preserves_link_role_state(self):
        account = self._create_account()
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("UPDATE alumnos SET nombre = ? WHERE alumno_id = ?;", ("Nombre Escolar Actual", self.student_id))
            connection.commit()
        finally:
            connection.close()
        updated = usuario_alumno_repository.actualizar_correo_cuenta(
            account["usuario_id"], " NUEVO@EDUPASS.TEST ", self.admin_id, self.database_path
        )
        self.assertEqual(updated["correo"], "nuevo@edupass.test")
        self.assertEqual(updated["usuario_nombre"], "Nombre Escolar Actual")
        self.assertEqual(updated["alumno_id"], self.student_id)
        self.assertEqual(updated["rol_nombre"], ROL_ALUMNO)
        self.assertEqual(updated["usuario_estado"], ESTADO_ACTIVO)

    def test_update_email_allows_own_and_rejects_another_user(self):
        account = self._create_account(email="propio@edupass.test")
        same = usuario_alumno_repository.actualizar_correo_cuenta(
            account["usuario_id"], "PROPIO@EDUPASS.TEST", self.admin_id, self.database_path
        )
        self.assertEqual(same["correo"], "propio@edupass.test")
        self._user(ROL_ESCANER, email="ajeno@edupass.test")
        with self.assertRaises(DuplicateUserError):
            usuario_alumno_repository.actualizar_correo_cuenta(
                account["usuario_id"], "ajeno@edupass.test", self.admin_id, self.database_path
            )

    def test_password_update_changes_only_hash(self):
        account = self._create_account()
        new_hash = generate_password_hash("NuevaPassword123!")
        updated = usuario_alumno_repository.actualizar_password_cuenta(
            account["usuario_id"], new_hash, self.admin_id, self.database_path
        )
        self.assertEqual(updated, account)
        connection = database_manager.get_connection(self.database_path)
        try:
            stored = connection.execute("SELECT password_hash FROM usuarios WHERE usuario_id = ?;", (account["usuario_id"],)).fetchone()[0]
        finally:
            connection.close()
        self.assertTrue(check_password_hash(stored, "NuevaPassword123!"))

    def test_activate_and_deactivate_preserve_link(self):
        account = self._create_account()
        inactive = usuario_alumno_repository.cambiar_estado_cuenta(
            account["usuario_id"], ESTADO_INACTIVO, self.admin_id, self.database_path
        )
        self.assertEqual(inactive["usuario_estado"], ESTADO_INACTIVO)
        active = usuario_alumno_repository.cambiar_estado_cuenta(
            account["usuario_id"], ESTADO_ACTIVO, self.admin_id, self.database_path
        )
        self.assertEqual(active["usuario_estado"], ESTADO_ACTIVO)
        self.assertEqual(active["usuario_alumno_id"], account["usuario_alumno_id"])

    def test_activation_rejects_inactive_student(self):
        account = self._create_account()
        alumno_repository.actualizar_estado_alumno(self.student_id, ESTADO_INACTIVO, self.database_path)
        usuario_alumno_repository.cambiar_estado_cuenta(account["usuario_id"], ESTADO_INACTIVO, self.admin_id, self.database_path)
        with self.assertRaises(AlumnoInactivoError):
            usuario_alumno_repository.cambiar_estado_cuenta(account["usuario_id"], ESTADO_ACTIVO, self.admin_id, self.database_path)

    def test_updates_reject_wrong_or_unlinked_targets(self):
        admin = self._user(ROL_ADMINISTRADOR)
        scanner = self._user(ROL_ESCANER)
        student_user = self._user(ROL_ALUMNO)
        for target in (admin, scanner, student_user, 999999):
            with self.subTest(target=target), self.assertRaises(VinculoUsuarioAlumnoNoEncontradoError):
                usuario_alumno_repository.cambiar_estado_cuenta(target, ESTADO_INACTIVO, self.admin_id, self.database_path)

    def test_deactivation_preserves_qr_movements_and_link(self):
        account = self._create_account()
        connection = database_manager.get_connection(self.database_path)
        try:
            connection.execute("INSERT INTO qr_tokens (alumno_id, token_hash, generado_en, expira_en, estado) VALUES (?, ?, ?, ?, ?);", (self.student_id, "qr-cuenta", "2026-01-01", "2026-01-02", "activo"))
            connection.execute("INSERT INTO movimientos (alumno_id, tipo_movimiento, fecha_hora, usuario_id) VALUES (?, ?, ?, ?);", (self.student_id, "entrada", "2026-01-01", account["usuario_id"]))
            connection.commit()
        finally:
            connection.close()
        usuario_alumno_repository.cambiar_estado_cuenta(account["usuario_id"], ESTADO_INACTIVO, self.admin_id, self.database_path)
        connection = database_manager.get_connection(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM usuario_alumno;").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM qr_tokens;").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM movimientos;").fetchone()[0], 1)
        finally:
            connection.close()

    def test_concurrent_create_same_student_persists_exactly_one_account(self):
        barrier = threading.Barrier(3)
        def create(email):
            barrier.wait()
            try:
                return self._create_account(email=email)
            except Exception as exc:
                return exc
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(create, email) for email in ("uno@edupass.test", "dos@edupass.test")]
            barrier.wait()
            results = [future.result(timeout=10) for future in futures]
        self.assertEqual(sum(isinstance(item, dict) for item in results), 1)
        self.assertEqual(sum(isinstance(item, AlumnoYaTieneUsuarioError) for item in results), 1)
        self.assertEqual(len(usuario_alumno_repository.listar_cuentas(self.database_path)), 1)
        self.assertEqual(self._count_users_by_email("uno@edupass.test") + self._count_users_by_email("dos@edupass.test"), 1)

    def test_management_results_never_include_password_hash(self):
        account = self._create_account()
        operations = [
            usuario_alumno_repository.listar_cuentas(self.database_path)[0],
            usuario_alumno_repository.actualizar_correo_cuenta(account["usuario_id"], account["correo"], self.admin_id, self.database_path),
            usuario_alumno_repository.actualizar_password_cuenta(account["usuario_id"], generate_password_hash("OtraClave123!"), self.admin_id, self.database_path),
        ]
        self.assertTrue(all("password_hash" not in result for result in operations))

if __name__ == "__main__":
    unittest.main()