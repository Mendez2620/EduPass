"""Utilidades internas para tokens opacos y fechas UTC de credenciales."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import re
import secrets

from edupass.shared.constants import QR_TOKEN_BYTES, QR_TOKEN_PATRON
from edupass.shared.errors import ValidationError
from edupass.shared.time_utils import (
    Clock,
    UTC_FORMAT,
    interpretar_utc,
    normalizar_utc,
    obtener_utc_actual,
    serializar_utc,
)


TokenFactory = Callable[[], str]
_TOKEN_PATTERN = re.compile(QR_TOKEN_PATRON)


def validar_formato_token(token: object) -> str:
    """Valida el token Base64URL aprobado sin incluirlo en errores."""
    if not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None:
        raise ValidationError("El formato del token QR no es valido.")
    return token


def generar_token(token_factory: TokenFactory | None = None) -> str:
    """Genera y valida un token opaco de 32 bytes."""
    token = (
        token_factory()
        if token_factory is not None
        else secrets.token_urlsafe(QR_TOKEN_BYTES)
    )
    return validar_formato_token(token)


def calcular_hash_token(token: str) -> str:
    """Calcula el SHA-256 hexadecimal del token validado."""
    token_validado = validar_formato_token(token)
    return hashlib.sha256(token_validado.encode("ascii")).hexdigest()
