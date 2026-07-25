# Matriz de trazabilidad al cierre de Semana 11

## Criterios de lectura

- **Implementado** exige lógica funcional y evidencia automatizada o manual.
- **Implementado parcialmente** indica que solo una parte verificable está
  disponible.
- **Placeholder** identifica preparación estructural sin comportamiento final.
- La existencia de una tabla en `schema.sql` no acredita por sí sola un RF.
- `S9`, `S11` y `S12` indican la semana de implementación o la propuesta.

## Requerimientos funcionales RF-01 a RF-50

| ID | Nombre resumido | Prioridad original | Estado al cierre de S11 | Nivel final | Semana | Módulo | Evidencia actual | Prueba existente o propuesta | Decisión | Justificación |
|---|---|---|---|---:|---|---|---|---|---|---|
| RF-01 | Registro de alumnos | Alta | Implementado | 1 | S9 | Alumnos | Servicio, repositorio, SQL y PySide6; web solo lista | Pruebas de servicio/repositorio y prueba manual PySide6 | Conservar | Es base para credencial y movimientos; el alta web no existe. |
| RF-02 | Matrícula única | Alta | Implementado | 1 | S9 | Alumnos | Normalización, consulta previa y `UNIQUE` | Duplicado y variantes de espacios/mayúsculas | Conservar | Evita identidades escolares inconsistentes. |
| RF-03 | Edición de alumnos | Media | Implementado parcialmente | 2 | S9 | Alumnos | Servicio, repositorio y PySide6; sin edición web | Pruebas de edición y prueba manual PySide6 | Deseable | Existe en el prototipo, pero no en la interfaz web final. |
| RF-04 | Activar/desactivar alumnos | Alta | Implementado parcialmente | 1 | S9 | Alumnos | Lógica y PySide6; sin operación web | Pruebas de estado e idempotencia | Integrar | El estado existe; falta su operación en web y conexión con credencial. |
| RF-05 | Bloquear credencial de inactivos | Alta | Pendiente | 1 | S12-A | Credencial/QR | Estado de alumno disponible; credencial ausente | Alumno inactivo no obtiene token | Implementar | Regla indispensable antes de emitir credenciales. |
| RF-06 | Registro de tutores | Media | Fuera de EduPass 1.0 | 3 | Posterior | Tutores | Tabla y archivo base sin flujo funcional | Prueba futura de alta válida | Excluir | Amplía actores y datos sin bloquear el flujo principal. |
| RF-07 | Asociación alumno-tutor | Media | Fuera de EduPass 1.0 | 3 | Posterior | Tutores | Tabla relacional sin servicio funcional | Prueba futura de asociación única | Excluir | Depende del módulo de tutores excluido. |
| RF-08 | Tutores inactivos sin avisos | Media | Fuera de EduPass 1.0 | 3 | Posterior | Tutores/Notificaciones | Estructura inicial, sin avisos reales | Prueba futura con tutor inactivo | Excluir | Tutores y push están fuera de la versión. |
| RF-09 | Generar credencial digital | Alta | Pendiente | 1 | S12-A | Credencial/QR | Archivo base sin implementación | Alumno activo obtiene credencial | Implementar | Es la entrada al flujo QR. |
| RF-10 | Visualizar credencial | Alta | Pendiente | 1 | S12-A | Credencial/QR/Web | Sin ruta ni pantalla de credencial | Ver datos permitidos y QR vigente | Implementar | Debe existir una vista controlada sin cuenta completa. |
| RF-11 | Renovar QR cada 30 s | Alta | Pendiente | 1 | S12-A | Credencial/QR | Sin generador ni temporizador | Reloj controlado y renovación a 30 s | Implementar | Regla central aprobada del MVP. |
| RF-12 | Invalidar QR vencido/usado | Alta | Pendiente | 1 | S12-A | Validación QR | Tabla `qr_tokens`, sin lógica | Token vencido o usado no valida | Implementar | Necesario para temporalidad y uso único. |
| RF-13 | Rechazar QR vencido/reutilizado | Alta | Pendiente | 1 | S12-A | Validación QR | Archivo base sin implementación | Rechazos por vencimiento y reutilización | Implementar | Protege la integridad del registro. |
| RF-14 | Rechazar QR inválido/alterado | Alta | Pendiente | 1 | S12-A | Validación QR | Archivo base sin implementación | Token inexistente o alterado se rechaza | Implementar | Evita aceptar credenciales ajenas o manipuladas. |
| RF-15 | Proteger datos dentro del QR | Media | Implementado parcialmente | 1 | S12-A | Credencial/Seguridad | Decisión aprobada: usar token opaco; aún no hay QR | Inspeccionar contenido y comprobar ausencia de PII | Completar | El diseño está definido, pero falta evidencia funcional. |
| RF-16 | Inicio de sesión por rol | Alta | Implementado | 1 | S11 | Autenticación/Web | Servicio, Flask-Login, rutas y paneles por rol | Pruebas de login y autorización web | Conservar | Administrador y escáner acceden a funciones separadas. |
| RF-17 | Crear usuarios con roles | Alta | Implementado parcialmente | 2 | S11 | Usuarios/Roles | Servicio, repositorios y script interactivo; sin panel CRUD | Pruebas de creación y roles permitidos | Mantener acotado | Permite preparar demos sin ampliar la web administrativa. |
| RF-18 | Desactivar usuarios | Alta | Pendiente | 2 | Posterior | Usuarios/Roles | El esquema admite estado; no hay operación administrativa final | Prueba futura de cambio de estado | Diferir | No bloquea la demostración si los usuarios se preparan previamente. |
| RF-19 | Restringir usuarios inactivos | Alta | Implementado | 1 | S11 | Autenticación/Web | Autenticación y recarga de sesión excluyen cuentas inactivas | Login y sesión de usuario inactivo | Conservar | Evita acceso posterior con una cuenta no vigente. |
| RF-20 | Registrar dispositivos fijos | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Dispositivos | Tabla y archivo base | Prueba futura de alta única | Excluir | El escaneo se asocia al usuario autenticado, no a inventario de equipos. |
| RF-21 | Asociar dispositivo a punto/área | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Dispositivos | Relación estructural, sin flujo | Prueba futura de asociación | Excluir | Depende de dispositivos y áreas excluidos. |
| RF-22 | Activar/desactivar dispositivos | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Dispositivos | Campo de estado, sin lógica | Prueba futura de bloqueo | Excluir | No es necesario para captura manual autenticada. |
| RF-23 | Rechazar dispositivo no autorizado | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Dispositivos/Validación | Motivo previsto en esquema, sin validación | Prueba futura de rechazo | Excluir | EduPass 1.0 autoriza usuarios, no dispositivos fijos. |
| RF-24 | Crear áreas internas | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Áreas | Tabla y archivo base | Prueba futura de alta | Excluir | La versión solo registra entrada y salida del plantel. |
| RF-25 | Editar/desactivar áreas | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Áreas | Campo de estado, sin lógica | Prueba futura de edición/estado | Excluir | Depende del módulo de áreas. |
| RF-26 | Método de escaneo por área | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Áreas | Sin configuración funcional | Prueba futura por modalidad | Excluir | Introduce reglas que no aplican al acceso principal. |
| RF-27 | Notificaciones por área | Media | Fuera de EduPass 1.0 | 3 | Posterior | Áreas/Notificaciones | Sin configuración funcional | Prueba futura de configuración | Excluir | Áreas y notificaciones están fuera. |
| RF-28 | Bloquear movimientos en área inactiva | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Áreas/Movimientos | Sin lógica funcional | Prueba futura con área inactiva | Excluir | No hay movimientos internos en EduPass 1.0. |
| RF-29 | Registrar entrada al plantel | Alta | Pendiente | 1 | S12-B | Movimientos | Tabla `movimientos`, sin caso de uso | Entrada válida persiste una vez | Implementar | Es parte del flujo principal. |
| RF-30 | Registrar salida del plantel | Alta | Pendiente | 1 | S12-B | Movimientos | Tabla `movimientos`, sin caso de uso | Salida válida con entrada previa | Implementar | Completa la trazabilidad del plantel. |
| RF-31 | Entrada a área interna | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Movimientos/Áreas | Esquema general, sin lógica | Prueba futura de entrada de área | Excluir | Movimientos internos quedan fuera. |
| RF-32 | Salida de área interna | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Movimientos/Áreas | Esquema general, sin lógica | Prueba futura de salida de área | Excluir | Movimientos internos quedan fuera. |
| RF-33 | Datos obligatorios del movimiento | Alta | Implementado parcialmente | 1 | S12-B | Movimientos/Persistencia | Columnas estructurales en `movimientos`; sin registro funcional | Integración que consulta todos los campos | Completar | El esquema prepara la evidencia, pero no guarda movimientos aún. |
| RF-34 | Resultado del escaneo | Alta | Pendiente | 1 | S12-B | Validación/Web | Dashboard de escáner informa que el flujo está pendiente | Casos exitoso y rechazos con mensaje claro | Implementar | El operador necesita una respuesta inequívoca. |
| RF-35 | Permiso de usuario por área | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Permisos | Tabla de permisos, sin flujo | Prueba futura de autorización de área | Excluir | Solo hay acceso al plantel y dos roles globales. |
| RF-36 | Punto asignado al dispositivo | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Dispositivos | Estructura sin validación | Prueba futura de punto distinto | Excluir | Depende de dispositivos fijos excluidos. |
| RF-37 | Rechazar doble registro | Alta | Pendiente | 1 | S12-B | Movimientos | Sin reglas de secuencia | Doble entrada/salida consecutiva se rechaza | Implementar | Evita movimientos duplicados. |
| RF-38 | Rechazar salida sin entrada | Alta | Pendiente | 1 | S12-B | Movimientos | Sin reglas de secuencia | Salida sin entrada activa se rechaza | Implementar | Evita historial contradictorio. |
| RF-39 | Notificar entrada | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Notificaciones | Tabla y archivo base, sin push | Prueba futura de envío | Excluir | Requiere tutores e infraestructura push. |
| RF-40 | Notificar salida | Alta | Fuera de EduPass 1.0 | 3 | Posterior | Notificaciones | Tabla y archivo base, sin push | Prueba futura de envío | Excluir | Requiere tutores e infraestructura push. |
| RF-41 | Notificar áreas internas | Media | Fuera de EduPass 1.0 | 3 | Posterior | Notificaciones/Áreas | Sin flujo funcional | Prueba futura de área configurada | Excluir | Depende de dos módulos excluidos. |
| RF-42 | Restringir avisos por área | Media | Fuera de EduPass 1.0 | 3 | Posterior | Notificaciones/Áreas | Sin flujo funcional | Prueba futura con avisos deshabilitados | Excluir | No hay áreas ni avisos en la versión. |
| RF-43 | Contenido de notificación | Media | Fuera de EduPass 1.0 | 3 | Posterior | Notificaciones | Sin plantilla ni envío | Prueba futura de contenido | Excluir | No se implementan notificaciones reales. |
| RF-44 | Estado de notificación | Media | Fuera de EduPass 1.0 | 3 | Posterior | Notificaciones/Persistencia | Columna `estado` en esquema; sin servicio | Prueba estructural existente; funcional futura | Excluir | Hay soporte estructural, no una función entregada. |
| RF-45 | Conservar movimiento si falla aviso | Media | Fuera de EduPass 1.0 | 3 | Posterior | Movimientos/Notificaciones | Sin coordinación funcional | Prueba futura de fallo de envío | Excluir | La dependencia push está fuera del alcance. |
| RF-46 | Historial por alumno | Alta | Pendiente | 1 | S12-B | Historial/Web | Archivo base sin consulta funcional | Consultar movimientos de alumno | Implementar | Cierra el flujo con consulta posterior. |
| RF-47 | Filtros de historial | Media | Pendiente | 2 | Posterior/S12 si hay capacidad | Historial/Web | Sin filtros | Pruebas futuras de fecha y tipo | Deseable | Aporta búsqueda, pero no bloquea el historial básico. |
| RF-48 | Detalle de movimiento | Alta | Pendiente | 1 | S12-B | Historial/Web | Esquema con campos; sin vista | Abrir evento y ver evidencia completa | Implementar | Permite auditar el registro. |
| RF-49 | Mensaje sin resultados | Media | Pendiente | 1 | S12-B | Historial/Web | Sin pantalla de historial | Consulta vacía muestra mensaje distinto de error | Implementar | Evita ambigüedad en la consulta. |
| RF-50 | Intentos rechazados | Alta | Placeholder | 2 | Posterior/S12 si hay capacidad | Auditoría/Persistencia | Tabla `intentos_rechazados` y prueba estructural; sin registro funcional | Prueba futura por cada motivo aprobado | Deseable | El soporte existe, pero falta el caso de uso auditable. |

