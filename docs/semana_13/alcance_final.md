# Alcance final de Semana 13

## Implementado

- CRUD seguro de alumnos, administradores y escáneres.
- Alta y edición integradas de alumno y cuenta.
- Portal personal, vínculo uno a uno y protección IDOR.
- Contraseña temporal segura, muestra única y cambio obligatorio.
- QR opaco temporal, matrícula enmascarada y uso único.
- Entrada/salida automática y transaccional.
- Historial, notificaciones internas, cámara local y UX responsive.

## Futuro

- Intentos rechazados persistentes y push externo.
- Tutores, áreas y dispositivos completos.
- App móvil nativa, offline, multiinstitución y despliegue productivo.
- Certificación externa y validación física amplia.

Suite final: **964 pruebas en OK**. Clasificación: **A. APROBADO**.

## Matriz final de trazabilidad

| ID | Requisito | Prioridad | Estado final | Módulo | Prueba | Decisión |
|---|---|---|---|---|---|---|
| S13-01 | CRUD web de alumnos | Alta | Implementado | alumnos/admin | `test_web_alumnos_crud` | Conservar |
| S13-02 | Administradores y escáneres | Alta | Implementado | auth/admin | `test_web_administradores`, `test_web_escaneres` | Conservar |
| S13-03 | Alta integrada alumno + acceso | Alta | Implementado | cuentas alumno | `test_alta_integrada_alumno_service` | Conservar |
| S13-04 | Contraseña temporal y cambio obligatorio | Crítica | Implementado | auth/cuentas alumno | `test_password_temporal`, `test_web_auth` | Conservar |
| S13-05 | Portal e IDOR | Crítica | Implementado | portal alumno | `test_web_alumno_portal` | Conservar |
| S13-06 | QR temporal y uso único | Crítica | Implementado | credencial QR | `test_credencial_service`, `test_qr_token_repository` | Conservar |
| S13-07 | Entrada/salida automática | Crítica | Implementado | movimientos | `test_movimientos_automaticos` | Conservar |
| S13-08 | Cámara y captura manual | Media | Implementado | web scanner | `test_web_camera_qr` | Conservar; física pendiente |
| S13-09 | Historial y notificaciones | Alta | Implementado | historial/notificaciones | `test_web_historial`, `test_notificaciones_alumno` | Conservar |
| S13-10 | Responsive y UX | Media | Implementado | web UI | `test_web_ui_responsive`, `test_web_ux_final` | Conservar |
| S13-F01 | Intentos rechazados persistentes | Baja | Futuro | no funcional | Sin prueba funcional | Diferir |
| S13-F02 | Push, tutores, áreas y dispositivos | Baja | Futuro | dominios estructurales | Sin flujo final | Diferir |
| S13-F03 | Producción, móvil, offline y multiinstitución | Baja | Futuro | operación | Fuera de suite | Diferir |
