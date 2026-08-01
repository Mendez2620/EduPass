"""Operaciones seguras del portal personal del alumno."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from edupass.modules.credencial_qr import credencial_service
from edupass.modules.credencial_qr._token_utils import Clock, TokenFactory
from edupass.modules.historial import historial_service
from edupass.persistence.repositories import (
    usuario_alumno_repository,
    usuario_repository,
)
from edupass.shared.constants import ESTADO_ACTIVO, ROL_ALUMNO
from edupass.shared.errors import (
    AlumnoInactivoError,
    AuthenticationError,
    UsuarioNoEncontradoError,
    UsuarioNoEsAlumnoError,
    ValidationError,
    VinculoUsuarioAlumnoNoEncontradoError,
)


def _validar_id(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(
            f"El identificador de {field_name} debe ser un entero mayor que cero."
        )
    return value


def _resolver_alumno_propio(
    usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Resuelve el alumno activo exclusivamente desde una cuenta activa."""
    identifier = _validar_id(usuario_id, "usuario")
    usuario = usuario_repository.obtener_por_id(identifier, database_path)
    if usuario is None:
        raise UsuarioNoEncontradoError(
            "No se encontro el usuario solicitado."
        )
    if usuario.get("rol_nombre") != ROL_ALUMNO:
        raise UsuarioNoEsAlumnoError("El usuario no tiene el rol alumno.")
    if usuario.get("estado") != ESTADO_ACTIVO:
        raise AuthenticationError("La cuenta no esta disponible.")

    vinculo = usuario_alumno_repository.obtener_por_usuario(
        identifier, database_path
    )
    if (
        vinculo is None
        or vinculo.get("usuario_id") != identifier
        or vinculo.get("rol_nombre") != ROL_ALUMNO
        or not isinstance(vinculo.get("alumno_id"), int)
        or isinstance(vinculo.get("alumno_id"), bool)
        or vinculo["alumno_id"] <= 0
    ):
        raise VinculoUsuarioAlumnoNoEncontradoError(
            "No se encontró la vinculación solicitada."
        )
    if vinculo.get("usuario_estado") != ESTADO_ACTIVO:
        raise AuthenticationError("La cuenta no esta disponible.")
    if vinculo.get("alumno_estado") != ESTADO_ACTIVO:
        raise AlumnoInactivoError("El alumno se encuentra inactivo.")

    return {
        "usuario_id": identifier,
        "alumno_id": vinculo["alumno_id"],
        "nombre": vinculo["alumno_nombre"],
        "matricula": vinculo["matricula"],
        "grado": vinculo["grado"],
        "grupo": vinculo["grupo"],
        "alumno_estado": vinculo["alumno_estado"],
        "correo": vinculo["correo"],
        "usuario_estado": vinculo["usuario_estado"],
    }


def obtener_perfil_propio(
    usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Devuelve el perfil escolar seguro de la cuenta autenticada."""
    return _resolver_alumno_propio(usuario_id, database_path)


def generar_credencial_propia(
    usuario_id: object,
    database_path: Path | None = None,
    clock: Clock | None = None,
    token_factory: TokenFactory | None = None,
) -> dict[str, Any]:
    """Genera una credencial para el alumno resuelto desde la cuenta."""
    perfil = _resolver_alumno_propio(usuario_id, database_path)
    return credencial_service.generar_credencial(
        perfil["alumno_id"], database_path, clock, token_factory
    )


def renovar_credencial_propia(
    usuario_id: object,
    database_path: Path | None = None,
    clock: Clock | None = None,
    token_factory: TokenFactory | None = None,
) -> dict[str, Any]:
    """Renueva la credencial del alumno resuelto desde la cuenta."""
    perfil = _resolver_alumno_propio(usuario_id, database_path)
    return credencial_service.renovar_token_qr(
        perfil["alumno_id"], database_path, clock, token_factory
    )


def consultar_historial_propio(
    usuario_id: object,
    pagina: object = 1,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Consulta el historial del alumno vinculado, con paginacion historica."""
    perfil = _resolver_alumno_propio(usuario_id, database_path)
    return historial_service.consultar_historial_alumno(
        perfil["alumno_id"], pagina, database_path=database_path
    )


def consultar_movimiento_propio(
    usuario_id: object,
    movimiento_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Consulta un movimiento sólo si pertenece al alumno vinculado."""
    perfil = _resolver_alumno_propio(usuario_id, database_path)
    movement_id = _validar_id(movimiento_id, "movimiento")
    return historial_service.consultar_movimiento(
        movement_id,
        perfil["alumno_id"],
        database_path,
    )