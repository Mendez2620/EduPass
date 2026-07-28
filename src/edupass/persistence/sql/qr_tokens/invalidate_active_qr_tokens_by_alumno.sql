UPDATE qr_tokens
SET estado = ?
WHERE alumno_id = ?
  AND estado = ?;
