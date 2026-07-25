"""Operaciones de persistencia para usuarios de autenticacion."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edupass.persistence import database_manager
from edupass.shared.constants import ESTADO_ACTIVO, ESTADO_INACTIVO
from edupass.shared.errors import (
    ConsultaSqlError,
    DuplicateUserError,
    RepositoryError,
)


_SQL_DIRECTORY = Path(__file__).resolve().parent.parent / "sql" / "usuarios"
_SELECT_BY_EMAIL_FILE = "select_usuario_by_correo.sql"
_SELECT_BY_ID_FILE = "select_usuario_by_id.sql"
_INSERT_FILE = "insert_usuario.sql"


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
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError("No se pudo consultar el usuario.") from exc
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
