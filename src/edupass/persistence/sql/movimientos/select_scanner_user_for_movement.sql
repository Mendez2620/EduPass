SELECT
    usuarios.usuario_id,
    usuarios.nombre AS usuario_nombre,
    usuarios.estado AS usuario_estado,
    usuarios.rol_id,
    roles.nombre AS rol_nombre
FROM usuarios
INNER JOIN roles
    ON roles.rol_id = usuarios.rol_id
WHERE usuarios.usuario_id = ?;