### Conteo por nivel

| Nivel | Cantidad |
|---|---:|
| Nivel 1 - obligatorio | 22 |
| Nivel 2 - deseable | 5 |
| Nivel 3 - mejora futura | 23 |
| **Total** | **50** |

## Trazabilidad detallada de Nivel 1

| RF | Historia de usuario | Criterio de aceptación principal | Estado | Módulo | Prueba | Semana | Evidencia esperada |
|---|---|---|---|---|---|---|---|
| RF-01 | HU-01 - Registrar alumnos | Con datos obligatorios válidos, el alumno se crea correctamente. | Implementado | Alumnos | Alta válida y validación de obligatorios | S9 | Registro persistente en PySide6 y pruebas de servicio/repositorio. |
| RF-02 | HU-02 - Evitar matrícula duplicada | Una matrícula nueva se guarda y una existente se rechaza tras normalizar. | Implementado | Alumnos | Duplicado, espacios y mayúsculas | S9 | Restricción `UNIQUE` y pruebas automatizadas. |
| RF-04 | HU-04 - Activar/desactivar alumnos | Un alumno desactivado pierde acceso a credencial; al activarlo lo recupera. | Implementado parcialmente | Alumnos | Estado e idempotencia; integración futura con credencial | S9/S12 | Estado persistente y rechazo posterior de credencial. |
| RF-05 | HU-04 - Controlar uso de credencial | Un alumno inactivo no puede generar un QR válido. | Pendiente | Credencial/QR | Solicitud con alumno inactivo | S12-A | Respuesta de credencial no disponible, sin token creado. |
| RF-09 | HU-08 - Obtener credencial digital | Un alumno activo dispone de su credencial controlada. | Pendiente | Credencial/Web | Apertura válida e inactiva | S12-A | Ruta y vista controlada probadas. |
| RF-10 | HU-09 - Ver datos y QR | La credencial muestra datos permitidos y QR vigente. | Pendiente | Credencial/Web | Render de credencial | S12-A | Pantalla sin datos indebidos y token vigente. |
| RF-11 | HU-10 - Renovar QR | Con la credencial abierta, el QR cambia al cumplirse 30 segundos. | Pendiente | Credencial/QR | Reloj controlado en varios ciclos | S12-A | Tokens distintos y vencimiento verificable. |
| RF-12 | HU-10 - Invalidar QR anterior | Al renovarse o usarse, el token anterior deja de ser válido. | Pendiente | Validación QR | Vencido y usado | S12-A | Estado y fecha de uso persistidos. |
| RF-13 | HU-11 - Rechazar vencido/reutilizado | Un QR vencido o ya usado se rechaza con motivo específico. | Pendiente | Validación QR | Dos rechazos deterministas | S12-A | Respuesta sin movimiento creado. |
| RF-14 | HU-12 - Rechazar inválido/alterado | Un token ajeno, incompleto o alterado no continúa la validación. | Pendiente | Validación QR | Token inexistente o alterado | S12-A | Rechazo claro, sin persistir movimiento. |
| RF-15 | HU-13 - No exponer datos personales | El contenido del QR no revela datos personales directamente. | Implementado parcialmente | Credencial/Seguridad | Inspección del token generado | S12-A | Token opaco sin nombre, matrícula, grado, grupo o fotografía. |
| RF-16 | HU-14 - Iniciar sesión | Credenciales válidas llevan al panel correspondiente al rol. | Implementado | Autenticación/Web | Login administrador, escáner y rol incorrecto | S11 | Pruebas web, sesiones y paneles protegidos. |
| RF-19 | HU-16 - Bloquear usuario inactivo | Una cuenta inactiva no inicia sesión ni conserva acceso válido. | Implementado | Autenticación/Web | Login y recarga de sesión inactiva | S11 | Pruebas de servicio y web. |
| RF-29 | HU-24 - Registrar entrada | QR válido y no usado de alumno activo registra una entrada. | Pendiente | Movimientos | Integración de entrada válida | S12-B | Fila de movimiento y resultado de éxito. |
| RF-30 | HU-25 - Registrar salida | QR válido y no usado con entrada previa registra una salida. | Pendiente | Movimientos | Integración de salida válida | S12-B | Fila de salida asociada al alumno. |
| RF-33 | HU-28 - Evidencia completa | El detalle muestra alumno, fecha, hora, tipo, punto y responsable. | Implementado parcialmente | Movimientos/Historial | Guardado y lectura de todos los campos | S12-B | Registro completo; hoy solo existe soporte de esquema. |
| RF-34 | HU-29 - Resultado claro | Cada validación informa éxito o motivo de rechazo. | Pendiente | Validación/Web | Tabla de respuestas por resultado | S12-B | Mensaje visible y estado HTTP coherente. |
| RF-37 | HU-32 - Evitar duplicados consecutivos | Una segunda entrada o salida consecutiva se rechaza. | Pendiente | Movimientos | Secuencias entrada-entrada y salida-salida | S12-B | Solo el primer movimiento válido persiste. |
| RF-38 | HU-33 - Exigir entrada previa | Una salida sin entrada activa se rechaza. | Pendiente | Movimientos | Salida inicial y secuencia válida | S12-B | Rechazo sin fila de salida inválida. |
| RF-46 | HU-41 - Consultar historial | Seleccionar un alumno muestra sus movimientos. | Pendiente | Historial/Web | Con eventos y sin eventos | S12-B | Lista ordenada correspondiente al alumno. |
| RF-48 | HU-43 - Ver detalle | Abrir un evento muestra la información completa del movimiento. | Pendiente | Historial/Web | Detalle por identificador válido | S12-B | Pantalla con actor, momento, tipo, punto y responsable. |
| RF-49 | HU-44 - Informar sin resultados | Una búsqueda sin coincidencias muestra “sin resultados”, no un error. | Pendiente | Historial/Web | Alumno sin movimientos | S12-B | Estado vacío diferenciado de fallo técnico. |

