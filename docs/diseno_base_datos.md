# Diseno minimo de base de datos

Base de datos sugerida: SQLite.

Tablas principales:

- `alumnos`
- `tutores`
- `alumno_tutor`
- `roles`
- `usuarios`
- `areas_internas`
- `usuario_area_permiso`
- `dispositivos_fijos`
- `qr_tokens`
- `movimientos`
- `notificaciones_push`
- `intentos_rechazados`

Nota: la tabla `notificaciones_push` usara el campo `estado` para indicar si la notificacion esta `enviada`, `pendiente` o `fallida`.

