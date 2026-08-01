SELECT
    alumnos.alumno_id,
    alumnos.nombre,
    alumnos.matricula,
    alumnos.grado,
    alumnos.grupo,
    alumnos.estado
FROM alumnos
LEFT JOIN usuario_alumno
    ON usuario_alumno.alumno_id = alumnos.alumno_id
WHERE usuario_alumno.usuario_alumno_id IS NULL
  AND ? = 1
ORDER BY alumnos.nombre, alumnos.alumno_id;