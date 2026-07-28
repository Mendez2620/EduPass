"""Utilidades internas para tokens opacos y fechas UTC de credenciales."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
import re
import secrets

from edupass.shared.constants import QR_TOKEN_BYTES, QR_TOKEN_PATRON
from edupass.shared.errors import ValidationError


Clock = Callable[[], datetime]
TokenFactory = Callable[[], str]
UTC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
_TOKEN_PATTERN = re.compile(QR_TOKEN_PATRON)


def normalizar_utc(value: datetime) -> datetime:
    """Normaliza un datetime consciente de zona horaria a UTC."""
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValidationError(
            "El reloj debe devolver una fecha con zona horaria."
        )
    return value.astimezone(timezone.utc)


def obtener_utc_actual(clock: Clock | None = None) -> datetime:
    """Obtiene el instante actual desde un reloj inyectable."""
    value = clock() if clock is not None else datetime.now(timezone.utc)
    return normalizar_utc(value)


def serializar_utc(value: datetime) -> str:
    """Serializa un datetime consciente con precision fija y sufijo Z."""
    return normalizar_utc(value).strftime(UTC_FORMAT)


def interpretar_utc(value: str) -> datetime:
    """Interpreta el formato UTC persistido por EduPass."""
    if not isinstance(value, str):
        raise ValidationError("La fecha UTC almacenada no es valida.")
    try:
        parsed = datetime.strptime(value, UTC_FORMAT)
    except ValueError as exc:
        raise ValidationError("La fecha UTC almacenada no es valida.") from exc
    return parsed.replace(tzinfo=timezone.utc)


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
