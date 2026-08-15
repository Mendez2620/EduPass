# Reporte del incremento técnico de Semana 13

## 1. Objetivo

Completar el incremento administrativo y personal de EduPass sin alterar el núcleo transaccional estable de Semana 12. El trabajo incorporó CRUD web, cámara, modos HTTPS, el rol alumno, cuentas vinculadas, portal personal y una auditoría integral antes del cierre documental.

## 2. Estado previo

El punto de partida publicado fue `f1197b29608f3dc900a4ea3f0e4d72addb29ee00`. En ese corte existían persistencia SQLite, autenticación de administrador y escáner, credencial QR temporal administrativa, captura manual, movimientos transaccionales e historial administrativo. La suite publicada contenía 484 pruebas.

Todavía no estaban implementados el CRUD web completo, la cámara, los modos HTTPS configurables, el rol alumno, el vínculo uno a uno, la administración de cuentas alumno ni el portal personal. Los intentos rechazados no se persistían.

## 3. Alcance ejecutado

Semana 13 se dividió en siete incrementos funcionales y una auditoría:

1. CRUD web seguro de alumnos.
2. CRUD web de administradores.
3. CRUD web de escáneres.
4. Cámara QR local y modos HTTPS.
5. Rol alumno y vínculo uno a uno.
6. Administración de cuentas alumno.
7. Portal personal del alumno.
8. Congelamiento y auditoría integral con clasificación A. APROBADO.

No se implementaron notificaciones, tutores completos, áreas o dispositivos funcionales, intentos rechazados persistentes, aplicación móvil ni despliegue productivo.

## 4. Commits técnicos

| Orden | SHA | Mensaje | Alcance |
|---:|---|---|---|
| 1 | `a65685f7c4dc2f97ca216fe73a8644bf2063ae2a` | `feat: agregar CRUD web seguro de alumnos` | Alta, edición, activación y desactivación web de alumnos. |
| 2 | `9f597fdf054d7573a6e651b74b666cbef448a74f` | `feat: agregar CRUD web seguro de administradores` | Gestión de administradores y protecciones de estado. |
| 3 | `24969e3e27f442f152ab5c6389609b51e146de79` | `feat: agregar CRUD web seguro de escaneres` | Gestión separada de cuentas escáner. |
| 4 | `957dcb6fbc8285d8d8e9d0882c83b95bf781b964` | `feat: integrar camara QR y modos HTTPS` | ZXing local, cámara y configuración off/proxy/direct. |
| 5 | `b113c37dc14cfcb48ac8b8e732d7f95f7e8b1163` | `feat: agregar rol y vinculacion segura de alumnos` | Rol alumno y relación uno a uno. |
| 6 | `2ec44848b7fd38c98e4fb35958dd52b0403d64de` | `feat: agregar administracion de cuentas de alumnos` | Creación y mantenimiento administrativo de cuentas vinculadas. |
| 7 | `87eef8552768cd06b1090e89e84e229a7dd0e8ce` | `feat: agregar portal personal seguro del alumno` | Login, perfil, QR e historial propios. |

## 5. CRUD web de alumnos

El administrador puede registrar, editar, activar y desactivar alumnos desde Flask. La matrícula se normaliza y conserva la restricción única. Los cambios de estado son operaciones `POST`, mientras que un `GET` sobre activar o desactivar devuelve 405. No existe borrado físico.

La edición preserva el estado y la fotografía cuando no se sustituye. La desactivación conserva credenciales QR, movimientos e historial. Las respuestas traducen validaciones, duplicados y errores de repositorio a códigos 400, 404, 409 o 500 controlados.

## 6. Administración de usuarios

### Administradores

El CRUD fija el rol en el servidor, separa el restablecimiento de contraseña y permite alta, edición, activación y desactivación. Impide el auto-bloqueo accidental y protege al último administrador activo. No ofrece eliminación física ni selector editable de rol.

### Escáneres

El CRUD usa contratos separados, fija el rol `escaner`, separa contraseña y estado, y no aplica indebidamente la regla del último administrador. Tampoco incluye borrado o cambio de rol desde el navegador.

## 7. Cámara y HTTPS

La cámara utiliza `@zxing/browser` 0.2.1 servido desde el repositorio, con licencia MIT y sin CDN.

- SHA-256 del tarball: `21f5c8b9cc9ca4e6897e9374c072a32d39a88d51f8561a040a5054ade81be215`.
- SHA-256 del JavaScript: `066bc34edfcdd4a33f0964aeec967752a0dea1ccaf36e58e319ac9fcb5070f6a`.

La cámara se inicia sólo por interacción, solicita video sin audio, prefiere la cámara trasera y detiene los tracks al detectar, cancelar, enviar u ocultar la página. La detección llena el campo, pero no envía el formulario; la captura manual permanece disponible.

Los modos soportados son:

