"""Crea usuarios de demostracion sin guardar contrasenas en el proyecto."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path
import sys

from edupass.modules.auth import roles_service, usuarios_service
from edupass.persistence import database_manager
from edupass.shared.constants import ROL_ADMINISTRADOR, ROL_ESCANER
from edupass.shared.errors import EduPassError, InvalidRoleError


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crear un usuario de demostracion para EduPass."
    )
    parser.add_argument(
        "--database",
        type=Path,
        help="Ruta de una base SQLite alternativa.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Solicita datos de forma interactiva y crea una cuenta segura."""
    arguments = _parse_arguments(argv)

    nombre = input("Nombre: ")
    correo = input("Correo: ")
    rol = input("Rol (administrador/escaner): ")
    password = getpass.getpass("Contrasena: ")
    confirmation = getpass.getpass("Confirmar contrasena: ")

    if password != confirmation:
        print(
            "[ERROR] La confirmacion de la contrasena no coincide.",
            file=sys.stderr,
        )
        return 2

    try:
        rol_normalizado = roles_service.validar_nombre_rol(rol)
        if rol_normalizado not in (ROL_ADMINISTRADOR, ROL_ESCANER):
            raise InvalidRoleError(
                "El script demo solo permite administrador o escaner."
            )
        database_path = database_manager.initialize_database(
            arguments.database
        )
        roles_service.asegurar_roles_autenticacion(database_path)
        usuario = usuarios_service.crear_usuario_demo(
            nombre,
            correo,
            password,
            rol_normalizado,
            database_path,
        )
    except (
        EduPassError,
        database_manager.DatabaseManagerError,
        FileNotFoundError,
    ):
        print(
            "[ERROR] No fue posible crear el usuario de demostracion.",
            file=sys.stderr,
        )
        return 1

    print(
        "[OK] Usuario de demostracion creado para el rol "
        f"{usuario['rol_nombre']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
