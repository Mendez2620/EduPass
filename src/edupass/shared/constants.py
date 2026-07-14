"""Constantes compartidas para el estado de los alumnos."""

ESTADO_ALUMNO_ACTIVO = "activo"
ESTADO_ALUMNO_INACTIVO = "inactivo"
ESTADOS_ALUMNO_VALIDOS = frozenset(
    {
        ESTADO_ALUMNO_ACTIVO,
        ESTADO_ALUMNO_INACTIVO,
    }
)
