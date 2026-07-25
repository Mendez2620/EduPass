# Cierre documental de Semana 11

## Objetivo

Consolidar el alcance aprobado de EduPass 1.0, registrar el incremento de
autenticación y web, actualizar la trazabilidad y dejar un plan controlado para
Semana 12 sin iniciar su implementación.

## Estado del corte

Al comenzar este cierre, `master` estaba sincronizada con `origin/master` en
`3520ddd797685773e3148932eb6b4bb1a70f2a3c`, sin cambios técnicos ni staging.
La suite de referencia ejecutó 172 pruebas correctamente.

Al finalizar la Semana 11 están disponibles la persistencia SQLite, el módulo
de alumnos, la autenticación modular para `administrador` y `escaner`, la
fábrica Flask, las sesiones protegidas, los paneles por rol y el listado web de
alumnos de solo lectura. La interfaz PySide6 se conserva como prototipo previo.

## Documentos

- [Alcance de EduPass 1.0](alcance_edupass_1_0.md)
- [Matriz de trazabilidad](matriz_trazabilidad.md)
- [Reporte del incremento](reporte_incremento.md)
- [Evidencias y pruebas](evidencias_y_pruebas.md)
- [Bitácora resumida de Codex](bitacora_codex_resumen.md)
- [Plan preliminar de Semana 12](plan_semana_12.md)

## Commits técnicos de Semana 11

- `2e1c520e7cd51e57937d16b1321410c9ca8584ac` -
  `feat: implementar autenticacion modular`
- `3520ddd797685773e3148932eb6b4bb1a70f2a3c` -
  `feat: agregar base web y listado administrativo`

## Alcance atendido

El incremento cubre autenticación por correo y contraseña, contraseñas
hasheadas, bloqueo de usuarios inactivos, recuperación de sesión, autorización
por rol, CSRF, cierre de sesión por `POST`, errores 403 y 404, paneles por rol y
consulta web administrativa de alumnos.

## Pendientes para Semana 12

La credencial controlada, el QR temporal de 30 segundos y un solo uso, su
validación, la captura manual del token, los movimientos de entrada y salida y
el historial básico siguen pendientes. La cámara es opcional y no sustituye la
captura manual.

## Limitaciones

EduPass se ejecuta localmente o en una red privada de demostración mediante
HTTP. SQLite es apropiado para el prototipo académico, no para producción
multiusuario. No existe aplicación móvil nativa, publicación en Internet,
carga web de fotografías ni evidencia final en todos los navegadores.
