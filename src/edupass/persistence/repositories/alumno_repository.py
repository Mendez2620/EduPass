"""Operaciones de persistencia para alumnos mediante consultas externas."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edupass.persistence import database_manager
from edupass.shared.errors import (
    ConsultaSqlError,
    MatriculaDuplicadaError,
    RepositoryError,
)


_SQL_DIRECTORY = Path(__file__).resolve().parent.parent / "sql" / "alumnos"

_INSERT_FILE = "insert_alumno.sql"
_SELECT_BY_ID_FILE = "select_alumno_by_id.sql"
_SELECT_BY_MATRICULA_FILE = "select_alumno_by_matricula.sql"
_SELECT_ALL_FILE = "select_all_alumnos.sql"
_EXISTS_MATRICULA_FILE = "exists_alumno_matricula.sql"
_UPDATE_FILE = "update_alumno.sql"
_UPDATE_ESTADO_FILE = "update_alumno_estado.sql"


def _load_query(file_name: str) -> str:
    """Carga una consulta externa y comprueba que contenga texto."""
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


def _is_duplicate_matricula_error(error: sqlite3.IntegrityError) -> bool:
    error_name = getattr(error, "sqlite_errorname", "")
    return (
        error_name == "SQLITE_CONSTRAINT_UNIQUE"
        and "alumnos.matricula" in str(error)
    )


def _rollback(connection: sqlite3.Connection | None) -> None:
    if connection is None:
        return

    try:
        connection.rollback()
    except sqlite3.Error:
        pass


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
        raise RepositoryError(
            "No se pudo completar la consulta de alumnos."
        ) from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def _fetch_all(
    file_name: str,
    database_path: Path | None,
) -> list[dict[str, Any]]:
    query = _load_query(file_name)
    connection = None
    cursor = None

    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError(
            "No se pudo completar la consulta de alumnos."
        ) from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def _execute_update(
    file_name: str,
    parameters: tuple[Any, ...],
    database_path: Path | None,
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
        if _is_duplicate_matricula_error(exc):
            raise MatriculaDuplicadaError(
                "La matrícula ya está registrada."
            ) from exc
        raise RepositoryError(
            "No se pudo completar la actualizacion del alumno."
        ) from exc
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError(
            "No se pudo completar la actualizacion del alumno."
        ) from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def crear_alumno(
    nombre: str,
    matricula: str,
    grado: str,
    grupo: str,
    fotografia: str | None,
    estado: str,
    database_path: Path | None = None,
) -> int:
    """Guarda un alumno y devuelve su identificador."""
    query = _load_query(_INSERT_FILE)
    connection = None
    cursor = None

    try:
        connection = database_manager.get_connection(database_path)
        cursor = connection.execute(
            query,
            (nombre, matricula, grado, grupo, fotografia, estado),
        )
        connection.commit()
        return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        _rollback(connection)
        if _is_duplicate_matricula_error(exc):
            raise MatriculaDuplicadaError(
                "La matrícula ya está registrada."
            ) from exc
        raise RepositoryError(
            "No se pudo crear el alumno por una restriccion de datos."
        ) from exc
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError("No se pudo crear el alumno.") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def obtener_alumno_por_id(
    alumno_id: int,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Devuelve un alumno por identificador o None si no existe."""
    return _fetch_one(_SELECT_BY_ID_FILE, (alumno_id,), database_path)


def obtener_alumno_por_matricula(
    matricula: str,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Devuelve un alumno por matricula o None si no existe."""
    return _fetch_one(
        _SELECT_BY_MATRICULA_FILE,
        (matricula,),
        database_path,
    )


def listar_todos(
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Devuelve todos los alumnos ordenados por identificador."""
    return _fetch_all(_SELECT_ALL_FILE, database_path)


def existe_matricula(
    matricula: str,
    database_path: Path | None = None,
) -> bool:
    """Indica si la matricula recibida ya esta almacenada."""
    result = _fetch_one(
        _EXISTS_MATRICULA_FILE,
        (matricula,),
        database_path,
    )
    return bool(result and result["existe"])


def actualizar_alumno(
    alumno_id: int,
    nombre: str,
    matricula: str,
    grado: str,
    grupo: str,
    fotografia: str | None,
    database_path: Path | None = None,
) -> bool:
    """Actualiza los datos editables de un alumno existente."""
    return _execute_update(
        _UPDATE_FILE,
        (nombre, matricula, grado, grupo, fotografia, alumno_id),
        database_path,
    )


def actualizar_estado_alumno(
    alumno_id: int,
    estado: str,
    database_path: Path | None = None,
) -> bool:
    """Actualiza el estado de un alumno existente."""
    return _execute_update(
        _UPDATE_ESTADO_FILE,
        (estado, alumno_id),
        database_path,
    )
