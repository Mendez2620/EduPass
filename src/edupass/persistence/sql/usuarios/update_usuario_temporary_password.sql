UPDATE usuarios
SET password_hash = ?,
    requiere_cambio_password = ?
WHERE usuario_id = ?;
