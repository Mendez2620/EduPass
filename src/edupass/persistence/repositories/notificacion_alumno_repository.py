"""Persistencia segura de notificaciones internas del alumno."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edupass.persistence import database_manager
from edupass.shared.errors import RepositoryError


def _connect(database_path: Path | None) -> sqlite3.Connection:
    connection = database_manager.get_connection(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def listar_por_alumno(
    alumno_id: int,
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    connection = None
    try:
        connection = _connect(database_path)
        rows = connection.execute(
            """
            SELECT
                notificaciones_alumno.notificacion_id,
                notificaciones_alumno.leida,
                notificaciones_alumno.creada_en,
                movimientos.movimiento_id,
                movimientos.tipo_movimiento,
                movimientos.fecha_hora
            FROM notificaciones_alumno
            INNER JOIN movimientos
                ON movimientos.movimiento_id = notificaciones_alumno.movimiento_id
            WHERE notificaciones_alumno.alumno_id = ?
              AND movimientos.alumno_id = notificaciones_alumno.alumno_id
            ORDER BY notificaciones_alumno.creada_en DESC,
                     notificaciones_alumno.notificacion_id DESC;
            """,
            (alumno_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError("No se pudieron consultar las notificaciones.") from exc
    finally:
        if connection is not None:
            connection.close()


def contar_no_leidas(
    alumno_id: int,
    database_path: Path | None = None,
) -> int:
    connection = None
    try:
        connection = _connect(database_path)
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM notificaciones_alumno
            WHERE alumno_id = ? AND leida = 0;
            """,
            (alumno_id,),
        ).fetchone()
        return int(row[0])
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        raise RepositoryError("No se pudo contar las notificaciones.") from exc
    finally:
        if connection is not None:
            connection.close()


def marcar_leida(
    alumno_id: int,
    notificacion_id: int,
    database_path: Path | None = None,
) -> bool:
    connection = None
    try:
        connection = _connect(database_path)
        cursor = connection.execute(
            """
            UPDATE notificaciones_alumno
            SET leida = 1
            WHERE notificacion_id = ? AND alumno_id = ?;
            """,
            (notificacion_id, alumno_id),
        )
        connection.commit()
        return cursor.rowcount == 1
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        if connection is not None:
            connection.rollback()
        raise RepositoryError("No se pudo actualizar la notificación.") from exc
    finally:
        if connection is not None:
            connection.close()


def marcar_todas_leidas(
    alumno_id: int,
    database_path: Path | None = None,
) -> int:
    connection = None
    try:
        connection = _connect(database_path)
        cursor = connection.execute(
            """
            UPDATE notificaciones_alumno
            SET leida = 1
            WHERE alumno_id = ? AND leida = 0;
            """,
            (alumno_id,),
        )
        connection.commit()
        return cursor.rowcount
    except (database_manager.DatabaseManagerError, sqlite3.Error) as exc:
        if connection is not None:
            connection.rollback()
        raise RepositoryError("No se pudieron actualizar las notificaciones.") from exc
    finally:
        if connection is not None:
            connection.close()
