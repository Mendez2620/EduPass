# Implementación de movimientos e historial

## Resumen

La Etapa B se implementó en dos incrementos técnicos. El primero agregó el
nucleo transaccional de movimientos; el segundo integró el flujo con Flask y
añadió el historial administrativo. No se cambiaron dependencias.

## Persistencia y tiempo

`schema.sql` incorpora el índice
`idx_movimientos_alumno_fecha` sobre alumno, fecha descendente e identificador
descendente. El índice respalda la consulta del último movimiento y el orden
del historial.

`time_utils.py` centraliza la obtención, normalización, serialización e
interpretación de instantes UTC. Admite un reloj inyectable para pruebas
deterministas.

`_qr_consumption.py` clasifica internamente el estado de una credencial sin
exponer sus datos opacos. Distingue credencial inexistente, vencida, utilizada,
invalidada y alumno inactivo.

Las consultas de movimientos son SQL externo. Cubren:

- selección del QR para registrar un movimiento;
- validación del usuario escáner;
- lectura del último movimiento;
- consumo condicional del QR;
- inserción del movimiento;
- recuperación por identificador;
- listado paginado por alumno;
- conteo por alumno.

## Repositorio y servicios

`movimiento_repository.py` ejecuta `BEGIN IMMEDIATE`, valida QR, responsable y
secuencia, consume condicionalmente la credencial, inserta el movimiento y
confirma todo con un único commit. Ante errores de dominio o SQLite realiza
rollback y cierra cursores y conexión. También ofrece consultas de solo lectura
para último movimiento, detalle, conteo y listado paginado.

`movimientos_service.py` valida token, tipo, usuario y punto; obtiene la hora
UTC del backend; delega la operación atómica al repositorio; limita el
resultado a campos seguros y genera el mensaje público de entrada o salida.

`historial_service.py` valida identificadores, página y tamaño; confirma la
existencia del alumno; calcula totales y páginas; limita el tamaño máximo a 50;
devuelve movimientos seguros; y comprueba la pertenencia del movimiento al
alumno antes de mostrar el detalle.

## Integración web

El formulario del escáner contiene únicamente:

- selector obligatorio de entrada o salida;
- token manual obligatorio de 43 caracteres;
- protección CSRF;
- botón **Registrar movimiento**.

`scanner_routes.py` exige rol escáner, obtiene el responsable desde el usuario
autenticado y llama al servicio transaccional. Presenta mensajes controlados y
códigos coherentes sin devolver el token ni identificadores internos.

`admin_routes.py` añade:

- `/admin/historial`;
- `/admin/historial/<alumno_id>`;
- `/admin/historial/<alumno_id>/movimientos/<movimiento_id>`.

Las tres rutas exigen administrador, usan encabezados sin caché y traducen
validaciones, recursos inexistentes y fallos de repositorio a respuestas
controladas.

Las plantillas `historial.html` y `movimiento_detalle.html` son de solo lectura.
La navegación y los paneles enlazan el historial, y el listado de alumnos
conserva la generación de credencial existente.

`app.css` añade estilos de formulario, estados, detalle, paginación y
contenedores de tabla con desplazamiento horizontal. La presentación se
mantiene utilizable a 390 píxeles.

`scanner_validation.js` actúa solo sobre el formulario de movimientos. Tras el
primer envío válido deshabilita el botón y muestra **Procesando...**. No lee,
almacena ni transmite el token, y el formulario sigue funcionando sin
JavaScript.

## Flujo implementado

```text
Escáner inicia sesión
→ selecciona entrada o salida
→ captura token
→ backend obtiene usuario
→ valida QR y alumno
→ valida secuencia
→ consume QR
→ inserta movimiento
→ commit único
→ muestra resultado
→ administrador consulta historial
```

## Atomicidad, rollback y concurrencia

El consumo y la inserción no son operaciones separadas. Si la secuencia es
inválida o falla la inserción, el QR permanece activo. Si dos operaciones
compiten por el mismo QR, la reserva de escritura y el consumo condicional
permiten un solo éxito. Las pruebas verifican rollback completo, filas
afectadas y ausencia de movimientos parciales.

## Pruebas y validación

El núcleo agregó 64 pruebas en `test_movimiento_repository.py` y
`test_movimientos_service.py`. La integración agregó o ajustó 103 pruebas para
servicio de historial, movimientos web, historial web, regresión QR y paneles
por rol.

La suite completa ejecuta 484 pruebas. Cubre entradas, salidas, secuencias,
atomicidad, concurrencia, paginación, detalle, roles, CSRF, IDOR, responsive y
privacidad. La validación manual aislada del incremento técnico confirmó
entrada, rechazo de doble entrada con QR activo, salida, orden del historial,
detalle y controles 403 mediante una base temporal fuera del repositorio.

La demostración visual definitiva confirmó además el historial vacío, la
secuencia Entrada–Salida–Entrada, el detalle administrativo, las restricciones
cruzadas de rol y las vistas responsive en 390 × 812. Las catorce capturas y
sus resultados están descritos en el
[inventario visual de Etapa B](evidencias_visuales_etapa_b/inventario_evidencias.md).
El commit documental y el push continúan pendientes.

## Alcance pendiente

La cámara sigue pendiente y la captura continúa siendo manual. Los intentos
rechazados no se persisten. También permanecen pendientes el CRUD web, el rol
alumno, la vinculación usuario-alumno, el panel e historial personal, y las
funciones posteriores de producción.
