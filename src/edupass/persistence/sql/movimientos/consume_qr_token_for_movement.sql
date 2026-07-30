UPDATE qr_tokens
SET
    usado_en = ?,
    estado = ?
WHERE token_hash = ?
  AND estado = ?
  AND usado_en IS NULL
  AND expira_en > ?;
