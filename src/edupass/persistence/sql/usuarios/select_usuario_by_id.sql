SELECT
    usuarios.usuario_id,
    usuarios.nombre,
    usuarios.correo,
    usuarios.password_hash,
    usuarios.requiere_cambio_password,
    usuarios.estado,
    usuarios.rol_id,
    roles.nombre AS rol_nombre
FROM usuarios
INNER JOIN roles ON roles.rol_id = usuarios.rol_id
WHERE usuarios.usuario_id = ?;
