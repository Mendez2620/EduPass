"""Operaciones de persistencia para roles de autenticacion."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edupass.persistence import database_manager
from edupass.shared.errors import ConsultaSqlError, RepositoryError


_SQL_DIRECTORY = Path(__file__).resolve().parent.parent / "sql" / "roles"
_SELECT_BY_NAME_FILE = "select_rol_by_nombre.sql"
_INSERT_IF_MISSING_FILE = "insert_rol_if_missing.sql"


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


def _normalizar_nombre(nombre: object) -> str:
    if not isinstance(nombre, str) or not nombre.strip():
        raise RepositoryError("El nombre del rol es obligatorio.")
    return nombre.strip().lower()


def _rollback(connection: sqlite3.Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.rollback()
    except sqlite3.Error:
        pass


def obtener_por_nombre(
    nombre: object,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Devuelve un rol por su nombre normalizado."""
    nombre_normalizado = _normalizar_nombre(nombre)
    query = _load_query(_SELECT_BY_NAME_FILE)
    connection = None
    cursor = None

    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(query, (nombre_normalizado,))
        row = cursor.fetchone()
        return dict(row) if row is not None else None
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError("No se pudo consultar el rol.") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def crear_si_no_existe(
    nombre: object,
    descripcion: object = None,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Crea un rol de forma idempotente y devuelve el registro real."""
    nombre_normalizado = _normalizar_nombre(nombre)
    if descripcion is not None and not isinstance(descripcion, str):
        raise RepositoryError("La descripcion del rol debe ser texto o None.")
    descripcion_normalizada = (
        descripcion.strip() or None if isinstance(descripcion, str) else None
    )

    insert_query = _load_query(_INSERT_IF_MISSING_FILE)
    select_query = _load_query(_SELECT_BY_NAME_FILE)
    connection = None
    insert_cursor = None
    select_cursor = None

    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        insert_cursor = connection.execute(
            insert_query,
            (nombre_normalizado, descripcion_normalizada),
        )
        select_cursor = connection.execute(
            select_query,
            (nombre_normalizado,),
        )
        row = select_cursor.fetchone()
        if row is None:
            raise RepositoryError(
                "No se pudo recuperar el rol despues de crearlo."
            )
        connection.commit()
        return dict(row)
    except RepositoryError:
        _rollback(connection)
        raise
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError("No se pudo crear o consultar el rol.") from exc
    finally:
        if insert_cursor is not None:
            insert_cursor.close()
        if select_cursor is not None:
            select_cursor.close()
        if connection is not None:
            connection.close()
