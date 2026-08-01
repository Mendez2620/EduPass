"""Vinculacion uno a uno entre usuarios con rol alumno y alumnos."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edupass.persistence import database_manager
from edupass.shared.constants import ROL_ALUMNO
from edupass.shared.errors import (
    AlumnoNoEncontradoError,
    AlumnoYaTieneUsuarioError,
    ConsultaSqlError,
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