"""Adaptadores de sesion y autorizacion para la interfaz web."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import abort, current_app
from flask_login import UserMixin, current_user, login_required

from edupass.modules.auth import usuarios_service
from edupass.shared.errors import EduPassError


ViewFunction = TypeVar("ViewFunction", bound=Callable[..., Any])


class SessionUser(UserMixin):
    """Representacion minima y segura de un usuario autenticado."""

    def __init__(
        self,
        usuario_id: int,
        nombre: str,
        correo: str,
        estado: str,
        rol_id: int,
        rol_nombre: str,
        requiere_cambio_password: int = 0,
    ) -> None:
        self.usuario_id = usuario_id
        self.nombre = nombre
        self.correo = correo
        self.estado = estado
        self.rol_id = rol_id
        self.rol_nombre = rol_nombre
        self.requiere_cambio_password = requiere_cambio_password

    @classmethod
    def from_service_data(cls, data: dict[str, Any]) -> "SessionUser":
        """Construye un usuario desde la respuesta segura del servicio."""
        return cls(
            usuario_id=data["usuario_id"],
            nombre=data["nombre"],
            correo=data["correo"],
            estado=data["estado"],
            rol_id=data["rol_id"],
            rol_nombre=data["rol_nombre"],
            requiere_cambio_password=data.get("requiere_cambio_password", 0),
        )

    def get_id(self) -> str:
        return str(self.usuario_id)

    def as_service_data(self) -> dict[str, Any]:
        """Devuelve el contrato seguro requerido por validar_rol."""
        return {
            "usuario_id": self.usuario_id,
            "nombre": self.nombre,
            "correo": self.correo,
            "estado": self.estado,
            "rol_id": self.rol_id,
            "rol_nombre": self.rol_nombre,
            "requiere_cambio_password": self.requiere_cambio_password,
        }


def load_user(user_id: str) -> SessionUser | None:
    """Recarga un usuario activo desde el servicio de autenticacion."""
    try:
        numeric_id = int(user_id)
        data = usuarios_service.obtener_usuario_sesion(
            numeric_id,
            current_app.config["DATABASE_PATH"],
        )
        return SessionUser.from_service_data(data) if data else None
    except (EduPassError, KeyError, TypeError, ValueError):
        return None


def role_required(required_role: str) -> Callable[[ViewFunction], ViewFunction]:
    """Exige autenticacion y el rol nominal indicado."""

    def decorator(view: ViewFunction) -> ViewFunction:
        @login_required
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                usuarios_service.validar_rol(
                    current_user.as_service_data(),
                    required_role,
                )
            except EduPassError:
                abort(403)
            return view(*args, **kwargs)

        return wrapped  # type: ignore[return-value]

    return decorator
