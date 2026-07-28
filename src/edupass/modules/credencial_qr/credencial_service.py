"""Reglas para generar y renovar credenciales QR temporales."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from edupass.modules.alumnos import alumnos_service
from edupass.modules.credencial_qr._token_utils import (
    Clock,
    TokenFactory,
    calcular_hash_token,
    generar_token,
    obtener_utc_actual,
    serializar_utc,
)
from edupass.persistence.repositories import qr_token_repository
from edupass.shared.constants import (
    ESTADO_ALUMNO_ACTIVO,
    QR_VIGENCIA_SEGUNDOS,
)
from edupass.shared.errors import AlumnoInactivoError, QRNoDisponibleError


def _obtener_alumno_activo(
    alumno_id: object,
    database_path: Path | None,
) -> dict[str, Any]:
    alumno = alumnos_service.consultar_alumno_por_id(
        alumno_id,
        database_path,
    )
    if alumno["estado"] != ESTADO_ALUMNO_ACTIVO:
        raise AlumnoInactivoError("El alumno se encuentra inactivo.")
    return alumno


def _enmascarar_matricula(matricula: str) -> str:
    """Conserva cuatro caracteres finales; oculta matriculas mas cortas."""
    if len(matricula) <= 4:
        return "*" * len(matricula)
    return ("*" * (len(matricula) - 4)) + matricula[-4:]


def generar_credencial(
    alumno_id: object,
    database_path: Path | None = None,
    clock: Clock | None = None,
    token_factory: TokenFactory | None = None,
) -> dict[str, Any]:
    """Genera un token opaco y persiste exclusivamente su hash."""
    alumno = _obtener_alumno_activo(alumno_id, database_path)
    ahora = obtener_utc_actual(clock)
    expira_en = ahora + timedelta(seconds=QR_VIGENCIA_SEGUNDOS)
    token = generar_token(token_factory)
    token_hash = calcular_hash_token(token)
    generado_texto = serializar_utc(ahora)
    expira_texto = serializar_utc(expira_en)

    qr_token_repository.reemplazar_token_activo(
        alumno["alumno_id"],
        token_hash,
        generado_texto,
        expira_texto,
        database_path,
    )

    return {
        "alumno_id": alumno["alumno_id"],
        "nombre": alumno["nombre"],
        "matricula_enmascarada": _enmascarar_matricula(
            alumno["matricula"]
        ),
        "grado": alumno["grado"],
        "grupo": alumno["grupo"],
        "estado": alumno["estado"],
        "token": token,
        "generado_en": generado_texto,
        "expira_en": expira_texto,
        "vigencia_segundos": QR_VIGENCIA_SEGUNDOS,
    }


def renovar_token_qr(
    alumno_id: object,
    database_path: Path | None = None,
    clock: Clock | None = None,
    token_factory: TokenFactory | None = None,
) -> dict[str, Any]:
    """Invalida el token activo anterior y genera una credencial nueva."""
    return generar_credencial(
        alumno_id,
        database_path,
        clock,
        token_factory,
    )


def obtener_metadata_vigente(
    alumno_id: object,
    database_path: Path | None = None,
    clock: Clock | None = None,
) -> dict[str, Any]:
    """Obtiene metadatos; el token original no puede reconstruirse."""
    alumno = _obtener_alumno_activo(alumno_id, database_path)
    ahora_texto = serializar_utc(obtener_utc_actual(clock))
    metadata = qr_token_repository.obtener_vigente_por_alumno(
        alumno["alumno_id"],
        ahora_texto,
        database_path,
    )
    if metadata is None:
        raise QRNoDisponibleError("No hay un token vigente disponible.")
    return {
        **metadata,
        "token_recuperable": False,
        "mensaje": "El token original no puede reconstruirse desde su hash.",
    }
