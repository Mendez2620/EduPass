SELECT
    usuarios.usuario_id,
    usuarios.nombre,
    usuarios.correo,
    usuarios.estado,
    usuarios.rol_id,
    roles.nombre AS rol_nombre
FROM usuarios
INNER JOIN roles ON roles.rol_id = usuarios.rol_id
WHERE roles.nombre = ?
ORDER BY usuarios.nombre ASC, usuarios.usuario_id ASC;
