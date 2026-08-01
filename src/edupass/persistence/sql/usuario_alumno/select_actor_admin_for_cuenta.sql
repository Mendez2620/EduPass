SELECT
    usuarios.usuario_id,
    usuarios.estado,
    roles.nombre AS rol_nombre
FROM usuarios
INNER JOIN roles ON roles.rol_id = usuarios.rol_id
WHERE usuarios.usuario_id = ?
  AND usuarios.estado = ?
  AND roles.nombre = ?;