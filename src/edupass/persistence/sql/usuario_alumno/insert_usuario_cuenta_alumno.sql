INSERT INTO usuarios (
    nombre,
    correo,
    password_hash,
    requiere_cambio_password,
    estado,
    rol_id
)
VALUES (?, ?, ?, ?, ?, ?);