- `off`: HTTP histórico, sin `ProxyFix` y cookies no marcadas `Secure`;
- `proxy`: HTTP local detrás de un HTTPS externo, `ProxyFix` con `x_proto=1` y `x_host=1`, host local y cookies `Secure`;
- `direct`: certificado y clave externos obligatorios, sin fallback silencioso y con `ssl_context` explícito.

Se validaron automáticamente los tres modos y se realizó validación local del modo proxy. Continúan pendientes la prueba física con teléfono, un túnel real y HTTPS directo con certificados externos.

## 8. Rol alumno y vínculo uno a uno

La tabla `usuario_alumno` relaciona un `usuario_id` con un `alumno_id`. Ambas columnas tienen restricciones `UNIQUE` y llaves foráneas, impidiendo múltiples cuentas por alumno y múltiples alumnos por cuenta.

La creación de usuario y vínculo utiliza `BEGIN IMMEDIATE`, una transacción corta y rollback total. Las pruebas de concurrencia verifican que no se produzcan vínculos duplicados. Las operaciones de estado conservan usuario, alumno, vínculo, QR y movimientos; no existe API de desvinculación o eliminación.

## 9. Cuentas alumno

El panel administrativo permite:

- crear atómicamente una cuenta para un alumno activo sin vínculo;
- normalizar y editar únicamente el correo;
- restablecer la contraseña mediante un formulario separado;
- activar o desactivar la cuenta;
- conservar alumno, vínculo, rol y datos históricos.

No permite cambiar el alumno asociado, modificar el rol, desvincular ni borrar. Un alumno inactivo impide crear o reactivar la cuenta. Los resultados seguros excluyen `password_hash`, fotografía y datos QR.

## 10. Portal alumno

Una cuenta activa, vinculada y con alumno activo puede iniciar sesión y acceder a:

- perfil escolar de sólo lectura;
- generación de credencial propia;
- renovación e invalidación del QR anterior;
- historial propio paginado;
- detalle de movimientos propios.

La identidad sigue `current_user.usuario_id → usuario_alumno → alumno_id`. No existe ruta ni formulario personal que permita seleccionar `alumno_id`. Un movimiento ajeno y uno inexistente producen el mismo 404 genérico. La sesión deja de ser válida al desactivar cuenta o alumno, eliminar el vínculo o cambiar el rol.

## 11. Arquitectura

```text
PySide6 / Flask
      |
      v
Servicios de alumnos, auth, credencial_qr, movimientos,
historial, cuentas alumno y portal alumno
      |
      v
Repositorios
      |
      v
SQL externo parametrizado
      |
      v
DatabaseManager -> SQLite
```

Las rutas no contienen SQL. Los servicios no abren conexiones directamente. Los repositorios cargan consultas externas, administran cursores y transacciones y devuelven estructuras controladas. No existe una conexión SQLite global.

## 12. Rutas principales

| Método | Prefijo o ruta | Rol | Finalidad | Mutabilidad |
|---|---|---|---|---|
| GET/POST | `/login` | Público controlado | Autenticación y redirección por rol. | Inicia sesión. |
| POST | `/logout` | Autenticado | Cierre con CSRF. | Modifica sesión. |
| GET/POST | `/admin/alumnos` y subrutas | Administrador | CRUD y estados de alumnos. | Mixta; mutaciones por POST. |
| GET/POST | `/admin/administradores` y subrutas | Administrador | CRUD de administradores. | Mixta; mutaciones por POST. |
| GET/POST | `/admin/escaneres` y subrutas | Administrador | CRUD de escáneres. | Mixta; mutaciones por POST. |
| GET/POST | `/admin/cuentas-alumnos` y subrutas | Administrador | Gestión de cuentas vinculadas. | Mixta; mutaciones por POST. |
| POST | `/admin/credencial` y `/admin/credencial/renovar` | Administrador | Generar o renovar la credencial administrativa. | Mutación por POST. |
| GET | `/admin/historial` y subrutas | Administrador | Historial y detalle administrativo. | Sólo lectura. |
| GET/POST | `/scanner/validar` | Escáner | Cámara, captura manual y movimiento. | Registra por POST. |
| GET | `/alumno` | Alumno | Panel y perfil propio. | Sólo lectura. |
| GET/POST | `/alumno/credencial` y subrutas | Alumno | QR propio y renovación. | Generar/renovar por POST. |
| GET | `/alumno/historial` y detalle | Alumno | Historial y movimientos propios. | Sólo lectura. |

## 13. Seguridad

- Autenticación con mensajes genéricos y hash Werkzeug.
- Autorización nominal mediante `role_required`.
- Formularios Flask-WTF y CSRF.
- Logout por `POST`.
- Sesiones recargadas desde la base.
- Respuestas seguras sin contraseñas ni hashes.
- QR opaco, SHA-256 persistido, 30 segundos y un solo uso.
- Consumo QR y movimiento dentro de una transacción.
- SQL externo parametrizado.
- `ProxyFix` limitado a proxy y cookies `Secure` en proxy/direct.
- Certificados externos en direct.
- CSP en la credencial del alumno.
- `no-store` y `no-referrer` en respuestas sensibles.
- Prevención de IDOR y errores públicos genéricos.
- Token fuera de URL, sesión, flash, logs y texto visible en el portal alumno.

