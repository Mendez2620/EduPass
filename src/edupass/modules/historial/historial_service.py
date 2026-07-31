"""Consulta segura y paginada del historial de movimientos."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from edupass.modules.alumnos import alumnos_service
from edupass.persistence.repositories import movimiento_repository
from edupass.shared.constants import HISTORIAL_TAMANO_PAGINA
from edupass.shared.errors import (
    MovimientoNoEncontradoError,
    ValidationError,
)


_ALUMNO_KEYS = (
    "alumno_id",
    "nombre",
    "matricula",
    "grado",
    "grupo",
    "estado",
)
_MOVIMIENTO_KEYS = (
    "movimiento_id",
    "alumno_id",
    "alumno_nombre",
    "matricula",
    "tipo_movimiento",
    "fecha_hora",
    "punto_plantel",
    "usuario_id",
    "usuario_nombre",
)


def _validar_entero_positivo(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(
            f"El campo {field_name} debe ser un entero mayor que cero."
        )
    return value


def _alumno_seguro(alumno: dict[str, Any]) -> dict[str, Any]:
    return {key: alumno[key] for key in _ALUMNO_KEYS}


def _movimiento_seguro(movimiento: dict[str, Any]) -> dict[str, Any]:
    return {key: movimiento.get(key) for key in _MOVIMIENTO_KEYS}


def consultar_historial_alumno(
    alumno_id: int,
    pagina: int = 1,
    tamano_pagina: int = HISTORIAL_TAMANO_PAGINA,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Consulta el historial de un alumno existente, mas reciente primero."""
    alumno_id_validado = _validar_entero_positivo(alumno_id, "alumno_id")
    pagina_validada = _validar_entero_positivo(pagina, "pagina")
    tamano_validado = _validar_entero_positivo(
        tamano_pagina,
        "tamano_pagina",
    )
    if tamano_validado > HISTORIAL_TAMANO_PAGINA:
        raise ValidationError(
            "El tamano de pagina no puede ser mayor que 50."
        )

    alumno = alumnos_service.consultar_alumno_por_id(
        alumno_id_validado,
        database_path,
    )
    total_movimientos = movimiento_repository.contar_por_alumno(
        alumno_id_validado,
        database_path,
    )
    total_paginas = (
        (total_movimientos + tamano_validado - 1) // tamano_validado
        if total_movimientos
        else 0
    )
    if total_paginas and pagina_validada > total_paginas:
        raise MovimientoNoEncontradoError(
            "La pagina de historial solicitada no existe."
        )

    offset = (pagina_validada - 1) * tamano_validado
    movimientos = movimiento_repository.listar_por_alumno(
        alumno_id_validado,
        tamano_validado,
        offset,
        database_path,
    )
    return {
        "alumno": _alumno_seguro(alumno),
        "movimientos": [
            _movimiento_seguro(movimiento)
            for movimiento in movimientos
        ],
        "paginacion": {
            "pagina": pagina_validada,
            "tamano_pagina": tamano_validado,
            "total_movimientos": total_movimientos,
            "total_paginas": total_paginas,
            "tiene_anterior": pagina_validada > 1,
            "tiene_siguiente": pagina_validada < total_paginas,
        },
    }


def consultar_movimiento(
    movimiento_id: int,
    alumno_id: int | None = None,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Consulta un detalle seguro y comprueba su pertenencia al alumno."""
    movimiento_id_validado = _validar_entero_positivo(
        movimiento_id,
        "movimiento_id",
    )
    alumno_id_validado = (
        _validar_entero_positivo(alumno_id, "alumno_id")
        if alumno_id is not None
        else None
    )
    movimiento = movimiento_repository.obtener_por_id(
        movimiento_id_validado,
        database_path,
    )
    if movimiento is None or (
        alumno_id_validado is not None
        and movimiento["alumno_id"] != alumno_id_validado
    ):
        raise MovimientoNoEncontradoError(
            "No se encontro el movimiento solicitado."
        )

    alumno = alumnos_service.consultar_alumno_por_id(
        movimiento["alumno_id"],
        database_path,
    )
    return {
        "movimiento_id": movimiento["movimiento_id"],
        "alumno_id": movimiento["alumno_id"],
        "alumno_nombre": movimiento["alumno_nombre"],
        "matricula": alumno["matricula"],
        "tipo_movimiento": movimiento["tipo_movimiento"],
        "fecha_hora": movimiento["fecha_hora"],
        "punto_plantel": movimiento["punto_plantel"],
        "usuario_id": movimiento["usuario_id"],
        "usuario_nombre": movimiento["usuario_nombre"],
    }
