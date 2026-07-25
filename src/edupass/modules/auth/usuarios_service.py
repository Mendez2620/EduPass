"""Autenticacion y aprovisionamiento seguro de usuarios de EduPass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from edupass.modules.auth import roles_service
from edupass.persistence.repositories import usuario_repository
from edupass.shared.constants import (
    ESTADO_ACTIVO,
    ROL_ADMINISTRADOR,
    ROL_ESCANER,
    ROLES_AUTENTICACION,
)
from edupass.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    DuplicateUserError,
    InvalidRoleError,
    RepositoryError,
    ValidationError,
)


_AUTHENTICATION_MESSAGE = (
    "No fue posible iniciar sesi?n con las credenciales proporcionadas."
)
_MINIMUM_PASSWORD_LENGTH = 8
_SAFE_USER_FIELDS = (
    "usuario_id",
    "nombre",
    "correo",
    "estado",
    "rol_id",
    "rol_nombre",
)


def _normalizar_texto_obligatorio(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValidationError(f"El campo {campo} es obligatorio.")
    return valor.strip()


def _normalizar_correo(correo: object) -> str:
    return _normalizar_texto_obligatorio(correo, "correo").lower()


def _validar_password_creacion(password: object) -> str:
    if not isinstance(password, str) or not password:
        raise ValidationError("La contrasena es obligatoria.")
    if len(password) < _MINIMUM_PASSWORD_LENGTH:
        raise ValidationError(
            "La contrasena debe tener al menos 8 caracteres."
        )
    return password


def _validar_usuario_id(usuario_id: object) -> int:
    if (
        isinstance(usuario_id, bool)
        or not isinstance(usuario_id, int)
        or usuario_id <= 0
    ):
        raise ValidationError(
            "El identificador del usuario debe ser un entero mayor que cero."
        )
    return usuario_id


def _usuario_seguro(usuario: dict[str, Any]) -> dict[str, Any]:
    return {campo: usuario[campo] for campo in _SAFE_USER_FIELDS}


def _authentication_error() -> AuthenticationError:
    return AuthenticationError(_AUTHENTICATION_MESSAGE)


def autenticar_usuario(
    correo: object,
    password: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Autentica credenciales y devuelve datos seguros para una sesion."""
    try:
        correo_normalizado = _normalizar_correo(correo)
    except ValidationError as exc:
        raise _authentication_error() from exc

    if not isinstance(password, str) or not password:
        raise _authentication_error()

    usuario = usuario_repository.obtener_por_correo(
        correo_normalizado,
        database_path,
    )
    if usuario is None:
        raise _authentication_error()

    try:
        password_valido = check_password_hash(
            usuario["password_hash"],
            password,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise _authentication_error() from exc

    if not password_valido:
        raise _authentication_error()
    if usuario.get("estado") != ESTADO_ACTIVO:
        raise _authentication_error()
    if usuario.get("rol_nombre") not in ROLES_AUTENTICACION:
        raise _authentication_error()

    return _usuario_seguro(usuario)


def obtener_usuario_sesion(
    usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any] | None:
    """Recupera un usuario activo y seguro para una futura sesion."""
    usuario_id_validado = _validar_usuario_id(usuario_id)
    usuario = usuario_repository.obtener_por_id(
        usuario_id_validado,
        database_path,
    )

    if usuario is None or usuario.get("estado") != ESTADO_ACTIVO:
        return None
    if usuario.get("rol_nombre") not in ROLES_AUTENTICACION:
        return None
    return _usuario_seguro(usuario)


def validar_rol(
    usuario: object,
    rol_requerido: object,
) -> bool:
    """Valida el rol o genera AuthorizationError para acceso denegado."""
    rol_normalizado = roles_service.validar_nombre_rol(rol_requerido)
    if not isinstance(usuario, dict):
        raise AuthorizationError("El usuario no tiene el rol requerido.")
    if usuario.get("rol_nombre") != rol_normalizado:
        raise AuthorizationError("El usuario no tiene el rol requerido.")
    return True


def crear_usuario_demo(
    nombre: object,
    correo: object,
    password: object,
    rol: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Crea una cuenta de demostracion activa sin exponer su hash."""
    nombre_normalizado = _normalizar_texto_obligatorio(nombre, "nombre")
    correo_normalizado = _normalizar_correo(correo)
    password_validado = _validar_password_creacion(password)
    rol_normalizado = roles_service.validar_nombre_rol(rol)

    roles = roles_service.asegurar_roles_autenticacion(database_path)
    roles_por_nombre = {item["nombre"]: item for item in roles}
    rol_real = roles_por_nombre.get(rol_normalizado)
    if rol_real is None:
        raise InvalidRoleError("El rol indicado no esta permitido.")

    if usuario_repository.obtener_por_correo(
        correo_normalizado,
        database_path,
    ) is not None:
        raise DuplicateUserError("El correo ya esta registrado.")

    usuario_id = usuario_repository.crear(
        nombre_normalizado,
        correo_normalizado,
        generate_password_hash(password_validado),
        ESTADO_ACTIVO,
        rol_real["rol_id"],
        database_path,
    )
    usuario = usuario_repository.obtener_por_id(usuario_id, database_path)
    if usuario is None:
        raise RepositoryError(
            "No se pudo recuperar el usuario despues de crearlo."
        )
    return _usuario_seguro(usuario)


__all__ = [
    "ROL_ADMINISTRADOR",
    "ROL_ESCANER",
    "autenticar_usuario",
    "crear_usuario_demo",
    "obtener_usuario_sesion",
    "validar_rol",
]
