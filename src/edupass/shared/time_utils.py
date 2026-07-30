"""Utilidades compartidas para fechas conscientes y persistencia UTC."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from edupass.shared.errors import ValidationError


Clock = Callable[[], datetime]
UTC_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


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
