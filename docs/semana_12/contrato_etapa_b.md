# Contrato técnico de Semana 12, Etapa B

## Propósito y alcance

La Etapa B completa el flujo técnico que transforma una credencial QR temporal
en un movimiento auditable de entrada o salida y permite su consulta
administrativa. El alcance incluye el núcleo transaccional, la integración web
del escáner, el historial por alumno, el detalle y las pruebas de regresión.

Los requerimientos funcionales relacionados son RF-29, RF-30, RF-33, RF-34,
RF-37, RF-38, RF-46, RF-48 y RF-49. Se relacionan además los RNF de seguridad,
modularidad, mensajes controlados, pruebas, control de roles, privacidad,
responsive y documentación.

Quedan excluidos el CRUD web de alumnos y usuarios, el rol y portal del alumno,
la cámara, la persistencia de intentos rechazados, tutores, notificaciones,
áreas internas funcionales, dispositivos fijos funcionales, reportes,
exportación, aplicación móvil y despliegue público.

## Arquitectura

La solución conserva una arquitectura por capas:

1. Las plantillas y rutas Flask reciben la operación autorizada.
2. Los servicios normalizan datos y aplican reglas de negocio.
3. Los repositorios concentran el acceso a SQLite.
4. Las consultas SQL se mantienen en archivos externos.
5. Los errores compartidos se traducen a mensajes públicos controlados.

La ruta del escáner obtiene el identificador del usuario autenticado desde el
servidor. El navegador no proporciona alumno, responsable, fecha, punto, área,
dispositivo ni identificadores internos.

## Movimientos y secuencia histórica

Los únicos tipos admitidos son `entrada` y `salida`. La secuencia se determina
con el movimiento más reciente del alumno:

- el primer movimiento válido debe ser una entrada;
- una entrada no puede seguir inmediatamente a otra entrada;
- una salida requiere una entrada previa;
- una salida no puede seguir inmediatamente a otra salida;
- después de una salida puede registrarse una nueva entrada.

Una secuencia rechazada no consume el QR ni crea un movimiento.

## Tiempo, punto y responsable

El backend genera una fecha y hora consciente de zona, la normaliza a UTC y la
persiste con formato estable. El punto permitido en esta etapa es
`acceso_principal`. El movimiento conserva al usuario escáner autenticado como
responsable. Área y dispositivo permanecen nulos porque todavía no son
funcionales.

## Contrato transaccional

El registro de un movimiento y el consumo del QR forman una única transacción:

1. Se abre una conexión local.
2. `BEGIN IMMEDIATE` reserva la escritura.
3. Se consulta y clasifica el QR temporal.
4. Se confirma que el alumno esté activo.
5. Se confirma que el responsable sea un escáner activo.
6. Se valida la secuencia histórica.
7. El consumo condicional actualiza exactamente una fila activa y vigente.
8. Se inserta el movimiento.
9. Se recupera el resultado seguro.
10. Un único `commit` confirma ambas operaciones.

Cualquier error controlado o de persistencia ejecuta rollback total. Por ello
no puede quedar un QR consumido sin movimiento, ni un movimiento confirmado sin
el consumo correspondiente.

`BEGIN IMMEDIATE`, el consumo condicional y la comprobación de filas afectadas
serializan las escrituras relevantes en SQLite. Las pruebas concurrentes
confirman que un mismo QR solo produce un resultado exitoso.

## Historial administrativo

El administrador puede seleccionar un alumno y consultar sus movimientos en
orden de fecha descendente y, como desempate, identificador descendente. La
paginación está fijada por el backend en 50 registros por página. Un alumno
existente sin movimientos devuelve una lista vacía y el mensaje:

> No hay movimientos registrados para este alumno.

El detalle muestra identificador administrativo, alumno, matrícula, tipo,
fecha y hora UTC, punto y responsable. La consulta recibe simultáneamente el
alumno y el movimiento; si no coinciden responde como recurso inexistente para
prevenir IDOR. Las vistas son de solo lectura.

## Seguridad y privacidad

- Administrador y escáner tienen rutas separadas mediante control de rol.
- Los formularios POST conservan protección CSRF.
- El QR viaja únicamente en el cuerpo del formulario del escáner.
- El QR se limpia del formulario después del POST y no aparece en URL, flash,
  JavaScript, logs ni respuestas.
- El historial no devuelve correo, credenciales, fotografía ni datos QR.
- Las respuestas administrativas y del escáner usan encabezados sin caché.
- Los errores internos, SQL y rutas locales no se muestran al usuario.
- La pertenencia alumno-movimiento se comprueba en el servicio.

## Mensajes públicos y códigos HTTP

| Escenario | Mensaje público | HTTP |
|---|---|---:|
| Entrada válida | Entrada registrada correctamente. | 200 |
| Salida válida | Salida registrada correctamente. | 200 |
| QR inválido | Token inválido. | 200 |
| QR vencido | Token vencido. | 200 |
| QR utilizado | Token ya utilizado. | 200 |
| Alumno inactivo | Alumno inactivo. | 200 |
| Doble entrada | No se puede registrar otra entrada sin una salida previa. | 200 |
| Salida sin entrada | No se puede registrar una salida sin una entrada previa. | 200 |
| Doble salida | No se puede registrar otra salida sin una nueva entrada. | 200 |
| Formulario inválido | Selecciona un tipo de movimiento e ingresa un token QR válido de 43 caracteres. | 400 |
| Rol incorrecto | Acceso no autorizado. | 403 |
| Recurso administrativo inexistente | Mensaje controlado de recurso no encontrado. | 404 |
| Fallo técnico | No fue posible registrar el movimiento. | 500 |

## Criterios de aceptación

- Entrada y salida válidas se persisten una sola vez.
- QR y movimiento se confirman o revierten juntos.
- Los rechazos de secuencia conservan el QR activo.
- El responsable y la hora proceden del backend.
- El historial está ordenado, paginado y limitado a datos seguros.
- El detalle previene acceso cruzado entre alumnos.
- Visitantes y roles incorrectos reciben la respuesta prevista.
- El formulario funciona sin JavaScript; el script solo evita doble envío.
- La interfaz mantiene controles etiquetados y tablas responsive.
- Las 484 pruebas terminan con cero errores y cero fallos.

## Evidencia visual

Los criterios anteriores se demostraron con datos ficticios y una base SQLite
temporal. Las catorce capturas están registradas en el
[inventario visual de Etapa B](evidencias_visuales_etapa_b/inventario_evidencias.md).
El commit documental y el push continúan pendientes.

## Limitaciones y decisiones aplazadas

La captura continúa siendo manual y la cámara está pendiente. No se persisten
intentos rechazados. SQLite y HTTP local son adecuados para la demostración
académica, no para producción multiusuario. Permanecen aplazados el CRUD web,
el rol alumno, la vinculación usuario-alumno, el historial personal, HTTPS
productivo, rate limiting distribuido, multiinstitución, tutores,
notificaciones, reportes y exportación.
