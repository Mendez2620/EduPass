SELECT
    usuarios.usuario_id,
    usuarios.correo
FROM usuarios
WHERE usuarios.correo = ?;