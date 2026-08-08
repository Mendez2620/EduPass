"""Reglas de administracion de cuentas vinculadas a alumnos."""

from __future__ import annotations

from pathlib import Path
import secrets
from typing import Any

from werkzeug.security import generate_password_hash

from edupass.modules.auth import roles_service
from edupass.modules.alumnos import alumnos_service
from edupass.persistence.repositories import usuario_alumno_repository
from edupass.shared.constants import ESTADO_ACTIVO, ESTADO_INACTIVO, ROL_ALUMNO
from edupass.shared.errors import (
    AlumnoInactivoError,
    UsuarioNoEsAlumnoError,
    ValidationError,
    VinculoUsuarioAlumnoNoEncontradoError,
)


_MINIMUM_PASSWORD_LENGTH = 8
_MAXIMUM_PASSWORD_LENGTH = 256
_SAFE_ACCOUNT_FIELDS = (
    "usuario_alumno_id",
    "usuario_id",
    "alumno_id",
    "usuario_nombre",
    "correo",
    "usuario_estado",
    "rol_nombre",
    "alumno_nombre",
    "matricula",
    "grado",
    "grupo",
    "alumno_estado",
    "requiere_cambio_password",
)


def generar_password_temporal() -> str:
    """Genera una clave temporal criptograficamente segura."""
    password = secrets.token_urlsafe(18)
    return _validar_password(password)


