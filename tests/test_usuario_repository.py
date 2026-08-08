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

from edupass.persistence import database_manager
from edupass.persistence.repositories import (
    rol_repository,
    usuario_repository,
)
from edupass.shared.errors import (
    AuthorizationError,
    AutoBloqueoAdministradorError,
    ConsultaSqlError,
    DuplicateUserError,
    RepositoryError,
    UltimoAdministradorActivoError,
    UsuarioNoEncontradoError,
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
                "requiere_cambio_password",
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


class TestUsuarioRepositoryAdministradores(unittest.TestCase):
    PASSWORD = "ClaveAdministrativa123"

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "administradores_repo.sqlite"
        )
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        self.admin_rol = rol_repository.crear_si_no_existe(
            "administrador", database_path=self.database_path
        )
        self.scanner_rol = rol_repository.crear_si_no_existe(
            "escaner", database_path=self.database_path
        )
        self.password_hash = generate_password_hash(self.PASSWORD)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _crear(self, correo, *, rol="administrador", estado="activo"):
        role = self.admin_rol if rol == "administrador" else self.scanner_rol
        return usuario_repository.crear(
            correo.split("@")[0].title(),
            correo,
            self.password_hash,
            estado,
            role["rol_id"],
            self.database_path,
        )

    def test_listar_unicamente_por_rol_y_sin_hash(self):
        admin_id = self._crear("admin@edupass.test")
        self._crear("scanner@edupass.test", rol="escaner")

        rows = usuario_repository.listar_por_rol(
            "administrador", self.database_path
        )

        self.assertEqual([row["usuario_id"] for row in rows], [admin_id])
        self.assertTrue(all("password_hash" not in row for row in rows))
        self.assertEqual(rows[0]["rol_nombre"], "administrador")

    def test_actualizar_nombre_y_correo(self):
        usuario_id = self._crear("original@edupass.test")

        changed = usuario_repository.actualizar_datos(
            usuario_id,
            "  Nombre Editado  ",
            "  EDITADO@EDUPASS.TEST  ",
            self.database_path,
        )
        row = usuario_repository.obtener_por_id(usuario_id, self.database_path)

        self.assertTrue(changed)
        self.assertEqual(row["nombre"], "Nombre Editado")
        self.assertEqual(row["correo"], "editado@edupass.test")

    def test_actualizar_correo_duplicado(self):
        first = self._crear("primero@edupass.test")
        second = self._crear("segundo@edupass.test")

        with self.assertRaises(DuplicateUserError):
            usuario_repository.actualizar_datos(
                second, "Segundo", "primero@edupass.test", self.database_path
            )

        self.assertEqual(
            usuario_repository.obtener_por_id(second, self.database_path)[
                "correo"
            ],
            "segundo@edupass.test",
        )
        self.assertNotEqual(first, second)

    def test_actualizar_password_requiere_hash(self):
        usuario_id = self._crear("password@edupass.test")
        new_hash = generate_password_hash("NuevaClave123")

        self.assertTrue(
            usuario_repository.actualizar_password(
                usuario_id, new_hash, self.database_path
            )
        )
        saved = usuario_repository.obtener_por_id(
            usuario_id, self.database_path
        )["password_hash"]
        self.assertTrue(check_password_hash(saved, "NuevaClave123"))
        with self.assertRaises(RepositoryError):
            usuario_repository.actualizar_password(
                usuario_id, "texto-plano", self.database_path
            )

    def test_contar_administradores_activos(self):
        self._crear("activo1@edupass.test")
        self._crear("activo2@edupass.test")
        self._crear("inactivo@edupass.test", estado="inactivo")
        self._crear("scanner@edupass.test", rol="escaner")

        self.assertEqual(
            usuario_repository.contar_activos_por_rol(
                "administrador", self.database_path
            ),
            2,
        )

    def test_activar_administrador(self):
        actor = self._crear("actor@edupass.test")
        target = self._crear("target@edupass.test", estado="inactivo")

        result = usuario_repository.cambiar_estado_administrador_protegido(
            target, "activo", actor, self.database_path
        )

        self.assertEqual(result["estado"], "activo")
        self.assertNotIn("password_hash", result)

    def test_dos_administradores_permiten_desactivar_uno(self):
        actor = self._crear("actor@edupass.test")
        target = self._crear("target@edupass.test")

        result = usuario_repository.cambiar_estado_administrador_protegido(
            target, "inactivo", actor, self.database_path
        )

        self.assertEqual(result["estado"], "inactivo")
        self.assertEqual(
            usuario_repository.contar_activos_por_rol(
                "administrador", self.database_path
            ),
            1,
        )

    def test_auto_bloqueo_rechazado(self):
        actor = self._crear("actor@edupass.test")
        self._crear("otro@edupass.test")

        with self.assertRaises(AutoBloqueoAdministradorError):
            usuario_repository.cambiar_estado_administrador_protegido(
                actor, "inactivo", actor, self.database_path
            )

        self.assertEqual(
            usuario_repository.obtener_por_id(actor, self.database_path)[
                "estado"
            ],
            "activo",
        )

    def test_ultimo_administrador_activo_rechazado(self):
        actor = self._crear("actor@edupass.test")
        target = self._crear("target@edupass.test")
        original_loader = usuario_repository._load_query

        def one_active_loader(file_name):
            if file_name == usuario_repository._COUNT_ACTIVE_BY_ROLE_FILE:
                return "SELECT 1 AS total_activos WHERE ? = ?;"
            return original_loader(file_name)

        with patch.object(
            usuario_repository, "_load_query", side_effect=one_active_loader
        ):
            with self.assertRaises(UltimoAdministradorActivoError):
                usuario_repository.cambiar_estado_administrador_protegido(
                    target, "inactivo", actor, self.database_path
                )

    def test_actor_inactivo_rechazado(self):
        actor = self._crear("actor@edupass.test", estado="inactivo")
        target = self._crear("target@edupass.test")

        with self.assertRaises(AuthorizationError):
            usuario_repository.cambiar_estado_administrador_protegido(
                target, "inactivo", actor, self.database_path
            )

    def test_actor_no_administrador_rechazado(self):
        actor = self._crear("scanner@edupass.test", rol="escaner")
        target = self._crear("target@edupass.test")

        with self.assertRaises(AuthorizationError):
            usuario_repository.cambiar_estado_administrador_protegido(
                target, "inactivo", actor, self.database_path
            )

    def test_objetivo_de_otro_rol_rechazado(self):
        actor = self._crear("actor@edupass.test")
        target = self._crear("scanner@edupass.test", rol="escaner")

        with self.assertRaises(UsuarioNoEncontradoError):
            usuario_repository.cambiar_estado_administrador_protegido(
                target, "inactivo", actor, self.database_path
            )

    def test_rollback_ante_fallo_de_actualizacion(self):
        actor = self._crear("actor@edupass.test")
        target = self._crear("target@edupass.test")
        original_loader = usuario_repository._load_query

        def failing_loader(file_name):
            if file_name == usuario_repository._UPDATE_STATE_FILE:
                return "UPDATE tabla_inexistente SET estado = ? WHERE id = ?;"
            return original_loader(file_name)

        with patch.object(
            usuario_repository, "_load_query", side_effect=failing_loader
        ):
            with self.assertRaises(RepositoryError):
                usuario_repository.cambiar_estado_administrador_protegido(
                    target, "inactivo", actor, self.database_path
                )

        self.assertEqual(
            usuario_repository.obtener_por_id(target, self.database_path)[
                "estado"
            ],
            "activo",
        )

    def test_concurrencia_no_desactiva_a_los_dos_actores(self):
        first = self._crear("first@edupass.test")
        second = self._crear("second@edupass.test")
        barrier = threading.Barrier(2)
        outcomes = []
        lock = threading.Lock()

        def deactivate(target, actor):
            barrier.wait()
            try:
                usuario_repository.cambiar_estado_administrador_protegido(
                    target, "inactivo", actor, self.database_path
                )
                outcome = "ok"
            except (AuthorizationError, UltimoAdministradorActivoError):
                outcome = "blocked"
            with lock:
                outcomes.append(outcome)

        threads = [
            threading.Thread(target=deactivate, args=(second, first)),
            threading.Thread(target=deactivate, args=(first, second)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(outcomes), ["blocked", "ok"])
        self.assertEqual(
            usuario_repository.contar_activos_por_rol(
                "administrador", self.database_path
            ),
            1,
        )

    def test_sql_nuevo_es_parametrizado_y_sin_interpolacion(self):
        sql_dir = SRC_PATH / "edupass" / "persistence" / "sql" / "usuarios"
        for file_name in (
            "select_usuarios_by_rol.sql",
            "update_usuario_datos.sql",
            "update_usuario_estado.sql",
            "update_usuario_password.sql",
            "count_usuarios_activos_by_rol.sql",
        ):
            with self.subTest(file_name=file_name):
                sql = (sql_dir / file_name).read_text(encoding="utf-8")
                self.assertIn("?", sql)
                self.assertNotIn("%s", sql)
                self.assertNotIn("{", sql)

    def test_sql_faltante_en_listado_es_controlado(self):
        with patch.object(
            usuario_repository,
            "_SELECT_BY_ROLE_FILE",
            "archivo_inexistente.sql",
        ):
            with self.assertRaises(ConsultaSqlError):
                usuario_repository.listar_por_rol(
                    "administrador", self.database_path
                )

    def test_cierra_conexion_despues_de_listar(self):
        real_connection = database_manager.get_connection(self.database_path)

        class TrackingConnection:
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
                object.__setattr__(self, "closed", True)
                self.connection.close()

        tracking = TrackingConnection(real_connection)
        with patch.object(
            usuario_repository.database_manager,
            "get_connection",
            return_value=tracking,
        ):
            usuario_repository.listar_por_rol("administrador", self.database_path)

        self.assertTrue(tracking.closed)
class TestUsuarioRepositoryEscaneres(unittest.TestCase):
    PASSWORD = "ClaveEscaner123"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "escaneres_repo.sqlite"
        database_manager.initialize_database(self.database_path, SCHEMA_PATH)
        self.admin_role = rol_repository.crear_si_no_existe(
            "administrador", database_path=self.database_path
        )
        self.scanner_role = rol_repository.crear_si_no_existe(
            "escaner", database_path=self.database_path
        )
        self.password_hash = generate_password_hash(self.PASSWORD)

    def tearDown(self):
        self.temp.cleanup()

    def _user(self, email, role="escaner", state="activo"):
        role_id = (
            self.scanner_role["rol_id"]
            if role == "escaner"
            else self.admin_role["rol_id"]
        )
        return usuario_repository.crear(
            email.split("@")[0], email, self.password_hash,
            state, role_id, self.database_path,
        )

    def test_listar_solo_escaneres_sin_administradores_ni_hash(self):
        scanner = self._user("scanner@edupass.test")
        self._user("admin@edupass.test", role="administrador")
        rows = usuario_repository.listar_por_rol("escaner", self.database_path)
        self.assertEqual([row["usuario_id"] for row in rows], [scanner])
        self.assertTrue(all(row["rol_nombre"] == "escaner" for row in rows))
        self.assertTrue(all("password_hash" not in row for row in rows))

    def test_administrador_activo_puede_desactivar_y_activar_escaner(self):
        actor = self._user("admin@edupass.test", role="administrador")
        target = self._user("scanner@edupass.test")
        inactive = usuario_repository.cambiar_estado_escaner_protegido(
            target, "inactivo", actor, self.database_path
        )
        active = usuario_repository.cambiar_estado_escaner_protegido(
            target, "activo", actor, self.database_path
        )
        self.assertEqual(inactive["estado"], "inactivo")
        self.assertEqual(active["estado"], "activo")
        self.assertNotIn("password_hash", active)

    def test_actor_inactivo_y_actor_escaner_son_rechazados(self):
        inactive_admin = self._user(
            "inactive@edupass.test", role="administrador", state="inactivo"
        )
        scanner_actor = self._user("actor@edupass.test")
        target = self._user("target@edupass.test")
        for actor in (inactive_admin, scanner_actor):
            with self.subTest(actor=actor):
                with self.assertRaises(AuthorizationError):
                    usuario_repository.cambiar_estado_escaner_protegido(
                        target, "inactivo", actor, self.database_path
                    )

    def test_objetivo_administrador_e_inexistente_son_rechazados(self):
        actor = self._user("actor@edupass.test", role="administrador")
        admin_target = self._user("target@edupass.test", role="administrador")
        for target in (admin_target, 99999):
            with self.subTest(target=target):
                with self.assertRaises(UsuarioNoEncontradoError):
                    usuario_repository.cambiar_estado_escaner_protegido(
                        target, "inactivo", actor, self.database_path
                    )

    def test_rollback_ante_fallo_conserva_estado(self):
        actor = self._user("actor@edupass.test", role="administrador")
        target = self._user("scanner@edupass.test")
        original_loader = usuario_repository._load_query

        def failing_loader(file_name):
            if file_name == usuario_repository._UPDATE_STATE_FILE:
                return "UPDATE tabla_inexistente SET estado = ? WHERE id = ?;"
            return original_loader(file_name)

        with patch.object(usuario_repository, "_load_query", side_effect=failing_loader):
            with self.assertRaises(RepositoryError):
                usuario_repository.cambiar_estado_escaner_protegido(
                    target, "inactivo", actor, self.database_path
                )
        self.assertEqual(usuario_repository.obtener_por_id(
            target, self.database_path)["estado"], "activo")

    def test_desactivar_conserva_movimiento_asociado(self):
        actor = self._user("actor@edupass.test", role="administrador")
        target = self._user("scanner@edupass.test")
        connection = database_manager.get_connection(self.database_path)
        try:
            alumno = connection.execute(
                "INSERT INTO alumnos (nombre, matricula, grado, grupo, estado) "
                "VALUES (?, ?, ?, ?, ?);",
                ("Alumno", "MAT-S13-E3", "1", "A", "activo"),
            ).lastrowid
            connection.execute(
                "INSERT INTO movimientos "
                "(alumno_id, tipo_movimiento, fecha_hora, usuario_id) "
                "VALUES (?, ?, ?, ?);",
                (alumno, "entrada", "2026-07-31T18:00:00", target),
            )
            connection.commit()
        finally:
            connection.close()
        usuario_repository.cambiar_estado_escaner_protegido(
            target, "inactivo", actor, self.database_path
        )
        connection = database_manager.get_connection(self.database_path)
        try:
            total = connection.execute(
                "SELECT COUNT(*) FROM movimientos WHERE usuario_id = ?;", (target,)
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(total, 1)

    def test_operacion_declara_begin_immediate_y_no_regla_ultimo_admin(self):
        source = Path(usuario_repository.__file__).read_text(encoding="utf-8")
        self.assertIn('connection.execute("BEGIN IMMEDIATE;")', source)
        actor = self._user("admin@edupass.test", role="administrador")
        target = self._user("scanner@edupass.test")
        with patch.object(
            usuario_repository,
            "_load_query",
            wraps=usuario_repository._load_query,
        ) as loader:
            usuario_repository.cambiar_estado_escaner_protegido(
                target, "inactivo", actor, self.database_path
            )
        loaded = [call.args[0] for call in loader.call_args_list]
        self.assertNotIn(usuario_repository._COUNT_ACTIVE_BY_ROLE_FILE, loaded)

    def test_cambio_de_administradores_conserva_compatibilidad(self):
        actor = self._user("actor@edupass.test", role="administrador")
        target = self._user("target@edupass.test", role="administrador")
        result = usuario_repository.cambiar_estado_administrador_protegido(
            target, "inactivo", actor, self.database_path
        )
        self.assertEqual(result["estado"], "inactivo")

    def test_conexion_y_cursores_se_cierran(self):
        actor = self._user("admin@edupass.test", role="administrador")
        target = self._user("scanner@edupass.test")
        real = database_manager.get_connection(self.database_path)

        class TrackingCursor:
            def __init__(self, cursor):
                self.cursor = cursor
                self.closed = False
            def __getattr__(self, name):
                return getattr(self.cursor, name)
            def close(self):
                self.closed = True
                self.cursor.close()

        class TrackingConnection:
            def __init__(self, connection):
                object.__setattr__(self, "connection", connection)
                object.__setattr__(self, "closed", False)
                object.__setattr__(self, "cursors", [])
            def __getattr__(self, name):
                return getattr(self.connection, name)
            def __setattr__(self, name, value):
                if name in {"connection", "closed", "cursors"}:
                    object.__setattr__(self, name, value)
                else:
                    setattr(self.connection, name, value)
            def execute(self, *args, **kwargs):
                cursor = TrackingCursor(self.connection.execute(*args, **kwargs))
                self.cursors.append(cursor)
                return cursor
            def close(self):
                self.closed = True
                self.connection.close()

        tracking = TrackingConnection(real)
        with patch.object(usuario_repository.database_manager, "get_connection",
                          return_value=tracking):
            usuario_repository.cambiar_estado_escaner_protegido(
                target, "inactivo", actor, self.database_path
            )
        self.assertTrue(tracking.closed)
        self.assertTrue(tracking.cursors)
        self.assertTrue(all(cursor.closed for cursor in tracking.cursors))

if __name__ == "__main__":
    unittest.main()
