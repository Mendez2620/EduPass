"""Excepciones controladas compartidas por los modulos de EduPass."""


class EduPassError(Exception):
    """Error base controlado de EduPass."""


class ValidationError(EduPassError):
    """Error causado por datos que no cumplen las reglas del sistema."""


class MatriculaDuplicadaError(ValidationError):
    """Error causado por una matricula de alumno ya registrada."""


class AlumnoNoEncontradoError(EduPassError):
    """Error causado por la ausencia del alumno solicitado."""


class AlumnoInactivoError(EduPassError):
    """Error causado por un alumno que no puede usar una credencial."""


class QRInvalidoError(EduPassError):
    """Error causado por un token QR invalido o inexistente."""


class QRVencidoError(EduPassError):
    """Error causado por un token QR fuera de vigencia."""


class QRUtilizadoError(EduPassError):
    """Error causado por el segundo uso de un token QR."""


class QRNoDisponibleError(EduPassError):
    """Error causado por la ausencia de un token QR vigente."""


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