def _validar_id(value: object, entity: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(
            f"El identificador del {entity} debe ser un entero mayor que cero."
        )
    return value


def _normalizar_correo(correo: object) -> str:
    if not isinstance(correo, str) or not correo.strip():
        raise ValidationError("El correo es obligatorio.")
    correo_normalizado = correo.strip().lower()
    if len(correo_normalizado) > 254:
        raise ValidationError("El correo no puede exceder 254 caracteres.")
    return correo_normalizado


def _validar_password(password: object) -> str:
    if not isinstance(password, str) or not password:
        raise ValidationError("La contrasena es obligatoria.")
    if len(password) < _MINIMUM_PASSWORD_LENGTH:
        raise ValidationError(
            "La contrasena debe tener al menos 8 caracteres."
        )
    if len(password) > _MAXIMUM_PASSWORD_LENGTH:
        raise ValidationError(
            "La contrasena no puede exceder 256 caracteres."
        )
    return password


def _cuenta_segura(account: dict[str, Any]) -> dict[str, Any]:
    return {
        field: account[field]
        for field in _SAFE_ACCOUNT_FIELDS
        if field in account
    }


def listar_cuentas_alumno(
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Lista cuentas alumno vinculadas con datos seguros."""
    return [
        _cuenta_segura(account)
        for account in usuario_alumno_repository.listar_cuentas(database_path)
    ]


def listar_alumnos_sin_cuenta(
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Lista los registros escolares que aun no tienen cuenta."""
    return usuario_alumno_repository.listar_alumnos_sin_cuenta(database_path)


def consultar_cuenta_alumno(
    usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Consulta una cuenta alumno vinculada o genera un error controlado."""
    identifier = _validar_id(usuario_id, "usuario")
    account = usuario_alumno_repository.obtener_por_usuario(
        identifier, database_path
    )
    if account is None:
        raise VinculoUsuarioAlumnoNoEncontradoError(
            "No se encontró la vinculación solicitada."
        )
    if account.get("rol_nombre") != ROL_ALUMNO:
        raise UsuarioNoEsAlumnoError("El usuario no tiene el rol alumno.")
    return _cuenta_segura(account)


def crear_cuenta_alumno(
    alumno_id: object,
    correo: object,
    password: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Valida y crea una cuenta alumno vinculada."""
    student_id = _validar_id(alumno_id, "alumno")
    actor_id = _validar_id(actor_usuario_id, "usuario actor")
    normalized_email = _normalizar_correo(correo)
    validated_password = _validar_password(password)
    roles_service.asegurar_roles_sistema(database_path)
    account = usuario_alumno_repository.crear_cuenta_vinculada(
        student_id,
        normalized_email,
        generate_password_hash(validated_password),
        actor_id,
        database_path,
    )
    return _cuenta_segura(account)


def crear_alumno_con_cuenta(
    nombre: object,
    matricula: object,
    grado: object,
    grupo: object,
    fotografia: object,
    alumno_estado: object,
    correo: object,
    cuenta_estado: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Valida y crea alumno, cuenta y vinculo de forma atomica."""
    actor_id = _validar_id(actor_usuario_id, "usuario actor")
    nombre_normalizado = alumnos_service._normalizar_texto_obligatorio(
        nombre, "nombre"
    )
    matricula_normalizada = alumnos_service._normalizar_matricula(matricula)
    grado_normalizado = alumnos_service._normalizar_texto_obligatorio(
        grado, "grado"
    )
    grupo_normalizado = alumnos_service._normalizar_texto_obligatorio(
        grupo, "grupo"
    )
    fotografia_normalizada = alumnos_service._normalizar_fotografia(fotografia)
    alumno_estado_normalizado = alumnos_service._normalizar_estado(alumno_estado)
    correo_normalizado = _normalizar_correo(correo)
    password_temporal = generar_password_temporal()
    if not isinstance(cuenta_estado, str):
        raise ValidationError("El estado de la cuenta no es valido.")
    cuenta_estado_normalizado = cuenta_estado.strip().lower()
    if cuenta_estado_normalizado not in {ESTADO_ACTIVO, ESTADO_INACTIVO}:
        raise ValidationError("El estado de la cuenta no es valido.")
    if (
        alumno_estado_normalizado != ESTADO_ACTIVO
        and cuenta_estado_normalizado == ESTADO_ACTIVO
    ):
        raise AlumnoInactivoError(
            "No se puede activar una cuenta para un alumno inactivo."
        )

    account = usuario_alumno_repository.crear_alumno_con_cuenta(
        nombre_normalizado,
        matricula_normalizada,
        grado_normalizado,
        grupo_normalizado,
        fotografia_normalizada,
        alumno_estado_normalizado,
        correo_normalizado,
        generate_password_hash(password_temporal),
        cuenta_estado_normalizado,
        actor_id,
        database_path,
    )
    return _cuenta_segura(account), password_temporal


def editar_cuenta_alumno(
    usuario_id: object,
    correo: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Actualiza exclusivamente el correo de una cuenta alumno."""
    identifier = _validar_id(usuario_id, "usuario")
    actor_id = _validar_id(actor_usuario_id, "usuario actor")
    normalized_email = _normalizar_correo(correo)
    return _cuenta_segura(
        usuario_alumno_repository.actualizar_correo_cuenta(
            identifier, normalized_email, actor_id, database_path
        )
    )


def generar_password_temporal_cuenta_alumno(
    usuario_id: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Genera temporal, actualiza hash+flag y devuelve la clave una vez."""
    identifier = _validar_id(usuario_id, "usuario")
    actor_id = _validar_id(actor_usuario_id, "usuario actor")
    password_temporal = generar_password_temporal()
    account = _cuenta_segura(
        usuario_alumno_repository.actualizar_password_cuenta(
            identifier,
            generate_password_hash(password_temporal),
            actor_id,
            database_path,
        )
    )
    return account, password_temporal


def activar_cuenta_alumno(
    usuario_id: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Activa una cuenta si su alumno vinculado esta activo."""
    identifier = _validar_id(usuario_id, "usuario")
    actor_id = _validar_id(actor_usuario_id, "usuario actor")
    return _cuenta_segura(
        usuario_alumno_repository.cambiar_estado_cuenta(
            identifier, ESTADO_ACTIVO, actor_id, database_path
        )
    )


def desactivar_cuenta_alumno(
    usuario_id: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Desactiva la cuenta sin eliminar su vinculacion."""
    identifier = _validar_id(usuario_id, "usuario")
    actor_id = _validar_id(actor_usuario_id, "usuario actor")
    return _cuenta_segura(
        usuario_alumno_repository.cambiar_estado_cuenta(
            identifier, ESTADO_INACTIVO, actor_id, database_path
        )
    )
