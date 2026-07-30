"""Clasificacion interna compartida para el consumo de tokens QR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from edupass.shared.constants import (
    ESTADO_ALUMNO_ACTIVO,
    QR_ESTADO_ACTIVO,
    QR_ESTADO_INVALIDADO,
    QR_ESTADO_UTILIZADO,
)


CONSUMO_CONSUMIDO = "consumido"
CONSUMO_INEXISTENTE = "inexistente"
CONSUMO_VENCIDO = "vencido"
CONSUMO_UTILIZADO = "utilizado"
CONSUMO_INVALIDADO = "invalidado"
CONSUMO_ALUMNO_INACTIVO = "alumno_inactivo"


@dataclass(frozen=True)
class ResultadoConsumo:
    """Clasificacion interna de un intento atomico de consumo."""

    resultado: str
    qr_id: int | None = None
    alumno_id: int | None = None
    consumido_en: str | None = None


def clasificar_fila_qr(
    row: Mapping[str, Any] | None,
    ahora: str,
) -> ResultadoConsumo:
    """Clasifica una fila QR sin exponer token ni hash."""
    if row is None:
        return ResultadoConsumo(CONSUMO_INEXISTENTE)

    common = {
        "qr_id": row["qr_id"],
        "alumno_id": row["alumno_id"],
    }
    qr_estado = row.get("qr_estado", row.get("estado"))
    if row["alumno_estado"] != ESTADO_ALUMNO_ACTIVO:
        return ResultadoConsumo(CONSUMO_ALUMNO_INACTIVO, **common)
    if qr_estado == QR_ESTADO_UTILIZADO or row["usado_en"] is not None:
        return ResultadoConsumo(CONSUMO_UTILIZADO, **common)
    if qr_estado == QR_ESTADO_INVALIDADO:
        return ResultadoConsumo(CONSUMO_INVALIDADO, **common)
    if qr_estado != QR_ESTADO_ACTIVO:
        return ResultadoConsumo(CONSUMO_INVALIDADO, **common)
    if row["expira_en"] <= ahora:
        return ResultadoConsumo(CONSUMO_VENCIDO, **common)
    return ResultadoConsumo(QR_ESTADO_ACTIVO, **common)
