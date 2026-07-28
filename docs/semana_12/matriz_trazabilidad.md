# Matriz de trazabilidad

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

## RNF verificables

| RNF | Evidencia |
|---|---|
| Seguridad | CSRF, roles, token opaco, SHA-256, no-cache y no-referrer. |
| Modularidad | Ruta web, servicio, repositorio y SQL externo separados. |
| Pruebas | 317 pruebas `unittest` en estado OK. |
| Navegador | Flujos administrativos y de escáner validados. |
| Responsive | Revisión a 390, 768 y 1366 píxeles. |
| Privacidad | Sin datos personales dentro del QR ni token en URL o logs. |
| Documentación | Seis documentos técnicos de Etapa A. |
| Control de versiones | Núcleo, web, corrección y documentación en commits separados. |

No forman parte de esta matriz como funciones implementadas los movimientos,
historial, cámara, notificaciones, tutores, áreas o dispositivos.
