INSERT INTO qr_tokens (
    alumno_id,
    token_hash,
    generado_en,
    expira_en,
    usado_en,
    estado
)
VALUES (?, ?, ?, ?, NULL, ?);
