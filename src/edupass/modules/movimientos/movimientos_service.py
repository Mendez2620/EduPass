"""Reglas de negocio para movimientos transaccionales con QR."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from edupass.modules.credencial_qr._token_utils import (
    calcular_hash_token,
    validar_formato_token,
)
from edupass.persistence.repositories import movimiento_repository
from edupass.shared.constants import (
    PUNTO_PLANTEL_ACCESO_PRINCIPAL,
    PUNTO_PLANTEL_LONGITUD_MAXIMA,
    PUNTOS_PLANTEL_MOVIMIENTO,
    TIPOS_MOVIMIENTO,
    TIPO_MOVIMIENTO_ENTRADA,
)
from edupass.shared.errors import (
    QRInvalidoError,
    RepositoryError,
    TipoMovimientoInvalidoError,
    UsuarioEscanerInvalidoError,
    ValidationError,
)
from edupass.shared.time_utils import Clock, obtener_utc_actual, serializar_utc


_RESULT_KEYS = (
    "movimiento_id",
    "alumno_id",
    "alumno_nombre",
    "tipo_movimiento",
    "fecha_hora",
    "punto_plantel",
    "usuario_id",
    "usuario_nombre",
)


def _normalizar_token(token: object) -> str:
    if not isinstance(token, str):
        raise QRInvalidoError("Token invalido.")
    token_normalizado = token.strip()
    if not token_normalizado:
        raise QRInvalidoError("Token invalido.")
    try:
        return validar_formato_token(token_normalizado)
    except ValidationError as exc:
        raise QRInvalidoError("Token invalido.") from exc


def _normalizar_tipo(tipo_movimiento: object) -> str:
    if not isinstance(tipo_movimiento, str):
        raise TipoMovimientoInvalidoError(
            "El tipo de movimiento no es valido."
        )
    tipo_normalizado = tipo_movimiento.strip().lower()
    if tipo_normalizado not in TIPOS_MOVIMIENTO:
        raise TipoMovimientoInvalidoError(
            "El tipo de movimiento no es valido."
        )
    return tipo_normalizado


def _validar_hash_token(token_hash: object) -> str:
    if not isinstance(token_hash, str) or len(token_hash) != 64:
        raise QRInvalidoError("Token invalido.")
    try:
        int(token_hash, 16)
    except ValueError as exc:
        raise QRInvalidoError("Token invalido.") from exc
    return token_hash.lower()


def _enmascarar_matricula(matricula: str) -> str:
    if len(matricula) <= 4:
        return "*" * len(matricula)
    return ("*" * (len(matricula) - 4)) + matricula[-4:]


def _validar_usuario_id(usuario_id: object) -> int:
    if (
        isinstance(usuario_id, bool)
        or not isinstance(usuario_id, int)
        or usuario_id <= 0
    ):
        raise UsuarioEscanerInvalidoError(
            "El usuario responsable no es valido."
        )
    return usuario_id


def _normalizar_punto(punto_plantel: object) -> str:
    if not isinstance(punto_plantel, str):
        raise ValidationError("El punto del plantel no es valido.")
    punto_normalizado = punto_plantel.strip().lower()
    if (
        not punto_normalizado
        or len(punto_normalizado) > PUNTO_PLANTEL_LONGITUD_MAXIMA
        or punto_normalizado not in PUNTOS_PLANTEL_MOVIMIENTO
    ):
        raise ValidationError("El punto del plantel no es valido.")
    return punto_normalizado


def registrar_movimiento_con_token(
    token: str,
    tipo_movimiento: str,
    usuario_id: int,
    punto_plantel: str = PUNTO_PLANTEL_ACCESO_PRINCIPAL,
    database_path: Path | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Valida la solicitud y delega el registro atomico al repositorio."""
    token_normalizado = _normalizar_token(token)
    tipo_normalizado = _normalizar_tipo(tipo_movimiento)
    usuario_id_validado = _validar_usuario_id(usuario_id)
    punto_normalizado = _normalizar_punto(punto_plantel)
    fecha_hora = serializar_utc(obtener_utc_actual(clock))
    token_hash = calcular_hash_token(token_normalizado)

    movimiento = movimiento_repository.registrar_con_token(
        token_hash,
        tipo_normalizado,
        fecha_hora,
        usuario_id_validado,
        punto_normalizado,
        database_path,
    )
    try:
        result = {key: movimiento[key] for key in _RESULT_KEYS}
    except (KeyError, TypeError) as exc:
        raise RepositoryError(
            "El repositorio devolvio un movimiento incompleto."
        ) from exc

    result["mensaje"] = (
        "Entrada registrada correctamente."
        if tipo_normalizado == TIPO_MOVIMIENTO_ENTRADA
        else "Salida registrada correctamente."
    )
    return result


