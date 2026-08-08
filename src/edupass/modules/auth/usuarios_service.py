"""Autenticacion y aprovisionamiento seguro de usuarios de EduPass."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash

from edupass.modules.auth import roles_service
from edupass.persistence.repositories import (
    usuario_alumno_repository,
    usuario_repository,
)
from edupass.shared.constants import (
    ESTADO_ACTIVO,
    ESTADO_INACTIVO,
    ROL_ADMINISTRADOR,
    ROL_ALUMNO,
    ROL_ESCANER,
    ROLES_AUTENTICACION,
)
from edupass.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    DuplicateUserError,
    InvalidRoleError,
    RepositoryError,
    UsuarioNoEncontradoError,
    ValidationError,
)


_AUTHENTICATION_MESSAGE = (
    "No fue posible iniciar sesi?n con las credenciales proporcionadas."
)
_MINIMUM_PASSWORD_LENGTH = 8
_MAXIMUM_PASSWORD_LENGTH = 256
_SAFE_USER_FIELDS = (
    "usuario_id",
    "nombre",
    "correo",
    "estado",
    "rol_id",
    "rol_nombre",
    "requiere_cambio_password",
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
    if len(password) > _MAXIMUM_PASSWORD_LENGTH:
        raise ValidationError(
            "La contrasena no puede exceder 256 caracteres."
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
    return {campo: usuario.get(campo, 0) for campo in _SAFE_USER_FIELDS}


def cambiar_password_obligatorio_alumno(
    usuario_id: object,
    password_actual: object,
    password_nuevo: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Verifica la temporal y reemplaza hash y flag atomically."""
    identifier = _validar_usuario_id(usuario_id)
    actual = _validar_password_creacion(password_actual)
    nuevo = _validar_password_creacion(password_nuevo)
    usuario = usuario_repository.obtener_por_id(identifier, database_path)
    if (
        usuario is None
        or usuario.get("rol_nombre") != ROL_ALUMNO
        or usuario.get("requiere_cambio_password") != 1
    ):
        raise AuthorizationError("El cambio obligatorio no esta disponible.")
    if not check_password_hash(usuario["password_hash"], actual):
        raise AuthenticationError("La contrasena temporal no es correcta.")
    if check_password_hash(usuario["password_hash"], nuevo):
        raise ValidationError(
            "La nueva contrasena debe ser diferente de la temporal."
        )
    usuario_repository.actualizar_password_y_requerimiento(
        identifier, generate_password_hash(nuevo), 0, database_path
    )
    actualizado = usuario_repository.obtener_por_id(identifier, database_path)
    if actualizado is None:
        raise UsuarioNoEncontradoError("No se encontro el usuario solicitado.")
    return _usuario_seguro(actualizado)


def _authentication_error() -> AuthenticationError:
    return AuthenticationError(_AUTHENTICATION_MESSAGE)


def _obtener_administrador(
    usuario_id: int,
    database_path: Path | None,
) -> dict[str, Any]:
    usuario = usuario_repository.obtener_por_id(usuario_id, database_path)
    if (
        usuario is None
        or usuario.get("rol_nombre") != ROL_ADMINISTRADOR
    ):
        raise UsuarioNoEncontradoError(
            "No se encontro el administrador solicitado."
        )
    return usuario


def _obtener_escaner(
    usuario_id: int,
    database_path: Path | None,
) -> dict[str, Any]:
    usuario = usuario_repository.obtener_por_id(usuario_id, database_path)
    if usuario is None or usuario.get("rol_nombre") != ROL_ESCANER:
        raise UsuarioNoEncontradoError(
            "No se encontro el escaner solicitado."
        )
    return usuario


def _editar_usuario_por_rol(
    usuario_id: object,
    nombre: object,
    correo: object,
    rol_nombre: str,
    obtener_objetivo,
    database_path: Path | None,
) -> dict[str, Any]:
    usuario_id_validado = _validar_usuario_id(usuario_id)
    obtener_objetivo(usuario_id_validado, database_path)
    nombre_normalizado = _normalizar_texto_obligatorio(nombre, "nombre")
    correo_normalizado = _normalizar_correo(correo)
    existente = usuario_repository.obtener_por_correo(
        correo_normalizado, database_path
    )
    if existente is not None and existente["usuario_id"] != usuario_id_validado:
        raise DuplicateUserError("El correo ya esta registrado.")
    if not usuario_repository.actualizar_datos(
        usuario_id_validado,
        nombre_normalizado,
        correo_normalizado,
        database_path,
    ):
        raise UsuarioNoEncontradoError("No se encontro el usuario solicitado.")
    return _usuario_seguro(
        obtener_objetivo(usuario_id_validado, database_path)
    )


