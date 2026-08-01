SELECT
    usuario_alumno.usuario_alumno_id,
    usuarios.usuario_id,
    alumnos.alumno_id,
    alumnos.nombre AS alumno_nombre,
    alumnos.matricula,
    alumnos.grado,
    alumnos.grupo,
    alumnos.estado AS alumno_estado,
    usuarios.correo,
    usuarios.estado AS usuario_estado,
    roles.nombre AS rol_nombre
FROM usuario_alumno
INNER JOIN usuarios ON usuarios.usuario_id = usuario_alumno.usuario_id
INNER JOIN roles ON roles.rol_id = usuarios.rol_id
INNER JOIN alumnos ON alumnos.alumno_id = usuario_alumno.alumno_id
WHERE roles.nombre = ?
ORDER BY alumnos.nombre, alumnos.alumno_id;