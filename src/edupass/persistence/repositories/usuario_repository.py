"""Operaciones de persistencia para usuarios de autenticacion."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edupass.persistence import database_manager
from edupass.shared.constants import (
    ESTADO_ACTIVO,
    ESTADO_INACTIVO,
    ROL_ADMINISTRADOR,
    ROL_ESCANER,
)
from edupass.shared.errors import (
    AuthorizationError,
    AutoBloqueoAdministradorError,
    ConsultaSqlError,
    DuplicateUserError,
    EduPassError,
    RepositoryError,
    UltimoAdministradorActivoError,
    UsuarioNoEncontradoError,
)


_SQL_DIRECTORY = Path(__file__).resolve().parent.parent / "sql" / "usuarios"
_SELECT_BY_EMAIL_FILE = "select_usuario_by_correo.sql"
_SELECT_BY_ID_FILE = "select_usuario_by_id.sql"
_SELECT_BY_ROLE_FILE = "select_usuarios_by_rol.sql"
_INSERT_FILE = "insert_usuario.sql"
_UPDATE_DATA_FILE = "update_usuario_datos.sql"
_UPDATE_STATE_FILE = "update_usuario_estado.sql"
_UPDATE_PASSWORD_FILE = "update_usuario_password.sql"
_UPDATE_PASSWORD_REQUIREMENT_FILE = "update_usuario_password_requirement.sql"
_COUNT_ACTIVE_BY_ROLE_FILE = "count_usuarios_activos_by_rol.sql"
_SAFE_USER_FIELDS = (
    "usuario_id",
    "nombre",
    "correo",
    "estado",
    "rol_id",
    "rol_nombre",
)


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


def _normalizar_correo(correo: object) -> str:
    if not isinstance(correo, str) or not correo.strip():
        raise RepositoryError("El correo del usuario es obligatorio.")
    return correo.strip().lower()


def _normalizar_nombre(nombre: object) -> str:
    if not isinstance(nombre, str) or not nombre.strip():
        raise RepositoryError("El nombre del usuario es obligatorio.")
    return nombre.strip()


def _normalizar_rol(rol_nombre: object) -> str:
    if not isinstance(rol_nombre, str) or not rol_nombre.strip():
        raise RepositoryError("El rol del usuario es obligatorio.")
    return rol_nombre.strip().lower()


def _validar_password_hash(password_hash: object) -> str:
    if (
        not isinstance(password_hash, str)
        or password_hash.count("$") < 2
        or ":" not in password_hash.split("$", 1)[0]
    ):
        raise RepositoryError(
            "El repositorio requiere un hash de contrasena valido."
        )
    return password_hash


def _validar_estado(estado: object) -> str:
    if not isinstance(estado, str):
        raise RepositoryError("El estado del usuario no es valido.")
    estado_normalizado = estado.strip().lower()
    if estado_normalizado not in {ESTADO_ACTIVO, ESTADO_INACTIVO}:
        raise RepositoryError("El estado del usuario no es valido.")
    return estado_normalizado


def _validar_rol_id(rol_id: object) -> int:
    if isinstance(rol_id, bool) or not isinstance(rol_id, int) or rol_id <= 0:
        raise RepositoryError("El identificador del rol no es valido.")
    return rol_id


def _validar_usuario_id(usuario_id: object) -> int:
    if (
        isinstance(usuario_id, bool)
        or not isinstance(usuario_id, int)
        or usuario_id <= 0
    ):
        raise RepositoryError("El identificador del usuario no es valido.")
    return usuario_id


def _rollback(connection: sqlite3.Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.rollback()
    except sqlite3.Error:
        pass


def _es_correo_duplicado(error: sqlite3.IntegrityError) -> bool:
    return (
        getattr(error, "sqlite_errorname", "")
        == "SQLITE_CONSTRAINT_UNIQUE"
        and "usuarios.correo" in str(error)
    )


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _safe_user_row(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row[field] for field in _SAFE_USER_FIELDS}


def _fetch_one(
    file_name: str,
    parameters: tuple[Any, ...],
    database_path: Path | None,
) -> dict[str, Any] | None:
    query = _load_query(file_name)
    connection = None
    cursor = None

    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(query, parameters)
        return _row_to_dict(cursor.fetchone())
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError("No se pudo consultar el usuario.") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def _execute_update(
    file_name: str,
    parameters: tuple[Any, ...],
    database_path: Path | None,
    *,
    duplicate_email: bool = False,
) -> bool:
    query = _load_query(file_name)
    connection = None
    cursor = None
    try:
        connection = database_manager.get_connection(database_path)
        cursor = connection.execute(query, parameters)
        connection.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError as exc:
        _rollback(connection)
        if duplicate_email and _es_correo_duplicado(exc):
            raise DuplicateUserError(
                "El correo ya esta registrado."
            ) from exc
        raise RepositoryError(
            "No se pudo actualizar el usuario por una restriccion de datos."
        ) from exc
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError("No se pudo actualizar el usuario.") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def obtener_por_correo(
    correo: object,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Devuelve un usuario y su rol mediante correo normalizado."""
    correo_normalizado = _normalizar_correo(correo)
    return _fetch_one(
        _SELECT_BY_EMAIL_FILE,
        (correo_normalizado,),
        database_path,
    )


