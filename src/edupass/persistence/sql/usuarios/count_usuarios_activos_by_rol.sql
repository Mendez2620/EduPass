SELECT COUNT(*) AS total_activos
FROM usuarios
INNER JOIN roles ON roles.rol_id = usuarios.rol_id
WHERE roles.nombre = ?
  AND usuarios.estado = ?;
