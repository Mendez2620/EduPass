SELECT
    qr_id,
    alumno_id,
    generado_en,
    expira_en,
    usado_en,
    estado
FROM qr_tokens
WHERE alumno_id = ?
  AND estado = ?
  AND usado_en IS NULL
  AND expira_en > ?
ORDER BY generado_en DESC, qr_id DESC
LIMIT 1;
