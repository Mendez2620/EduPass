SELECT
    alumno_id,
    nombre,
    matricula,
    grado,
    grupo,
    fotografia,
    estado
FROM alumnos
WHERE alumno_id = ?;