def _restablecer_password_por_rol(
    usuario_id: object,
    password: object,
    obtener_objetivo,
    database_path: Path | None,
) -> dict[str, Any]:
    usuario_id_validado = _validar_usuario_id(usuario_id)
    obtener_objetivo(usuario_id_validado, database_path)
    password_validado = _validar_password_creacion(password)
    if not usuario_repository.actualizar_password(
        usuario_id_validado,
        generate_password_hash(password_validado),
        database_path,
    ):
        raise UsuarioNoEncontradoError("No se encontro el usuario solicitado.")
    return _usuario_seguro(
        obtener_objetivo(usuario_id_validado, database_path)
    )



def _vinculo_alumno_valido(
    usuario: dict[str, Any],
    database_path: Path | None,
) -> bool:
    if usuario.get("rol_nombre") != ROL_ALUMNO:
        return True
    vinculo = usuario_alumno_repository.obtener_por_usuario(
        usuario.get("usuario_id"), database_path
    )
    return bool(
        vinculo
        and vinculo.get("usuario_id") == usuario.get("usuario_id")
        and vinculo.get("rol_nombre") == ROL_ALUMNO
        and vinculo.get("usuario_estado") == ESTADO_ACTIVO
        and vinculo.get("alumno_estado") == ESTADO_ACTIVO
        and isinstance(vinculo.get("alumno_id"), int)
        and not isinstance(vinculo.get("alumno_id"), bool)
        and vinculo["alumno_id"] > 0
    )


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
    if not _vinculo_alumno_valido(usuario, database_path):
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
    if not _vinculo_alumno_valido(usuario, database_path):
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


