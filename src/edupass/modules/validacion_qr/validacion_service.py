"""Validacion y consumo atomico de tokens QR temporales."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from edupass.modules.credencial_qr._token_utils import (
    Clock,
    calcular_hash_token,
    obtener_utc_actual,
    serializar_utc,
    validar_formato_token,
)
from edupass.persistence.repositories import qr_token_repository
from edupass.shared.errors import (
    AlumnoInactivoError,
    QRInvalidoError,
    QRUtilizadoError,
    QRVencidoError,
    ValidationError,
)


_SUCCESS_MESSAGE = (
    "Token válido y consumido; no se registró ningún movimiento."
)


def _normalizar_token(token: object) -> str:
    if not isinstance(token, str):
        raise QRInvalidoError("El token proporcionado no es válido.")
    token_normalizado = token.strip()
    try:
        return validar_formato_token(token_normalizado)
    except ValidationError as exc:
        raise QRInvalidoError(
            "El token proporcionado no es válido."
        ) from exc


def consumir_token_qr(
    token: object,
    database_path: Path | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Consume un token vigente sin registrar movimientos ni intentos."""
    token_normalizado = _normalizar_token(token)
    token_hash = calcular_hash_token(token_normalizado)
    ahora_texto = serializar_utc(obtener_utc_actual(clock))
    result = qr_token_repository.consumir_condicionalmente(
        token_hash,
        ahora_texto,
        ahora_texto,
        database_path,
    )

    if result.resultado == qr_token_repository.CONSUMO_INEXISTENTE:
        raise QRInvalidoError("El token proporcionado no es válido.")
    if result.resultado == qr_token_repository.CONSUMO_VENCIDO:
        raise QRVencidoError("El token ha vencido.")
    if result.resultado == qr_token_repository.CONSUMO_UTILIZADO:
        raise QRUtilizadoError("El token ya fue utilizado.")
    if result.resultado == qr_token_repository.CONSUMO_INVALIDADO:
        raise QRInvalidoError("El token proporcionado no es válido.")
    if result.resultado == qr_token_repository.CONSUMO_ALUMNO_INACTIVO:
        raise AlumnoInactivoError("El alumno se encuentra inactivo.")
    if result.resultado != qr_token_repository.CONSUMO_CONSUMIDO:
        raise QRInvalidoError("El token proporcionado no es válido.")

    return {
        "resultado": "consumido",
        "mensaje": _SUCCESS_MESSAGE,
        "alumno_id": result.alumno_id,
        "consumido_en": result.consumido_en,
        "no_registro_movimiento": True,
    }
