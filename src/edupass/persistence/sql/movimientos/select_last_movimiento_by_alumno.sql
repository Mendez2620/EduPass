SELECT
    movimiento_id,
    tipo_movimiento,
    fecha_hora
FROM movimientos
WHERE alumno_id = ?
ORDER BY fecha_hora DESC, movimiento_id DESC
LIMIT 1;
