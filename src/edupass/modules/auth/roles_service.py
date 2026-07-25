"""Reglas y operaciones del dominio de roles de autenticacion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from edupass.persistence.repositories import rol_repository
from edupass.shared.constants import (
    ROL_ADMINISTRADOR,
    ROL_ESCANER,
    ROLES_AUTENTICACION,
)
from edupass.shared.errors import InvalidRoleError


_ROLE_DESCRIPTIONS = {
    ROL_ADMINISTRADOR: "Administracion escolar de EduPass.",
    ROL_ESCANER: "Personal autorizado para escaneo.",
}


def validar_nombre_rol(nombre: object) -> str:
    """Normaliza un rol y rechaza valores fuera del alcance aprobado."""
    if not isinstance(nombre, str):
        raise InvalidRoleError("El rol indicado no esta permitido.")

    nombre_normalizado = nombre.strip().lower()
    if nombre_normalizado not in ROLES_AUTENTICACION:
        raise InvalidRoleError("El rol indicado no esta permitido.")
    return nombre_normalizado


def asegurar_roles_autenticacion(
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Garantiza de forma idempotente los dos roles de autenticacion."""
    return [
        rol_repository.crear_si_no_existe(
            nombre,
            _ROLE_DESCRIPTIONS[nombre],
            database_path,
        )
        for nombre in ROLES_AUTENTICACION
    ]