def crear_usuario(
    nombre: object,
    correo: object,
    password: object,
    rol: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Crea una cuenta activa de un rol permitido sin exponer su hash."""
    nombre_normalizado = _normalizar_texto_obligatorio(nombre, "nombre")
    correo_normalizado = _normalizar_correo(correo)
    password_validado = _validar_password_creacion(password)
    rol_normalizado = roles_service.validar_nombre_rol(rol)
    if rol_normalizado == ROL_ALUMNO:
        raise InvalidRoleError(
            "Las cuentas alumno deben crearse mediante vinculacion escolar."
        )

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


def crear_usuario_demo(
    nombre: object,
    correo: object,
    password: object,
    rol: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Conserva la API historica de creacion de usuarios de demostracion."""
    return crear_usuario(nombre, correo, password, rol, database_path)


def listar_administradores(
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Lista exclusivamente cuentas administrativas seguras."""
    return [
        _usuario_seguro(usuario)
        for usuario in usuario_repository.listar_por_rol(
            ROL_ADMINISTRADOR,
            database_path,
        )
    ]


def consultar_administrador(
    usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Consulta un administrador existente por identificador."""
    usuario_id_validado = _validar_usuario_id(usuario_id)
    return _usuario_seguro(
        _obtener_administrador(usuario_id_validado, database_path)
    )


def crear_administrador(
    nombre: object,
    correo: object,
    password: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Crea una cuenta con rol administrador fijado en servidor."""
    return crear_usuario(
        nombre,
        correo,
        password,
        ROL_ADMINISTRADOR,
        database_path,
    )


def editar_administrador(
    usuario_id: object,
    nombre: object,
    correo: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Edita solamente nombre y correo de un administrador."""
    usuario_id_validado = _validar_usuario_id(usuario_id)
    _obtener_administrador(usuario_id_validado, database_path)
    nombre_normalizado = _normalizar_texto_obligatorio(nombre, "nombre")
    correo_normalizado = _normalizar_correo(correo)

    existente = usuario_repository.obtener_por_correo(
        correo_normalizado,
        database_path,
    )
    if (
        existente is not None
        and existente["usuario_id"] != usuario_id_validado
    ):
        raise DuplicateUserError("El correo ya esta registrado.")

    actualizado = usuario_repository.actualizar_datos(
        usuario_id_validado,
        nombre_normalizado,
        correo_normalizado,
        database_path,
    )
    if not actualizado:
        raise UsuarioNoEncontradoError(
            "No se encontro el administrador solicitado."
        )
    return _usuario_seguro(
        _obtener_administrador(usuario_id_validado, database_path)
    )


def restablecer_password_administrador(
    usuario_id: object,
    password: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Reemplaza solamente el hash de contrasena del administrador."""
    usuario_id_validado = _validar_usuario_id(usuario_id)
    _obtener_administrador(usuario_id_validado, database_path)
    password_validado = _validar_password_creacion(password)
    actualizado = usuario_repository.actualizar_password(
        usuario_id_validado,
        generate_password_hash(password_validado),
        database_path,
    )
    if not actualizado:
        raise UsuarioNoEncontradoError(
            "No se encontro el administrador solicitado."
        )
    return _usuario_seguro(
        _obtener_administrador(usuario_id_validado, database_path)
    )


def activar_administrador(
    usuario_id: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Activa un administrador mediante la operacion protegida."""
    objetivo_id = _validar_usuario_id(usuario_id)
    actor_id = _validar_usuario_id(actor_usuario_id)
    return _usuario_seguro(
        usuario_repository.cambiar_estado_administrador_protegido(
            objetivo_id,
            ESTADO_ACTIVO,
            actor_id,
            database_path,
        )
    )


def desactivar_administrador(
    usuario_id: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Desactiva un administrador protegiendo actor y ultimo activo."""
    objetivo_id = _validar_usuario_id(usuario_id)
    actor_id = _validar_usuario_id(actor_usuario_id)
    return _usuario_seguro(
        usuario_repository.cambiar_estado_administrador_protegido(
            objetivo_id,
            ESTADO_INACTIVO,
            actor_id,
            database_path,
        )
    )


def listar_escaneres(
    database_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Lista exclusivamente cuentas de escaneo seguras."""
    return [
        _usuario_seguro(usuario)
        for usuario in usuario_repository.listar_por_rol(
            ROL_ESCANER, database_path
        )
    ]


def consultar_escaner(
    usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Consulta una cuenta de escaneo por identificador."""
    usuario_id_validado = _validar_usuario_id(usuario_id)
    return _usuario_seguro(
        _obtener_escaner(usuario_id_validado, database_path)
    )


def crear_escaner(
    nombre: object,
    correo: object,
    password: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Crea una cuenta con rol escaner fijado en servidor."""
    return crear_usuario(nombre, correo, password, ROL_ESCANER, database_path)


def editar_escaner(
    usuario_id: object,
    nombre: object,
    correo: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Edita solamente nombre y correo de una cuenta de escaneo."""
    return _editar_usuario_por_rol(
        usuario_id,
        nombre,
        correo,
        ROL_ESCANER,
        _obtener_escaner,
        database_path,
    )


def restablecer_password_escaner(
    usuario_id: object,
    password: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Reemplaza solamente el hash de una cuenta de escaneo."""
    return _restablecer_password_por_rol(
        usuario_id, password, _obtener_escaner, database_path
    )


def activar_escaner(
    usuario_id: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Activa un escaner mediante un actor administrador activo."""
    return _usuario_seguro(
        usuario_repository.cambiar_estado_escaner_protegido(
            _validar_usuario_id(usuario_id),
            ESTADO_ACTIVO,
            _validar_usuario_id(actor_usuario_id),
            database_path,
        )
    )


def desactivar_escaner(
    usuario_id: object,
    actor_usuario_id: object,
    database_path: Path | None = None,
) -> dict[str, Any]:
    """Desactiva un escaner sin reglas del ultimo administrador."""
    return _usuario_seguro(
        usuario_repository.cambiar_estado_escaner_protegido(
            _validar_usuario_id(usuario_id),
            ESTADO_INACTIVO,
            _validar_usuario_id(actor_usuario_id),
            database_path,
        )
    )

__all__ = [
    "ROL_ADMINISTRADOR",
    "ROL_ESCANER",
    "activar_administrador",
    "activar_escaner",
    "autenticar_usuario",
    "consultar_administrador",
    "consultar_escaner",
    "crear_administrador",
    "crear_escaner",
    "crear_usuario_demo",
    "desactivar_administrador",
    "desactivar_escaner",
    "editar_administrador",
    "editar_escaner",
    "listar_administradores",
    "listar_escaneres",
    "obtener_usuario_sesion",
    "restablecer_password_administrador",
    "restablecer_password_escaner",
    "validar_rol",
]
