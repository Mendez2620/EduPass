"""Persistencia transaccional de tokens QR mediante SQL externo."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edupass.persistence import database_manager
from edupass.persistence.repositories._qr_consumption import (
    CONSUMO_ALUMNO_INACTIVO,
    CONSUMO_CONSUMIDO,
    CONSUMO_INVALIDADO,
    CONSUMO_INEXISTENTE,
    CONSUMO_UTILIZADO,
    CONSUMO_VENCIDO,
    ResultadoConsumo,
    clasificar_fila_qr,
)
from edupass.shared.constants import (
    QR_ESTADO_ACTIVO,
    QR_ESTADO_INVALIDADO,
    QR_ESTADO_UTILIZADO,
)
from edupass.shared.errors import ConsultaSqlError, RepositoryError


_SQL_DIRECTORY = Path(__file__).resolve().parent.parent / "sql" / "qr_tokens"
_INSERT_FILE = "insert_qr_token.sql"
_SELECT_BY_HASH_FILE = "select_qr_token_by_hash.sql"
_SELECT_METADATA_FILE = "select_qr_token_metadata_by_alumno.sql"
_INVALIDATE_FILE = "invalidate_active_qr_tokens_by_alumno.sql"
_CONSUME_FILE = "consume_qr_token_conditionally.sql"


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


def _rollback(connection: sqlite3.Connection | None) -> None:
    if connection is None:
        return
    try:
        connection.rollback()
    except sqlite3.Error:
        pass


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _classify_row(
    row: dict[str, Any] | None,
    ahora: str,
) -> ResultadoConsumo:
    return clasificar_fila_qr(row, ahora)


def reemplazar_token_activo(
    alumno_id: int,
    token_hash: str,
    generado_en: str,
    expira_en: str,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Invalida tokens activos e inserta uno nuevo en una transaccion."""
    invalidate_query = _load_query(_INVALIDATE_FILE)
    insert_query = _load_query(_INSERT_FILE)
    select_query = _load_query(_SELECT_BY_HASH_FILE)
    connection = None
    cursors: list[sqlite3.Cursor] = []

    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE;")
        cursors.append(
            connection.execute(
                invalidate_query,
                (QR_ESTADO_INVALIDADO, alumno_id, QR_ESTADO_ACTIVO),
            )
        )
        cursors.append(
            connection.execute(
                insert_query,
                (
                    alumno_id,
                    token_hash,
                    generado_en,
                    expira_en,
                    QR_ESTADO_ACTIVO,
                ),
            )
        )
        cursor = connection.execute(select_query, (token_hash,))
        cursors.append(cursor)
        row = _row_to_dict(cursor.fetchone())
        if row is None:
            raise RepositoryError(
                "No se pudo recuperar el token QR despues de crearlo."
            )
        connection.commit()
        return row
    except RepositoryError:
        _rollback(connection)
        raise
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError("No se pudo reemplazar el token QR.") from exc
    finally:
        for cursor in cursors:
            cursor.close()
        if connection is not None:
            connection.close()


def obtener_por_hash(
    token_hash: str,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Obtiene un token interno y el estado de su alumno."""
    query = _load_query(_SELECT_BY_HASH_FILE)
    connection = None
    cursor = None
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(query, (token_hash,))
        return _row_to_dict(cursor.fetchone())
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError("No se pudo consultar el token QR.") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def obtener_vigente_por_alumno(
    alumno_id: int,
    ahora: str,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Obtiene metadatos del token vigente sin exponer hash ni token."""
    query = _load_query(_SELECT_METADATA_FILE)
    connection = None
    cursor = None
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            query,
            (alumno_id, QR_ESTADO_ACTIVO, ahora),
        )
        return _row_to_dict(cursor.fetchone())
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError(
            "No se pudo consultar el token QR vigente."
        ) from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def consumir_condicionalmente(
    token_hash: str,
    ahora: str,
    usado_en: str,
    database_path: Path | None = None,
) -> ResultadoConsumo:
    """Clasifica y consume un token una sola vez bajo bloqueo de escritura."""
    select_query = _load_query(_SELECT_BY_HASH_FILE)
    consume_query = _load_query(_CONSUME_FILE)
    connection = None
    cursors: list[sqlite3.Cursor] = []

    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE;")
        select_cursor = connection.execute(select_query, (token_hash,))
        cursors.append(select_cursor)
        row = _row_to_dict(select_cursor.fetchone())
        classification = _classify_row(row, ahora)
        if classification.resultado != QR_ESTADO_ACTIVO:
            connection.commit()
            return classification

        update_cursor = connection.execute(
            consume_query,
            (
                usado_en,
                QR_ESTADO_UTILIZADO,
                token_hash,
                QR_ESTADO_ACTIVO,
                ahora,
            ),
        )
        cursors.append(update_cursor)
        if update_cursor.rowcount == 1:
            connection.commit()
            return ResultadoConsumo(
                CONSUMO_CONSUMIDO,
                qr_id=classification.qr_id,
                alumno_id=classification.alumno_id,
                consumido_en=usado_en,
            )

        retry_cursor = connection.execute(select_query, (token_hash,))
        cursors.append(retry_cursor)
        retry_row = _row_to_dict(retry_cursor.fetchone())
        retry_result = _classify_row(retry_row, ahora)
        connection.commit()
        return retry_result
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError("No se pudo consumir el token QR.") from exc
    finally:
        for cursor in cursors:
            cursor.close()
        if connection is not None:
            connection.close()
