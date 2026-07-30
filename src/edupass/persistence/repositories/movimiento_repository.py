"""Persistencia transaccional de movimientos vinculados al consumo QR."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edupass.persistence import database_manager
from edupass.persistence.repositories._qr_consumption import (
    CONSUMO_ALUMNO_INACTIVO,
    CONSUMO_INVALIDADO,
    CONSUMO_INEXISTENTE,
    CONSUMO_UTILIZADO,
    CONSUMO_VENCIDO,
    ResultadoConsumo,
    clasificar_fila_qr,
)
from edupass.shared.constants import (
    ESTADO_ACTIVO,
    QR_ESTADO_ACTIVO,
    QR_ESTADO_UTILIZADO,
    ROL_ESCANER,
    TIPO_MOVIMIENTO_ENTRADA,
    TIPO_MOVIMIENTO_SALIDA,
)
from edupass.shared.errors import (
    AlumnoInactivoError,
    ConsultaSqlError,
    EduPassError,
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    RepositoryError,
    SecuenciaMovimientoError,
    UsuarioEscanerInvalidoError,
)


_SQL_DIRECTORY = Path(__file__).resolve().parent.parent / "sql" / "movimientos"
_SELECT_QR_FILE = "select_qr_for_movement.sql"
_SELECT_USER_FILE = "select_scanner_user_for_movement.sql"
_SELECT_LAST_FILE = "select_last_movimiento_by_alumno.sql"
_CONSUME_QR_FILE = "consume_qr_token_for_movement.sql"
_INSERT_FILE = "insert_movimiento.sql"
_SELECT_BY_ID_FILE = "select_movimiento_by_id.sql"


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


def _raise_for_qr(classification: ResultadoConsumo) -> None:
    if classification.resultado == CONSUMO_INEXISTENTE:
        raise QRInvalidoError("Token invalido.")
    if classification.resultado == CONSUMO_VENCIDO:
        raise QRVencidoError("Token vencido.")
    if classification.resultado == CONSUMO_UTILIZADO:
        raise QRUtilizadoError("Token ya utilizado.")
    if classification.resultado == CONSUMO_INVALIDADO:
        raise QRInvalidoError("Token invalido.")
    if classification.resultado == CONSUMO_ALUMNO_INACTIVO:
        raise AlumnoInactivoError("Alumno inactivo.")
    if classification.resultado != QR_ESTADO_ACTIVO:
        raise QRInvalidoError("Token invalido.")


def _validar_usuario_escaner(row: dict[str, Any] | None) -> None:
    if (
        row is None
        or row["usuario_estado"] != ESTADO_ACTIVO
        or row["rol_nombre"] != ROL_ESCANER
    ):
        raise UsuarioEscanerInvalidoError(
            "El usuario responsable no es un escaner activo."
        )


def _validar_secuencia(
    ultimo: dict[str, Any] | None,
    tipo_movimiento: str,
) -> None:
    if ultimo is None:
        if tipo_movimiento == TIPO_MOVIMIENTO_SALIDA:
            raise SecuenciaMovimientoError(
                "No se puede registrar una salida sin una entrada previa."
            )
        return

    ultimo_tipo = ultimo["tipo_movimiento"]
    if (
        ultimo_tipo == TIPO_MOVIMIENTO_ENTRADA
        and tipo_movimiento == TIPO_MOVIMIENTO_ENTRADA
    ):
        raise SecuenciaMovimientoError(
            "No se puede registrar otra entrada sin una salida previa."
        )
    if (
        ultimo_tipo == TIPO_MOVIMIENTO_SALIDA
        and tipo_movimiento == TIPO_MOVIMIENTO_SALIDA
    ):
        raise SecuenciaMovimientoError(
            "No se puede registrar otra salida sin una nueva entrada."
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
        return _row_to_dict(cursor.fetchone())
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError("No se pudo consultar el movimiento.") from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def registrar_con_token(
    token_hash: str,
    tipo_movimiento: str,
    fecha_hora: str,
    usuario_id: int,
    punto_plantel: str,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Consume el QR e inserta el movimiento en una sola transaccion."""
    select_qr_query = _load_query(_SELECT_QR_FILE)
    select_user_query = _load_query(_SELECT_USER_FILE)
    select_last_query = _load_query(_SELECT_LAST_FILE)
    consume_qr_query = _load_query(_CONSUME_QR_FILE)
    insert_query = _load_query(_INSERT_FILE)
    select_by_id_query = _load_query(_SELECT_BY_ID_FILE)
    connection = None
    cursors: list[sqlite3.Cursor] = []

    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE;")

        qr_cursor = connection.execute(select_qr_query, (token_hash,))
        cursors.append(qr_cursor)
        qr_row = _row_to_dict(qr_cursor.fetchone())
        classification = clasificar_fila_qr(qr_row, fecha_hora)
        _raise_for_qr(classification)

        user_cursor = connection.execute(select_user_query, (usuario_id,))
        cursors.append(user_cursor)
        user_row = _row_to_dict(user_cursor.fetchone())
        _validar_usuario_escaner(user_row)

        last_cursor = connection.execute(
            select_last_query,
            (classification.alumno_id,),
        )
        cursors.append(last_cursor)
        last_row = _row_to_dict(last_cursor.fetchone())
        _validar_secuencia(last_row, tipo_movimiento)

        consume_cursor = connection.execute(
            consume_qr_query,
            (
                fecha_hora,
                QR_ESTADO_UTILIZADO,
                token_hash,
                QR_ESTADO_ACTIVO,
                fecha_hora,
            ),
        )
        cursors.append(consume_cursor)
        if consume_cursor.rowcount != 1:
            retry_cursor = connection.execute(select_qr_query, (token_hash,))
            cursors.append(retry_cursor)
            retry_row = _row_to_dict(retry_cursor.fetchone())
            _raise_for_qr(clasificar_fila_qr(retry_row, fecha_hora))
            raise RepositoryError("No se pudo consumir el token QR.")

        insert_cursor = connection.execute(
            insert_query,
            (
                classification.alumno_id,
                tipo_movimiento,
                fecha_hora,
                punto_plantel,
                usuario_id,
            ),
        )
        cursors.append(insert_cursor)
        movimiento_id = int(insert_cursor.lastrowid)

        result_cursor = connection.execute(
            select_by_id_query,
            (movimiento_id,),
        )
        cursors.append(result_cursor)
        result = _row_to_dict(result_cursor.fetchone())
        if result is None:
            raise RepositoryError(
                "No se pudo recuperar el movimiento despues de registrarlo."
            )

        connection.commit()
        return result
    except EduPassError:
        _rollback(connection)
        raise
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        _rollback(connection)
        raise RepositoryError("No se pudo registrar el movimiento.") from exc
    finally:
        for cursor in cursors:
            cursor.close()
        if connection is not None:
            connection.close()


def obtener_ultimo_por_alumno(
    alumno_id: int,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Obtiene el ultimo movimiento historico de un alumno."""
    return _fetch_one(_SELECT_LAST_FILE, (alumno_id,), database_path)


def obtener_por_id(
    movimiento_id: int,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Obtiene un movimiento seguro por identificador."""
    return _fetch_one(_SELECT_BY_ID_FILE, (movimiento_id,), database_path)
