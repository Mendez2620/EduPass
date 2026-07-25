"""Reglas de negocio y validaciones del modulo de alumnos."""

from __future__ import annotations

from typing import Any

from edupass.persistence.repositories import alumno_repository
from edupass.shared.constants import (
    ESTADO_ALUMNO_ACTIVO,
    ESTADO_ALUMNO_INACTIVO,
    ESTADOS_ALUMNO_VALIDOS,
)
from edupass.shared.errors import (
    AlumnoNoEncontradoError,
    MatriculaDuplicadaError,
    RepositoryError,
    ValidationError,
)


def _validar_alumno_id(alumno_id: object) -> int:
    if (
        isinstance(alumno_id, bool)
        or not isinstance(alumno_id, int)
        or alumno_id <= 0
    ):
        raise ValidationError(
            "El identificador del alumno debe ser un entero mayor que cero."
        )
    return alumno_id


def _normalizar_texto_obligatorio(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ValidationError(f"El campo {campo} es obligatorio.")
    return valor.strip()


def _normalizar_matricula(matricula: object) -> str:
    return _normalizar_texto_obligatorio(matricula, "matrícula").upper()


def _normalizar_fotografia(fotografia: object) -> str | None:
    if fotografia is None:
        return None
    if not isinstance(fotografia, str):
        raise ValidationError(
            "El campo fotografía debe ser una ruta de texto o None."
        )
    return fotografia.strip() or None


def _normalizar_estado(estado: object) -> str:
    if not isinstance(estado, str):
        raise ValidationError(
            "El estado del alumno debe ser activo o inactivo."
        )

    estado_normalizado = estado.strip().lower()
    if estado_normalizado not in ESTADOS_ALUMNO_VALIDOS:
        raise ValidationError(
            "El estado del alumno debe ser activo o inactivo."
        )
    return estado_normalizado


def _obtener_alumno_existente(
    alumno_id: int,
    database_path: Any = None,
) -> dict[str, Any]:
    alumno = alumno_repository.obtener_alumno_por_id(
        alumno_id,
        database_path,
    )
    if alumno is None:
        raise AlumnoNoEncontradoError("No se encontró el alumno.")
    return alumno


def _cambiar_estado_alumno(
    alumno_id: object,
    estado: str,
    database_path: Any = None,
) -> dict[str, Any]:
    alumno_id_validado = _validar_alumno_id(alumno_id)
    _obtener_alumno_existente(alumno_id_validado, database_path)

    actualizado = alumno_repository.actualizar_estado_alumno(
        alumno_id_validado,
        estado,
        database_path,
    )
    if not actualizado:
        raise AlumnoNoEncontradoError("No se encontró el alumno.")

    return _obtener_alumno_existente(alumno_id_validado, database_path)


def registrar_alumno(
    nombre: object,
    matricula: object,
    grado: object,
    grupo: object,
    fotografia: object = None,
    estado: object = ESTADO_ALUMNO_ACTIVO,
    database_path: Any = None,
) -> dict[str, Any]:
    """Valida, normaliza y registra un alumno."""
    nombre_normalizado = _normalizar_texto_obligatorio(nombre, "nombre")
    matricula_normalizada = _normalizar_matricula(matricula)
    grado_normalizado = _normalizar_texto_obligatorio(grado, "grado")
    grupo_normalizado = _normalizar_texto_obligatorio(grupo, "grupo")
    fotografia_normalizada = _normalizar_fotografia(fotografia)
    estado_normalizado = _normalizar_estado(estado)

    if alumno_repository.existe_matricula(
        matricula_normalizada,
        database_path,
    ):
        raise MatriculaDuplicadaError("La matrícula ya está registrada.")

    alumno_id = alumno_repository.crear_alumno(
        nombre_normalizado,
        matricula_normalizada,
        grado_normalizado,
        grupo_normalizado,
        fotografia_normalizada,
        estado_normalizado,
        database_path,
    )
    alumno = alumno_repository.obtener_alumno_por_id(
        alumno_id,
        database_path,
    )
    if alumno is None:
        raise RepositoryError(
            "No se pudo recuperar el alumno después de registrarlo."
        )
    return alumno


def consultar_alumno_por_id(
    alumno_id: object,
    database_path: Any = None,
) -> dict[str, Any]:
    """Consulta un alumno existente mediante su identificador."""
    alumno_id_validado = _validar_alumno_id(alumno_id)
    return _obtener_alumno_existente(alumno_id_validado, database_path)


def consultar_alumno_por_matricula(
    matricula: object,
    database_path: Any = None,
) -> dict[str, Any]:
    """Consulta un alumno mediante su matrícula normalizada."""
    matricula_normalizada = _normalizar_matricula(matricula)
    alumno = alumno_repository.obtener_alumno_por_matricula(
        matricula_normalizada,
        database_path,
    )
    if alumno is None:
        raise AlumnoNoEncontradoError("No se encontró el alumno.")
    return alumno


def listar_alumnos(
    database_path: Any = None,
) -> list[dict[str, Any]]:
    """Devuelve todos los alumnos registrados."""
    return alumno_repository.listar_todos(database_path)


def editar_alumno(
    alumno_id: object,
    nombre: object,
    matricula: object,
    grado: object,
    grupo: object,
    fotografia: object = None,
    database_path: Any = None,
) -> dict[str, Any]:
    """Reemplaza los campos editables de un alumno existente."""
    alumno_id_validado = _validar_alumno_id(alumno_id)
    _obtener_alumno_existente(alumno_id_validado, database_path)

    nombre_normalizado = _normalizar_texto_obligatorio(nombre, "nombre")
    matricula_normalizada = _normalizar_matricula(matricula)
    grado_normalizado = _normalizar_texto_obligatorio(grado, "grado")
    grupo_normalizado = _normalizar_texto_obligatorio(grupo, "grupo")
    fotografia_normalizada = _normalizar_fotografia(fotografia)

    alumno_con_matricula = alumno_repository.obtener_alumno_por_matricula(
        matricula_normalizada,
        database_path,
    )
    if (
        alumno_con_matricula is not None
        and alumno_con_matricula["alumno_id"] != alumno_id_validado
    ):
        raise MatriculaDuplicadaError("La matrícula ya está registrada.")

    actualizado = alumno_repository.actualizar_alumno(
        alumno_id_validado,
        nombre_normalizado,
        matricula_normalizada,
        grado_normalizado,
        grupo_normalizado,
        fotografia_normalizada,
        database_path,
    )
    if not actualizado:
        raise AlumnoNoEncontradoError("No se encontró el alumno.")

    return _obtener_alumno_existente(alumno_id_validado, database_path)


def activar_alumno(
    alumno_id: object,
    database_path: Any = None,
) -> dict[str, Any]:
    """Activa un alumno y devuelve su información actualizada."""
    return _cambiar_estado_alumno(
        alumno_id,
        ESTADO_ALUMNO_ACTIVO,
        database_path,
    )


def desactivar_alumno(
    alumno_id: object,
    database_path: Any = None,
) -> dict[str, Any]:
    """Desactiva un alumno y devuelve su información actualizada."""
    return _cambiar_estado_alumno(
        alumno_id,
        ESTADO_ALUMNO_INACTIVO,
        database_path,
    )
