SELECT
    qr_tokens.qr_id,
    qr_tokens.alumno_id,
    qr_tokens.token_hash,
    qr_tokens.generado_en,
    qr_tokens.expira_en,
    qr_tokens.usado_en,
    qr_tokens.estado,
    alumnos.estado AS alumno_estado
FROM qr_tokens
INNER JOIN alumnos
    ON alumnos.alumno_id = qr_tokens.alumno_id
WHERE qr_tokens.token_hash = ?;
