"""Vinculacion uno a uno entre usuarios con rol alumno y alumnos."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edupass.persistence import database_manager
from edupass.shared.constants import (
    ESTADO_ACTIVO,
    ESTADO_INACTIVO,
    ROL_ADMINISTRADOR,
    ROL_ALUMNO,
)
from edupass.shared.errors import (
    AlumnoInactivoError,
    AlumnoNoEncontradoError,
    AlumnoYaTieneUsuarioError,
    AuthorizationError,
    ConsultaSqlError,
    DuplicateUserError,
    EduPassError,
    RepositoryError,
    UsuarioAlumnoYaVinculadoError,
    UsuarioNoEncontradoError,
    UsuarioNoEsAlumnoError,
    ValidationError,
    VinculoUsuarioAlumnoNoEncontradoError,
)


_SQL_DIRECTORY = Path(__file__).resolve().parent.parent / "sql" / "usuario_alumno"
_INSERT_FILE = "insert_usuario_alumno.sql"
_SELECT_BY_USER_FILE = "select_usuario_alumno_by_usuario.sql"
_SELECT_BY_STUDENT_FILE = "select_usuario_alumno_by_alumno.sql"
_SELECT_DETAIL_FILE = "select_usuario_alumno_detail.sql"
_SELECT_USER_ROLE_FILE = "select_usuario_role_for_link.sql"
_SELECT_STUDENT_FILE = "select_alumno_for_link.sql"
_SELECT_ACCOUNTS_FILE = "select_cuentas_alumno.sql"
_SELECT_UNLINKED_STUDENTS_FILE = "select_alumnos_sin_cuenta.sql"
_SELECT_ACTOR_FILE = "select_actor_admin_for_cuenta.sql"
_SELECT_STUDENT_ROLE_FILE = "select_rol_alumno_for_cuenta.sql"
_SELECT_EMAIL_FILE = "select_correo_usuario_for_cuenta.sql"
_INSERT_STUDENT_USER_FILE = "insert_usuario_cuenta_alumno.sql"
_USERS_SQL_DIRECTORY = _SQL_DIRECTORY.parent / "usuarios"
_UPDATE_USER_DATA_FILE = "update_usuario_datos.sql"
_UPDATE_USER_PASSWORD_FILE = "update_usuario_password.sql"
_UPDATE_USER_STATE_FILE = "update_usuario_estado.sql"


def _load_query(file_name: str) -> str:
    query_path = _SQL_DIRECTORY / file_name
    if not query_path.is_file():
        raise ConsultaSqlError(
            f"No se encontro el archivo de consulta SQL: {file_name}"
        )
    try:
        query = query_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConsultaSqlError(
            f"No se pudo leer el archivo de consulta SQL: {file_name}"
        ) from exc
    if not query.strip():
        raise ConsultaSqlError(
            f"El archivo de consulta SQL esta vacio: {file_name}"
        )
    return query


def _validar_id(value: object, entity: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(
            f"El identificador del {entity} debe ser un entero mayor que cero."
        )
    return value


def _rollback(connection: sqlite3.Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.rollback()
    except sqlite3.Error:
        pass


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _fetch_one(
    file_name: str,
    identifier: int,
    database_path: Path | None,
) -> dict[str, Any] | None:
    query = _load_query(file_name)
    connection = None
    cursor = None
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(query, (identifier,))
        return _row_to_dict(cursor.fetchone())
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError(
            "No se pudo consultar la vinculacion usuario-alumno."
        ) from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def _map_integrity_error(error: sqlite3.IntegrityError) -> EduPassError:
    message = str(error)
    if "usuario_alumno.usuario_id" in message:
        return UsuarioAlumnoYaVinculadoError(
            "El usuario ya está vinculado a un alumno."
        )
    if "usuario_alumno.alumno_id" in message:
        return AlumnoYaTieneUsuarioError(
            "El alumno ya tiene una cuenta vinculada."
        )
    return RepositoryError("No se pudo crear la vinculacion usuario-alumno.")


def vincular(
    usuario_id: object,
    alumno_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Crea y devuelve una vinculacion uno a uno de forma transaccional."""
    usuario_id_validado = _validar_id(usuario_id, "usuario")
    alumno_id_validado = _validar_id(alumno_id, "alumno")
    queries = {
        "usuario": _load_query(_SELECT_USER_ROLE_FILE),
        "alumno": _load_query(_SELECT_STUDENT_FILE),
        "por_usuario": _load_query(_SELECT_BY_USER_FILE),
        "por_alumno": _load_query(_SELECT_BY_STUDENT_FILE),
        "insertar": _load_query(_INSERT_FILE),
        "detalle": _load_query(_SELECT_DETAIL_FILE),
    }
    connection = None
    cursors: list[sqlite3.Cursor] = []
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursors.append(connection.execute("BEGIN IMMEDIATE;"))

        cursor = connection.execute(queries["usuario"], (usuario_id_validado,))
        cursors.append(cursor)
        usuario = cursor.fetchone()
        if usuario is None:
            raise UsuarioNoEncontradoError(
                "No se encontro el usuario solicitado."
            )
        if usuario["rol_nombre"] != ROL_ALUMNO:
            raise UsuarioNoEsAlumnoError(
                "El usuario no tiene el rol alumno."
            )

        cursor = connection.execute(queries["alumno"], (alumno_id_validado,))
        cursors.append(cursor)
        if cursor.fetchone() is None:
            raise AlumnoNoEncontradoError(
                "No se encontro el alumno solicitado."
            )

        cursor = connection.execute(
            queries["por_usuario"], (usuario_id_validado,)
        )
        cursors.append(cursor)
        if cursor.fetchone() is not None:
            raise UsuarioAlumnoYaVinculadoError(
                "El usuario ya está vinculado a un alumno."
            )

        cursor = connection.execute(
            queries["por_alumno"], (alumno_id_validado,)
        )
        cursors.append(cursor)
        if cursor.fetchone() is not None:
            raise AlumnoYaTieneUsuarioError(
                "El alumno ya tiene una cuenta vinculada."
            )

        cursor = connection.execute(
            queries["insertar"],
            (usuario_id_validado, alumno_id_validado),
        )
        cursors.append(cursor)
        vinculo_id = int(cursor.lastrowid)

        cursor = connection.execute(queries["detalle"], (vinculo_id,))
        cursors.append(cursor)
        detalle = _row_to_dict(cursor.fetchone())
        if detalle is None:
            raise VinculoUsuarioAlumnoNoEncontradoError(
                "No se encontró la vinculación solicitada."
            )
        connection.commit()
        return detalle
    except sqlite3.IntegrityError as exc:
        _rollback(connection)
        raise _map_integrity_error(exc) from exc
    except EduPassError:
        _rollback(connection)
        raise
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError(
            "No se pudo crear la vinculacion usuario-alumno."
        ) from exc
    finally:
        for cursor in reversed(cursors):
            cursor.close()
        if connection is not None:
            connection.close()


