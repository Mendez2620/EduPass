SELECT
    usuario_alumno.usuario_alumno_id,
    usuario_alumno.usuario_id,
    usuario_alumno.alumno_id,
    usuarios.nombre AS usuario_nombre,
    usuarios.correo,
    usuarios.estado AS usuario_estado,
    usuarios.requiere_cambio_password,
    roles.nombre AS rol_nombre,
    alumnos.nombre AS alumno_nombre,
    alumnos.matricula,
    alumnos.grado,
    alumnos.grupo,
    alumnos.estado AS alumno_estado
FROM usuario_alumno
INNER JOIN usuarios ON usuarios.usuario_id = usuario_alumno.usuario_id
INNER JOIN roles ON roles.rol_id = usuarios.rol_id
INNER JOIN alumnos ON alumnos.alumno_id = usuario_alumno.alumno_id
WHERE usuario_alumno.usuario_alumno_id = ?;