def registrar_movimiento_automatico_directo(
    token: object,
    usuario_id: object,
    punto_plantel: str = PUNTO_PLANTEL_ACCESO_PRINCIPAL,
    database_path: Path | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Registra el siguiente tipo decidido enteramente por el backend."""
    token_normalizado = _normalizar_token(token)
    usuario_id_validado = _validar_usuario_id(usuario_id)
    punto_normalizado = _normalizar_punto(punto_plantel)
    fecha_hora = serializar_utc(obtener_utc_actual(clock))
    movimiento = movimiento_repository.registrar_directo_automatico_con_token(
        calcular_hash_token(token_normalizado),
        fecha_hora,
        usuario_id_validado,
        punto_normalizado,
        database_path,
    )
    result = {key: movimiento[key] for key in _RESULT_KEYS}
    result["mensaje"] = (
        "Entrada registrada correctamente."
        if result["tipo_movimiento"] == TIPO_MOVIMIENTO_ENTRADA
        else "Salida registrada correctamente."
    )
    return result


def previsualizar_movimiento_con_token(
    token: str,
    database_path: Path | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Valida y determina el tipo sin consumir el QR ni insertar movimientos."""
    token_normalizado = _normalizar_token(token)
    token_hash = calcular_hash_token(token_normalizado)
    fecha_hora = serializar_utc(obtener_utc_actual(clock))
    preview = movimiento_repository.previsualizar_con_token(
        token_hash,
        fecha_hora,
        database_path,
    )
    return {
        "token_hash": token_hash,
        "alumno_nombre": preview["alumno_nombre"],
        "matricula_enmascarada": _enmascarar_matricula(
            preview["alumno_matricula"]
        ),
        "tipo_movimiento": preview["tipo_movimiento"],
    }


def confirmar_movimiento_automatico(
    token_hash: str,
    tipo_esperado: str,
    usuario_id: int,
    punto_plantel: str = PUNTO_PLANTEL_ACCESO_PRINCIPAL,
    database_path: Path | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Recalcula el tipo en la transacción antes de consumir e insertar."""
    hash_validado = _validar_hash_token(token_hash)
    tipo_validado = _normalizar_tipo(tipo_esperado)
    usuario_id_validado = _validar_usuario_id(usuario_id)
    punto_normalizado = _normalizar_punto(punto_plantel)
    fecha_hora = serializar_utc(obtener_utc_actual(clock))

    movimiento = movimiento_repository.registrar_automatico_con_token(
        hash_validado,
        tipo_validado,
        fecha_hora,
        usuario_id_validado,
        punto_normalizado,
        database_path,
    )
    try:
        result = {key: movimiento[key] for key in _RESULT_KEYS}
    except (KeyError, TypeError) as exc:
        raise RepositoryError(
            "El repositorio devolvio un movimiento incompleto."
        ) from exc
    result["mensaje"] = (
        "Entrada registrada correctamente."
        if result["tipo_movimiento"] == TIPO_MOVIMIENTO_ENTRADA
        else "Salida registrada correctamente."
    )
    return result
