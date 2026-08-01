SELECT
    alumnos.alumno_id,
    alumnos.nombre,
    alumnos.matricula,
    alumnos.grado,
    alumnos.grupo,
    alumnos.estado
FROM alumnos
WHERE alumnos.alumno_id = ?;