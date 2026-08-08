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
    EstadoMovimientoCambiadoError,
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
_SELECT_BY_STUDENT_FILE = "select_movimientos_by_alumno.sql"
_COUNT_BY_STUDENT_FILE = "count_movimientos_by_alumno.sql"
_INSERT_NOTIFICATION_FILE = "insert_notificacion_alumno.sql"


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


def _determinar_tipo(ultimo: dict[str, Any] | None) -> str:
    """Determina el siguiente tipo usando la alternancia histórica."""
    if ultimo is None:
        return TIPO_MOVIMIENTO_ENTRADA
    if ultimo["tipo_movimiento"] == TIPO_MOVIMIENTO_ENTRADA:
        return TIPO_MOVIMIENTO_SALIDA
    if ultimo["tipo_movimiento"] == TIPO_MOVIMIENTO_SALIDA:
        return TIPO_MOVIMIENTO_ENTRADA
    raise RepositoryError("El último movimiento contiene un tipo inválido.")


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



def _fetch_all(
    file_name: str,
    alumno_id: int,
    limit: int,
    offset: int,
    database_path: Path | None,
) -> list[dict[str, Any]]:
    """Ejecuta una consulta paginada de solo lectura."""
    query = _load_query(file_name)
    connection = None
    cursor = None
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            query,
            (alumno_id, limit, offset),
        )
        return [
            dict(row)
            for row in cursor.fetchall()
        ]
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError(
            "No se pudo consultar el historial de movimientos."
        ) from exc
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def _registrar_con_token(
    token_hash: str,
    fecha_hora: str,
    usuario_id: int,
    punto_plantel: str,
    database_path: Path | None,
    *,
    tipo_solicitado: str | None = None,
    tipo_esperado: str | None = None,
) -> dict[str, Any]:
    """Calcula, consume e inserta dentro de una sola transacción."""
    select_qr_query = _load_query(_SELECT_QR_FILE)
    select_user_query = _load_query(_SELECT_USER_FILE)
    select_last_query = _load_query(_SELECT_LAST_FILE)
    consume_qr_query = _load_query(_CONSUME_QR_FILE)
    insert_query = _load_query(_INSERT_FILE)
    select_by_id_query = _load_query(_SELECT_BY_ID_FILE)
    insert_notification_query = _load_query(_INSERT_NOTIFICATION_FILE)
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
        if tipo_esperado is None:
            if tipo_solicitado is None:
                tipo_movimiento = _determinar_tipo(last_row)
            else:
                tipo_movimiento = tipo_solicitado
                _validar_secuencia(last_row, tipo_movimiento)
        else:
            tipo_movimiento = _determinar_tipo(last_row)
            if tipo_movimiento != tipo_esperado:
                raise EstadoMovimientoCambiadoError(tipo_movimiento)

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

        notification_cursor = connection.execute(
            insert_notification_query,
            (classification.alumno_id, movimiento_id, fecha_hora),
        )
        cursors.append(notification_cursor)

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


def registrar_con_token(
    token_hash: str,
    tipo_movimiento: str,
    fecha_hora: str,
    usuario_id: int,
    punto_plantel: str,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Conserva el contrato histórico de registro con secuencia validada."""
    return _registrar_con_token(
        token_hash,
        fecha_hora,
        usuario_id,
        punto_plantel,
        database_path,
        tipo_solicitado=tipo_movimiento,
    )


def registrar_automatico_con_token(
    token_hash: str,
    tipo_esperado: str,
    fecha_hora: str,
    usuario_id: int,
    punto_plantel: str,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Recalcula el tipo y registra atómicamente si coincide con el preview."""
    return _registrar_con_token(
        token_hash,
        fecha_hora,
        usuario_id,
        punto_plantel,
        database_path,
        tipo_esperado=tipo_esperado,
    )


def registrar_directo_automatico_con_token(
    token_hash: str,
    fecha_hora: str,
    usuario_id: int,
    punto_plantel: str,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Determina tipo, consume QR e inserta en una sola transaccion."""
    return _registrar_con_token(
        token_hash,
        fecha_hora,
        usuario_id,
        punto_plantel,
        database_path,
    )


def previsualizar_con_token(
    token_hash: str,
    fecha_hora: str,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Valida el QR y determina el siguiente tipo sin escribir en SQLite."""
    select_qr_query = _load_query(_SELECT_QR_FILE)
    select_last_query = _load_query(_SELECT_LAST_FILE)
    connection = None
    cursors: list[sqlite3.Cursor] = []
    try:
        connection = database_manager.get_connection(database_path)
        connection.row_factory = sqlite3.Row
        qr_cursor = connection.execute(select_qr_query, (token_hash,))
        cursors.append(qr_cursor)
        qr_row = _row_to_dict(qr_cursor.fetchone())
        classification = clasificar_fila_qr(qr_row, fecha_hora)
        _raise_for_qr(classification)

        last_cursor = connection.execute(
            select_last_query,
            (classification.alumno_id,),
        )
        cursors.append(last_cursor)
        ultimo = _row_to_dict(last_cursor.fetchone())
        return {
            "alumno_id": classification.alumno_id,
            "alumno_nombre": qr_row["alumno_nombre"],
            "alumno_matricula": qr_row["alumno_matricula"],
            "tipo_movimiento": _determinar_tipo(ultimo),
        }
    except EduPassError:
        raise
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError(
            "No se pudo previsualizar el movimiento."
        ) from exc
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

def listar_por_alumno(
    alumno_id: int,
    limit: int,
    offset: int,
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Lista movimientos seguros del alumno con paginacion controlada."""
    return _fetch_all(
        _SELECT_BY_STUDENT_FILE,
        alumno_id,
        limit,
        offset,
        database_path,
    )


def contar_por_alumno(
    alumno_id: int,
    database_path: Path | None = None,
) -> int:
    """Cuenta los movimientos existentes de un alumno."""
    result = _fetch_one(
        _COUNT_BY_STUDENT_FILE,
        (alumno_id,),
        database_path,
    )
    if result is None or "total_movimientos" not in result:
        raise RepositoryError(
            "No se pudo contar el historial de movimientos."
        )
    try:
        return int(result["total_movimientos"])
    except (TypeError, ValueError) as exc:
        raise RepositoryError(
            "El total de movimientos no es valido."
        ) from exc