def obtener_por_id(
    usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Devuelve un usuario y su rol mediante identificador."""
    return _fetch_one(_SELECT_BY_ID_FILE, (usuario_id,), database_path)


def listar_por_rol(
    rol_nombre: object,
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Lista usuarios seguros pertenecientes exclusivamente al rol indicado."""
    query = _load_query(_SELECT_BY_ROLE_FILE)
    rol_normalizado = _normalizar_rol(rol_nombre)
    connection = None
    cursor = None
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(query, (rol_normalizado,))
        return [dict(row) for row in cursor.fetchall()]
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError("No se pudieron listar los usuarios.") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def crear(
    nombre: object,
    correo: object,
    password_hash: object,
    estado: object,
    rol_id: object,
    database_path: Path | None = None,
) -> int:
    """Persiste un usuario con un hash previamente generado."""
    nombre_normalizado = _normalizar_nombre(nombre)
    correo_normalizado = _normalizar_correo(correo)
    hash_validado = _validar_password_hash(password_hash)
    estado_validado = _validar_estado(estado)
    rol_id_validado = _validar_rol_id(rol_id)
    query = _load_query(_INSERT_FILE)
    connection = None
    cursor = None

    try:
        connection = database_manager.get_connection(database_path)
        cursor = connection.execute(
            query,
            (
                nombre_normalizado,
                correo_normalizado,
                hash_validado,
                estado_validado,
                rol_id_validado,
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        _rollback(connection)
        if _es_correo_duplicado(exc):
            raise DuplicateUserError(
                "El correo ya esta registrado."
            ) from exc
        raise RepositoryError(
            "No se pudo crear el usuario por una restriccion de datos."
        ) from exc
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError("No se pudo crear el usuario.") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def actualizar_datos(
    usuario_id: object,
    nombre: object,
    correo: object,
    database_path: Path | None = None,
) -> bool:
    """Actualiza solamente nombre y correo."""
    usuario_id_validado = _validar_usuario_id(usuario_id)
    nombre_normalizado = _normalizar_nombre(nombre)
    correo_normalizado = _normalizar_correo(correo)
    return _execute_update(
        _UPDATE_DATA_FILE,
        (nombre_normalizado, correo_normalizado, usuario_id_validado),
        database_path,
        duplicate_email=True,
    )


def actualizar_password(
    usuario_id: object,
    password_hash: object,
    database_path: Path | None = None,
) -> bool:
    """Actualiza solamente el hash de contrasena."""
    usuario_id_validado = _validar_usuario_id(usuario_id)
    hash_validado = _validar_password_hash(password_hash)
    return _execute_update(
        _UPDATE_PASSWORD_FILE,
        (hash_validado, usuario_id_validado),
        database_path,
    )


def actualizar_password_y_requerimiento(
    usuario_id: object,
    password_hash: object,
    requiere_cambio_password: object,
    database_path: Path | None = None,
) -> bool:
    """Actualiza hash y requerimiento en una sola transaccion."""
    identifier = _validar_usuario_id(usuario_id)
    hash_validado = _validar_password_hash(password_hash)
    if requiere_cambio_password not in (0, 1):
        raise RepositoryError("El indicador de cambio no es valido.")
    connection = None
    cursor = None
    try:
        connection = database_manager.get_connection(database_path)
        connection.execute("BEGIN IMMEDIATE;")
        cursor = connection.execute(
            _load_query(_UPDATE_PASSWORD_REQUIREMENT_FILE),
            (hash_validado, requiere_cambio_password, identifier),
        )
        if cursor.rowcount < 1:
            raise UsuarioNoEncontradoError(
                "No se encontro el usuario solicitado."
            )
        connection.commit()
        return True
    except EduPassError:
        _rollback(connection)
        raise
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError("No se pudo actualizar la contrasena.") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def contar_activos_por_rol(
    rol_nombre: object,
    database_path: Path | None = None,
) -> int:
    """Cuenta usuarios activos del rol indicado."""
    result = _fetch_one(
        _COUNT_ACTIVE_BY_ROLE_FILE,
        (_normalizar_rol(rol_nombre), ESTADO_ACTIVO),
        database_path,
    )
    if result is None or "total_activos" not in result:
        raise RepositoryError("No se pudieron contar los usuarios activos.")
    try:
        return int(result["total_activos"])
    except (TypeError, ValueError) as exc:
        raise RepositoryError(
            "El total de usuarios activos no es valido."
        ) from exc


def _cambiar_estado_usuario_protegido(
    usuario_id: object,
    nuevo_estado: object,
    actor_usuario_id: object,
    rol_objetivo: object,
    proteger_ultimo_activo: bool,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Cambia el estado validando actor y rol objetivo en una transacción."""
    objetivo_id = _validar_usuario_id(usuario_id)
    actor_id = _validar_usuario_id(actor_usuario_id)
    estado = _validar_estado(nuevo_estado)
    rol = _normalizar_rol(rol_objetivo)
    if rol not in {ROL_ADMINISTRADOR, ROL_ESCANER}:
        raise RepositoryError("El rol objetivo no es valido.")
    if not isinstance(proteger_ultimo_activo, bool):
        raise RepositoryError("La proteccion de usuarios activos no es valida.")

    select_query = _load_query(_SELECT_BY_ID_FILE)
    update_query = _load_query(_UPDATE_STATE_FILE)
    count_query = (
        _load_query(_COUNT_ACTIVE_BY_ROLE_FILE)
        if proteger_ultimo_activo
        else None
    )
    connection = None
    cursors: list[sqlite3.Cursor] = []

    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursors.append(connection.execute("BEGIN IMMEDIATE;"))

        actor_cursor = connection.execute(select_query, (actor_id,))
        cursors.append(actor_cursor)
        actor = _row_to_dict(actor_cursor.fetchone())
        if (
            actor is None
            or actor.get("estado") != ESTADO_ACTIVO
            or actor.get("rol_nombre") != ROL_ADMINISTRADOR
        ):
            raise AuthorizationError(
                "El actor no es un administrador activo."
            )

        objetivo_cursor = connection.execute(select_query, (objetivo_id,))
        cursors.append(objetivo_cursor)
        objetivo = _row_to_dict(objetivo_cursor.fetchone())
        if objetivo is None or objetivo.get("rol_nombre") != rol:
            raise UsuarioNoEncontradoError(
                "No se encontro el usuario solicitado."
            )

        if (
            proteger_ultimo_activo
            and estado == ESTADO_INACTIVO
            and objetivo_id == actor_id
        ):
            raise AutoBloqueoAdministradorError(
                "No puedes desactivar tu propia cuenta."
            )

        if (
            proteger_ultimo_activo
            and estado == ESTADO_INACTIVO
            and objetivo.get("estado") == ESTADO_ACTIVO
        ):
            count_cursor = connection.execute(
                count_query,
                (rol, ESTADO_ACTIVO),
            )
            cursors.append(count_cursor)
            count_row = _row_to_dict(count_cursor.fetchone())
            if count_row is None or int(count_row["total_activos"]) <= 1:
                raise UltimoAdministradorActivoError(
                    "No se puede desactivar al ultimo administrador activo."
                )

        update_cursor = connection.execute(
            update_query,
            (estado, objetivo_id),
        )
        cursors.append(update_cursor)
        if update_cursor.rowcount != 1:
            raise UsuarioNoEncontradoError(
                "No se encontro el usuario solicitado."
            )

        result_cursor = connection.execute(select_query, (objetivo_id,))
        cursors.append(result_cursor)
        result = _row_to_dict(result_cursor.fetchone())
        if result is None:
            raise RepositoryError(
                "No se pudo recuperar el usuario actualizado."
            )

        connection.commit()
        return _safe_user_row(result)
    except EduPassError:
        _rollback(connection)
        raise
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError(
            "No se pudo cambiar el estado del usuario."
        ) from exc
    finally:
        for cursor in cursors:
            cursor.close()
        if connection is not None:
            connection.close()


def cambiar_estado_administrador_protegido(
    usuario_id: object,
    nuevo_estado: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Conserva las protecciones aprobadas para administradores."""
    return _cambiar_estado_usuario_protegido(
        usuario_id,
        nuevo_estado,
        actor_usuario_id,
        ROL_ADMINISTRADOR,
        True,
        database_path,
    )


def cambiar_estado_escaner_protegido(
    usuario_id: object,
    nuevo_estado: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Cambia el estado de un escáner sin reglas del último administrador."""
    return _cambiar_estado_usuario_protegido(
        usuario_id,
        nuevo_estado,
        actor_usuario_id,
        ROL_ESCANER,
        False,
        database_path,
    )
