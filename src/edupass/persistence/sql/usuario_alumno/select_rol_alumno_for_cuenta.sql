SELECT
    roles.rol_id,
    roles.nombre
FROM roles
WHERE roles.nombre = ?;