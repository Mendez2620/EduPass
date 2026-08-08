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


class UsuarioNoEncontradoError(EduPassError):
    """Error causado por la ausencia del usuario solicitado."""


class UsuarioAlumnoYaVinculadoError(ValidationError):
    """Error causado por un usuario que ya tiene un alumno vinculado."""


class AlumnoYaTieneUsuarioError(ValidationError):
    """Error causado por un alumno que ya tiene una cuenta vinculada."""


class UsuarioNoEsAlumnoError(ValidationError):
    """Error causado por intentar vincular una cuenta de otro rol."""


class VinculoUsuarioAlumnoNoEncontradoError(EduPassError):
    """Error causado por la ausencia de una vinculacion solicitada."""


class AutoBloqueoAdministradorError(EduPassError):
    """Error causado por el intento de auto-desactivar un administrador."""


class UltimoAdministradorActivoError(EduPassError):
    """Error causado por intentar desactivar al ultimo administrador."""

class MovimientoError(EduPassError):
    """Error controlado del registro de movimientos."""


class TipoMovimientoInvalidoError(MovimientoError):
    """Error causado por un tipo de movimiento no permitido."""


class SecuenciaMovimientoError(MovimientoError):
    """Error causado por una secuencia de entrada o salida invalida."""


class EstadoMovimientoCambiadoError(MovimientoError):
    """Error causado cuando el tipo cambió antes de la confirmación."""

    def __init__(self, tipo_movimiento_actual: str):
        super().__init__(
            "El estado del alumno cambió. Confirma el movimiento actualizado."
        )
        self.tipo_movimiento_actual = tipo_movimiento_actual


class UsuarioEscanerInvalidoError(MovimientoError):
    """Error causado por un responsable inexistente o no autorizado."""


class MovimientoNoEncontradoError(MovimientoError):
    """Error causado por la ausencia del movimiento solicitado."""