## Requerimientos no funcionales

La clasificación aprobada suma 25 obligatorios, 7 parcialmente aplicables, 3
deseables, 2 mejoras futuras y 3 no aplicables. El estado indica el corte real,
no una declaración de cumplimiento absoluto.

| ID | Clasificación | Estado actual | Evidencia | Limitación |
|---|---|---|---|---|
| RNF-01 | Obligatorio | Pendiente | Plan de vista controlada | Credencial aún no implementada. |
| RNF-02 | Obligatorio | Pendiente | Criterio documentado | No existe pantalla de credencial. |
| RNF-03 | Obligatorio | Pendiente | Regla de 30 s aprobada | No existe renovación visual. |
| RNF-04 | Obligatorio | Pendiente | Dashboard de escáner base | Faltan validación y mensajes finales. |
| RNF-05 | Obligatorio | Pendiente | Flujo propuesto de captura manual | No se ha medido el número de pasos. |
| RNF-06 | Obligatorio | Parcial | Validaciones en PySide6 y formularios web | No existen todas las pantallas finales. |
| RNF-07 | Obligatorio | Pendiente | Criterio temporal documentado | No hay validación QR para medir. |
| RNF-08 | Obligatorio | Pendiente | Arquitectura web disponible | No existe generación QR. |
| RNF-09 | Parcialmente aplicable | Pendiente | SQLite local y pruebas aisladas | No se probaron 20 validaciones simultáneas; SQLite no es producción multiusuario. |
| RNF-10 | Obligatorio | Pendiente | Persistencia preparada | No existe historial funcional ni medición. |
| RNF-11 | Parcialmente aplicable | Parcial | Autenticación de administrador y escáner | Alumno no tiene cuenta completa y tutores están excluidos. |
| RNF-12 | Obligatorio | Cumplido en el incremento | `role_required` y pruebas de 403 | Solo cubre los dos roles aprobados. |
| RNF-13 | No aplicable | No aplica | Tutores fuera de EduPass 1.0 | Se revisará si el alcance cambia. |
| RNF-14 | Obligatorio | Pendiente | Decisión de token opaco | Debe verificarse con el QR real. |
| RNF-15 | Parcialmente aplicable | Parcial | Demostración local por HTTP | HTTP local no equivale a HTTPS. |
| RNF-16 | Obligatorio | Cumplido | Hash de contraseñas y pruebas de autenticación | No constituye auditoría criptográfica externa. |
| RNF-17 | Parcialmente aplicable | Parcial | Tabla de intentos rechazados | No hay auditoría funcional de escaneos ni registro completo de accesos fallidos. |
| RNF-18 | Obligatorio | Cumplido | Sesión permanente configurable de 30 min | Requiere nueva revisión bajo despliegue real. |
| RNF-19 | Obligatorio | Cumplido | Paquetes por dominio y capa web separada | Debe conservarse durante Semana 12. |
| RNF-20 | Obligatorio | Cumplido en módulos existentes | Interfaz, servicios y repositorios separados | QR y movimientos aún deben respetar la separación. |
| RNF-21 | Obligatorio | Parcial | Errores compartidos y mensajes web controlados | Falta cubrir los módulos pendientes. |
| RNF-22 | Obligatorio | Pendiente | Duración inicial aprobada | Configuración del QR aún no existe. |
| RNF-23 | Obligatorio | Cumplido | Alumnos separado de autenticación y web | Debe evitarse acoplamiento con escaneo. |
| RNF-24 | No aplicable | No aplica | Áreas y notificaciones fuera de 1.0 | Los archivos base no acreditan funcionalidad. |
| RNF-25 | Obligatorio | Preparado | Módulos separados de validación y movimientos | Ambos módulos carecen de lógica funcional. |
| RNF-26 | No aplicable | No aplica | Áreas fuera de EduPass 1.0 | No se validará extensibilidad de áreas. |
| RNF-27 | Parcialmente aplicable | Pendiente | Decisión de web responsiva | Falta credencial y evidencia en navegador móvil. |
| RNF-28 | Deseable | Pendiente | Cámara declarada opcional | La captura manual seguirá siendo obligatoria. |
| RNF-29 | Obligatorio | Preparado y probado técnicamente | Pruebas web y HTML estándar | Requiere evidencia final en los navegadores disponibles. |
| RNF-30 | Obligatorio | Parcial | CSS responsivo y revisión técnica | No existe validación pixel-perfect en móvil, tablet y escritorio. |
| RNF-31 | Obligatorio | Pendiente | Plan de pruebas QR | No existe módulo QR funcional. |
| RNF-32 | Obligatorio | Pendiente | Plan de casos exitosos y rechazados | No existe escaneo funcional. |
| RNF-33 | Obligatorio | Cumplido en el incremento | Pruebas web por rol y 403 | Debe ampliarse al flujo de escaneo real. |
| RNF-34 | Mejora futura | Fuera del corte | Prueba estructural de columna `estado` | Notificaciones push fuera de EduPass 1.0. |
| RNF-35 | Mejora futura | Pendiente | RF-47 en Nivel 2 | El historial básico precede a los filtros. |
| RNF-36 | Parcialmente aplicable | Pendiente | Casos de plantel planeados | Entradas y salidas internas están fuera de 1.0. |
| RNF-37 | Obligatorio | Parcial | README y documentación técnica | El flujo QR se documentará al implementarlo. |
| RNF-38 | Deseable | Pendiente | Documentación de cierre iniciada | Falta guía final de administrador. |
| RNF-39 | Deseable | Pendiente | Alcance del escáner documentado | Falta guía operativa del flujo real. |
| RNF-40 | Parcialmente aplicable | Parcial | Reglas de inconsistencias documentadas | Notificaciones y permisos por área están excluidos. |

### Conteo RNF

| Clasificación | Cantidad |
|---|---:|
| Obligatorio | 25 |
| Parcialmente aplicable | 7 |
| Deseable | 3 |
| Mejora futura | 2 |
| No aplicable | 3 |
| **Total** | **40** |