def obtener_por_usuario(
    usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Devuelve el detalle seguro vinculado a un usuario."""
    identifier = _validar_id(usuario_id, "usuario")
    return _fetch_one(_SELECT_BY_USER_FILE, identifier, database_path)


def obtener_por_alumno(
    alumno_id: object,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Devuelve el detalle seguro vinculado a un alumno."""
    identifier = _validar_id(alumno_id, "alumno")
    return _fetch_one(_SELECT_BY_STUDENT_FILE, identifier, database_path)

def _load_user_query(file_name: str) -> str:
    query_path = _USERS_SQL_DIRECTORY / file_name
    if not query_path.is_file():
        raise ConsultaSqlError(
            f"No se encontro el archivo de consulta SQL: {file_name}"
        )
    try:
        query = query_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConsultaSqlError(
            f"No se pudo leer el archivo de consulta SQL: {file_name}"
        ) from exc
    if not query.strip():
        raise ConsultaSqlError(
            f"El archivo de consulta SQL esta vacio: {file_name}"
        )
    return query


def _normalizar_correo(correo: object) -> str:
    if not isinstance(correo, str) or not correo.strip():
        raise ValidationError("El correo es obligatorio.")
    correo_normalizado = correo.strip().lower()
    if len(correo_normalizado) > 254:
        raise ValidationError("El correo no puede exceder 254 caracteres.")
    return correo_normalizado


def _validar_password_hash(password_hash: object) -> str:
    if (
        not isinstance(password_hash, str)
        or password_hash.count("$") < 2
        or ":" not in password_hash.split("$", 1)[0]
    ):
        raise ValidationError("El hash de contrasena no es valido.")
    return password_hash


def _validar_estado(estado: object) -> str:
    if not isinstance(estado, str):
        raise ValidationError("El estado de la cuenta no es valido.")
    estado_normalizado = estado.strip().lower()
    if estado_normalizado not in {ESTADO_ACTIVO, ESTADO_INACTIVO}:
        raise ValidationError("El estado de la cuenta no es valido.")
    return estado_normalizado


def _execute(
    connection: sqlite3.Connection,
    cursors: list[sqlite3.Cursor],
    query: str,
    parameters: tuple[Any, ...] = (),
) -> sqlite3.Cursor:
    cursor = connection.execute(query, parameters)
    cursors.append(cursor)
    return cursor


def _require_active_admin(
    connection: sqlite3.Connection,
    cursors: list[sqlite3.Cursor],
    query: str,
    actor_usuario_id: int,
) -> None:
    actor = _execute(
        connection,
        cursors,
        query,
        (actor_usuario_id, ESTADO_ACTIVO, ROL_ADMINISTRADOR),
    ).fetchone()
    if actor is None:
        raise AuthorizationError("Acceso no autorizado.")


def _require_student_account(
    connection: sqlite3.Connection,
    cursors: list[sqlite3.Cursor],
    detail_query: str,
    usuario_id: int,
) -> dict[str, Any]:
    row = _execute(
        connection, cursors, detail_query, (usuario_id,)
    ).fetchone()
    account = _row_to_dict(row)
    if account is None or account.get("rol_nombre") != ROL_ALUMNO:
        raise VinculoUsuarioAlumnoNoEncontradoError(
            "No se encontró la vinculación solicitada."
        )
    return account


def _close_transaction_resources(
    cursors: list[sqlite3.Cursor],
    connection: sqlite3.Connection | None,
) -> None:
    for cursor in reversed(cursors):
        cursor.close()
    if connection is not None:
        connection.close()


def _fetch_all(
    file_name: str,
    parameters: tuple[Any, ...],
    database_path: Path | None,
) -> list[dict[str, Any]]:
    query = _load_query(file_name)
    connection = None
    cursor = None
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(query, parameters)
        return [dict(row) for row in cursor.fetchall()]
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError(
            "No se pudieron consultar las cuentas de alumnos."
        ) from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def listar_cuentas(
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Lista exclusivamente cuentas vinculadas con rol alumno."""
    return _fetch_all(_SELECT_ACCOUNTS_FILE, (ROL_ALUMNO,), database_path)


def listar_alumnos_sin_cuenta(
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Lista alumnos que todavia no tienen una cuenta vinculada."""
    return _fetch_all(_SELECT_UNLINKED_STUDENTS_FILE, (1,), database_path)


def crear_cuenta_vinculada(
    alumno_id: object,
    correo: object,
    password_hash: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Crea una cuenta alumno y su vinculo en una sola transaccion."""
    alumno_id_validado = _validar_id(alumno_id, "alumno")
    actor_id = _validar_id(actor_usuario_id, "usuario actor")
    correo_normalizado = _normalizar_correo(correo)
    hash_validado = _validar_password_hash(password_hash)
    queries = {
        "actor": _load_query(_SELECT_ACTOR_FILE),
        "alumno": _load_query(_SELECT_STUDENT_FILE),
        "vinculo": _load_query(_SELECT_BY_STUDENT_FILE),
        "correo": _load_query(_SELECT_EMAIL_FILE),
        "rol": _load_query(_SELECT_STUDENT_ROLE_FILE),
        "usuario": _load_query(_INSERT_STUDENT_USER_FILE),
        "relacion": _load_query(_INSERT_FILE),
        "detalle": _load_query(_SELECT_DETAIL_FILE),
    }
    connection = None
    cursors: list[sqlite3.Cursor] = []
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        _execute(connection, cursors, "BEGIN IMMEDIATE;")
        _require_active_admin(connection, cursors, queries["actor"], actor_id)

        alumno_row = _execute(
            connection, cursors, queries["alumno"], (alumno_id_validado,)
        ).fetchone()
        alumno = _row_to_dict(alumno_row)
        if alumno is None:
            raise AlumnoNoEncontradoError(
                "No se encontro el alumno solicitado."
            )
        if alumno["estado"] != ESTADO_ACTIVO:
            raise AlumnoInactivoError(
                "No se puede activar una cuenta para un alumno inactivo."
            )
        if _execute(
            connection, cursors, queries["vinculo"], (alumno_id_validado,)
        ).fetchone() is not None:
            raise AlumnoYaTieneUsuarioError(
                "El alumno ya tiene una cuenta vinculada."
            )
        if _execute(
            connection, cursors, queries["correo"], (correo_normalizado,)
        ).fetchone() is not None:
            raise DuplicateUserError("El correo ya está registrado.")

        rol = _execute(
            connection, cursors, queries["rol"], (ROL_ALUMNO,)
        ).fetchone()
        if rol is None:
            raise RepositoryError("No se encontro el rol alumno.")
        user_cursor = _execute(
            connection,
            cursors,
            queries["usuario"],
            (
                alumno["nombre"],
                correo_normalizado,
                hash_validado,
                ESTADO_ACTIVO,
                rol["rol_id"],
            ),
        )
        usuario_id = int(user_cursor.lastrowid)
        link_cursor = _execute(
            connection,
            cursors,
            queries["relacion"],
            (usuario_id, alumno_id_validado),
        )
        detail = _row_to_dict(
            _execute(
                connection,
                cursors,
                queries["detalle"],
                (int(link_cursor.lastrowid),),
            ).fetchone()
        )
        if detail is None:
            raise VinculoUsuarioAlumnoNoEncontradoError(
                "No se encontró la vinculación solicitada."
            )
        connection.commit()
        return detail
    except sqlite3.IntegrityError as exc:
        _rollback(connection)
        message = str(exc)
        if "usuarios.correo" in message:
            raise DuplicateUserError("El correo ya está registrado.") from exc
        if "usuario_alumno.alumno_id" in message:
            raise AlumnoYaTieneUsuarioError(
                "El alumno ya tiene una cuenta vinculada."
            ) from exc
        raise RepositoryError(
            "No se pudo crear la cuenta vinculada."
        ) from exc
    except EduPassError:
        _rollback(connection)
        raise
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError(
            "No se pudo crear la cuenta vinculada."
        ) from exc
    finally:
        _close_transaction_resources(cursors, connection)


def _actualizar_cuenta(
    usuario_id: object,
    actor_usuario_id: object,
    update_query: str,
    update_parameters,
    database_path: Path | None,
    *,
    require_active_student: bool = False,
) -> dict[str, Any]:
    usuario_id_validado = _validar_id(usuario_id, "usuario")
    actor_id = _validar_id(actor_usuario_id, "usuario actor")
    actor_query = _load_query(_SELECT_ACTOR_FILE)
    detail_query = _load_query(_SELECT_BY_USER_FILE)
    connection = None
    cursors: list[sqlite3.Cursor] = []
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        _execute(connection, cursors, "BEGIN IMMEDIATE;")
        _require_active_admin(connection, cursors, actor_query, actor_id)
        account = _require_student_account(
            connection, cursors, detail_query, usuario_id_validado
        )
        if require_active_student and account["alumno_estado"] != ESTADO_ACTIVO:
            raise AlumnoInactivoError(
                "No se puede activar una cuenta para un alumno inactivo."
            )
        parameters = update_parameters(
            connection, cursors, account, usuario_id_validado
        )
        _execute(connection, cursors, update_query, parameters)
        result = _require_student_account(
            connection, cursors, detail_query, usuario_id_validado
        )
        connection.commit()
        return result
    except sqlite3.IntegrityError as exc:
        _rollback(connection)
        if "usuarios.correo" in str(exc):
            raise DuplicateUserError("El correo ya está registrado.") from exc
        raise RepositoryError(
            "No se pudo actualizar la cuenta del alumno."
        ) from exc
    except EduPassError:
        _rollback(connection)
        raise
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError(
            "No se pudo actualizar la cuenta del alumno."
        ) from exc
    finally:
        _close_transaction_resources(cursors, connection)


def actualizar_correo_cuenta(
    usuario_id: object,
    correo: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Actualiza el correo y sincroniza el nombre con el alumno vinculado."""
    correo_normalizado = _normalizar_correo(correo)
    correo_query = _load_query(_SELECT_EMAIL_FILE)
    update_query = _load_user_query(_UPDATE_USER_DATA_FILE)

    def parameters(connection, cursors, account, identifier):
        existing = _execute(
            connection, cursors, correo_query, (correo_normalizado,)
        ).fetchone()
        if existing is not None and existing["usuario_id"] != identifier:
            raise DuplicateUserError("El correo ya está registrado.")
        return (account["alumno_nombre"], correo_normalizado, identifier)

    return _actualizar_cuenta(
        usuario_id,
        actor_usuario_id,
        update_query,
        parameters,
        database_path,
    )


def actualizar_password_cuenta(
    usuario_id: object,
    password_hash: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Actualiza solamente el hash de la cuenta vinculada."""
    hash_validado = _validar_password_hash(password_hash)
    return _actualizar_cuenta(
        usuario_id,
        actor_usuario_id,
        _load_user_query(_UPDATE_USER_PASSWORD_FILE),
        lambda connection, cursors, account, identifier: (
            hash_validado, identifier
        ),
        database_path,
    )


def cambiar_estado_cuenta(
    usuario_id: object,
    nuevo_estado: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Activa o desactiva la cuenta sin eliminar su vinculacion."""
    estado = _validar_estado(nuevo_estado)
    return _actualizar_cuenta(
        usuario_id,
        actor_usuario_id,
        _load_user_query(_UPDATE_USER_STATE_FILE),
        lambda connection, cursors, account, identifier: (estado, identifier),
        database_path,
        require_active_student=estado == ESTADO_ACTIVO,
    )