Estas medidas corresponden al prototipo auditado y no constituyen una certificación de seguridad externa.

## 14. Pruebas

| Corte | Total | Resultado |
|---|---:|---|
| Suite inicial de Semana 13 | 484 | OK |
| Etapa 1 | 522 | OK |
| Etapa 2 | 594 | OK |
| Etapa 3 | 661 | OK |
| Etapa 4 | 741 | OK |
| Etapa 5 | 792 | OK |
| Etapa 6 | 849 | OK |
| Etapa 7 | 892 | OK |

La auditoría integral ejecutó 892 pruebas en 226.983 segundos, con cero fallos y cero errores. Las diez suites focalizadas ejecutaron 355 pruebas en 133.516 segundos y también terminaron en `OK`.

Las pruebas emplean bases temporales; no usan `data/edupass.sqlite` como base de prueba. No se ejecutó una herramienta de cobertura y no se declara porcentaje. Las 22 advertencias observadas son mensajes esperados de pruebas que simulan errores de repositorio; no representan fallos.

## 15. Validaciones manuales

Se reportaron validaciones manuales con datos ficticios y SQLite temporal para:

- CRUD de alumnos y usuarios;
- autenticación y separación de roles;
- credencial QR, renovación e invalidación;
- entrada, rechazo de secuencia, salida e historial;
- portal alumno e aislamiento frente a datos ajenos;
- modo proxy en configuración local;
- eliminación de bases y helpers temporales.

No se declara realizada la validación física mediante un túnel de VS Code, teléfono real o permiso real de cámara. Tampoco se declara validado HTTPS directo con certificados externos.

## 16. Auditoría integral

La auditoría obtuvo la clasificación **A. APROBADO**. Verificó:

- esquema idempotente y persistencia conservada;
- llaves foráneas y restricciones únicas;
- separación de roles y autenticación;
- prevención de IDOR;
- QR, movimientos, transacciones y concurrencia;
- cámara, HTTPS y privacidad;
- CRUD de alumnos y usuarios;
- cuentas y portal alumno;
- CSRF, errores controlados y responsive a 390 px;
- ausencia de residuos técnicos relevantes;
- diff y staging vacíos durante el congelamiento.

No se identificaron bloqueadores funcionales.

## 17. Intentos rechazados

**Mejora futura diferida para evitar alterar el cierre transaccional estable de Semana 13.**

La tabla `intentos_rechazados` existe en el esquema como preparación estructural. No existe repositorio, servicio ni vista funcional. Los rechazos actuales no crean filas en ella y no se persisten tokens originales ni hashes de intentos rechazados.

## 18. Limitaciones

- Prototipo académico ejecutado con el servidor de desarrollo de Flask.
- SQLite no se plantea para alta concurrencia productiva.
- Cámara y proxy están cubiertos automáticamente, pero la evidencia física con teléfono está pendiente.
- HTTPS directo requiere certificados externos y confianza del dispositivo.
- Sin intentos rechazados persistentes ni notificaciones push.
- Sin flujo completo de tutores, áreas o dispositivos.
- Sin aplicación móvil, modo offline, reportes exportables o multiinstitución.
- Sin despliegue productivo ni porcentaje de cobertura declarado.

## 19. Trabajo futuro

- Persistencia controlada de intentos rechazados sin debilitar la atomicidad.
- Notificaciones y flujo funcional de tutores.
- Áreas internas, permisos y dispositivos.
- Estrategia formal de migraciones.
- Servidor de producción y despliegue controlado.
- Pruebas físicas en más dispositivos y navegadores.
- Empaquetado y distribución de recursos.

## 20. Resultado

### Consolidación final

Después del corte histórico de 892 pruebas se integraron detección automática de entrada/salida, alta atómica de alumno y acceso, contraseña temporal con `secrets`, cambio obligatorio, notificaciones internas y mejoras responsive/UX. El corte final contiene **964 pruebas en OK**.

El flujo automático de cierre fue: administrador → alumno con cambio obligatorio → QR → escáner con entrada y salida → rechazo por reutilización → notificaciones e historial del alumno → historial administrativo. Se usaron datos ficticios, SQLite temporal fuera del repositorio y tres viewports: 390 × 844, 768 × 1024 y 1366 × 768. La cámara se verificó en cuanto a interfaz y estados; no se declara una cámara física.

El inventario está en [`evidencias_visuales/inventario_evidencias.md`](evidencias_visuales/inventario_evidencias.md). Clasificación final: **A. APROBADO**; sin bloqueadores para el cierre académico.

Semana 13 cerró siete commits técnicos locales, 892 pruebas en `OK` y una auditoría integral A. APROBADO. Al redactar este reporte todavía no se ha realizado push de los commits locales; la documentación está en preparación y no se incluye un commit documental aún inexistente. La evidencia física con teléfono continúa pendiente y la carpeta de presentación queda expresamente excluida de este incremento.
