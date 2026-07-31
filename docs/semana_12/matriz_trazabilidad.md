# Matriz de trazabilidad

## Etapa A

| Requerimiento | Descripción | Componente | Pruebas | Evidencia | Estado | Observación |
|---|---|---|---|---|---|---|
| RF-05 | Restringir credencial a alumnos activos | Servicios y rutas administrativas | Credencial, repositorio y web | Suites `test_credencial_service` y `test_web_credencial` | Implementado | El backend vuelve a validar el estado. |
| RF-09 | Generar credencial digital | Servicio de credencial y vista administrativa | Credencial, renderer y web | Generación manual aislada | Implementado con limitación | Solo en sesión administrativa. |
| RF-10 | Visualizar credencial digital | Plantilla y SVG en memoria | Renderer y credencial web | SVG, token manual y vista responsiva | Implementado con limitación | No existe cuenta o portal público del alumno. |
| RF-11 | Renovar QR temporal | Servicio, ruta POST y JavaScript | Credencial y web | Renovación manual y automática | Implementado | La renovación manual funciona sin JavaScript. |
| RF-12 | Invalidar QR vencido o utilizado | Repositorio transaccional | Repositorio y validación | Estados y límites temporales | Implementado | Vencido es un estado calculado. |
| RF-13 | Rechazar QR vencido o reutilizado | Servicio de validación | Validación y web | Rechazo manual y automatizado | Implementado | El segundo consumo no tiene éxito. |
| RF-14 | Rechazar QR inválido o alterado | Formato, hash y validación | Validación y web | Token alterado e inexistente | Implementado | Mensaje público controlado. |
| RF-15 | No exponer datos personales en el QR | Token opaco y renderer | Servicios, renderer y web | Inspección de respuesta y SVG | Implementado | El QR contiene solo el token opaco. |

## Etapa B — Implementación técnica

| RF | Descripción | Módulo | Servicio | Repositorio | Ruta | Prueba | Evidencia visual | Commit | Estado |
|---|---|---|---|---|---|---|---|---|---|
| RF-29 | Registrar entrada al plantel | Movimientos | `registrar_movimiento_con_token` | `registrar_con_token` y SQL externo | `POST /scanner/validar` | `test_movimientos_service`, `test_movimiento_repository`, `test_web_movimientos` | Capturada y validada; consulte el inventario de Etapa B. | `e292e59`, `0f15315` | Implementado técnicamente |
| RF-30 | Registrar salida del plantel | Movimientos | `registrar_movimiento_con_token` | `registrar_con_token` y SQL externo | `POST /scanner/validar` | `test_movimientos_service`, `test_movimiento_repository`, `test_web_movimientos` | Capturada y validada; consulte el inventario de Etapa B. | `e292e59`, `0f15315` | Implementado técnicamente |
| RF-33 | Guardar datos obligatorios del movimiento | Movimientos e historial | Servicio de movimientos y servicio de historial | Repositorio de movimientos | Escáner, historial y detalle | Suites de repositorio, servicio e historial web | Capturada y validada; consulte el inventario de Etapa B. | `e292e59`, `0f15315` | Implementado técnicamente |
| RF-34 | Mostrar resultado del escaneo | Web de escáner | Servicio de movimientos | Repositorio de movimientos | `GET/POST /scanner/validar` | `test_web_movimientos`, `test_web_qr_validation` | Capturada y validada; consulte el inventario de Etapa B. | `0f15315` | Implementado técnicamente |
| RF-37 | Rechazar registros consecutivos | Movimientos | Validación de secuencia | Último movimiento y transacción QR-movimiento | `POST /scanner/validar` | Suites de movimientos y web | Capturada y validada; consulte el inventario de Etapa B. | `e292e59`, `0f15315` | Implementado técnicamente |
| RF-38 | Rechazar salida sin entrada | Movimientos | Validación de secuencia | Último movimiento y transacción QR-movimiento | `POST /scanner/validar` | Suites de movimientos y web | Capturada y validada; consulte el inventario de Etapa B. | `e292e59`, `0f15315` | Implementado técnicamente |
| RF-46 | Consultar historial por alumno | Historial | `consultar_historial_alumno` | Listado y conteo por alumno | `GET /admin/historial/<alumno_id>` | `test_historial_service`, `test_web_historial` | Capturada y validada; consulte el inventario de Etapa B. | `0f15315` | Implementado técnicamente |
| RF-48 | Consultar detalle de movimiento | Historial | `consultar_movimiento` | Consulta segura por identificador | `GET /admin/historial/<alumno_id>/movimientos/<movimiento_id>` | `test_historial_service`, `test_web_historial` | Capturada y validada; consulte el inventario de Etapa B. | `0f15315` | Implementado técnicamente |
| RF-49 | Informar historial sin resultados | Historial | `consultar_historial_alumno` | Conteo y listado por alumno | `GET /admin/historial/<alumno_id>` | `test_historial_service`, `test_web_historial` | Capturada y validada; consulte el inventario de Etapa B. | `0f15315` | Implementado técnicamente |

## RNF verificables

| RNF | Evidencia |
|---|---|
| Seguridad | CSRF, roles, QR opaco, SHA-256, no-cache, no-referrer e IDOR prevenido. |
| Modularidad | Rutas, servicios, repositorios y SQL externo separados. |
| Atomicidad | Consumo QR e inserción del movimiento en una transacción con rollback total. |
| Concurrencia | Reserva de escritura y consumo condicional probados con operaciones simultáneas. |
| Pruebas | 484 pruebas `unittest` en estado OK. |
| Navegador | Flujos administrativos y de escáner cubiertos por pruebas web y evidencia visual capturada y validada. |
| Responsive | CSS, pruebas estructurales y capturas validadas en viewport 390 × 812. |
| Privacidad | Sin QR en URL, logs o respuestas; historial limitado a datos seguros. |
| Documentación | Etapa A cerrada y documentación técnica de Etapa B preparada. |
| Control de versiones | Núcleo e integración web en commits separados; commit documental y push pendientes. |

Permanecen fuera del alcance implementado el CRUD web completo, el rol y portal
del alumno, la cámara, los intentos rechazados, tutores, notificaciones, áreas
funcionales, dispositivos funcionales, reportes y exportación.
