"""Excepciones compartidas del modulo de alumnos."""


class EduPassError(Exception):
    """Error base controlado de EduPass."""


class ValidationError(EduPassError):
    """Error causado por datos que no cumplen las reglas del sistema."""


class MatriculaDuplicadaError(ValidationError):
    """Error causado por una matricula de alumno ya registrada."""


class AlumnoNoEncontradoError(EduPassError):
    """Error causado por la ausencia del alumno solicitado."""


class RepositoryError(EduPassError):
    """Error controlado de acceso a la persistencia."""


class ConsultaSqlError(RepositoryError):
    """Error al localizar, leer o validar una consulta SQL externa."""
