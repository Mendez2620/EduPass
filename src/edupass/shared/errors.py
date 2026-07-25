"""Excepciones controladas compartidas por los modulos de EduPass."""


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


class AuthenticationError(EduPassError):
    """Error publico y generico al autenticar credenciales."""


class AuthorizationError(EduPassError):
    """Error causado por un rol sin autorizacion para una operacion."""


class DuplicateUserError(ValidationError):
    """Error causado por un correo de usuario ya registrado."""


class InvalidRoleError(ValidationError):
    """Error causado por un rol fuera del alcance de autenticacion."""
