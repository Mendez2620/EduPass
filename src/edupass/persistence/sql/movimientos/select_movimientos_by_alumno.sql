SELECT
    movimientos.movimiento_id,
    movimientos.alumno_id,
    alumnos.nombre AS alumno_nombre,
    alumnos.matricula,
    movimientos.tipo_movimiento,
    movimientos.fecha_hora,
    movimientos.punto_plantel,
    movimientos.usuario_id,
    usuarios.nombre AS usuario_nombre
FROM movimientos
INNER JOIN alumnos
    ON alumnos.alumno_id = movimientos.alumno_id
LEFT JOIN usuarios
    ON usuarios.usuario_id = movimientos.usuario_id
WHERE movimientos.alumno_id = ?
ORDER BY movimientos.fecha_hora DESC, movimientos.movimiento_id DESC
LIMIT ? OFFSET ?;
