# Plan preliminar y controlado de Semana 12

Este documento es únicamente un plan. No selecciona bibliotecas, no crea código
y no declara implementadas las funciones descritas.

## Principios

- Mantener `interfaz web -> servicio -> repositorio -> SQL -> SQLite`.
- Reutilizar autenticación, alumnos y `DatabaseManager`.
- Usar un token opaco, sin datos personales legibles.
- Conservar 30 segundos y un solo uso como reglas obligatorias.
- Mantener captura manual del token como alternativa obligatoria.
- Considerar cámara opcional y deseable.
- Completar la Etapa A antes de iniciar la Etapa B.

## Etapa A - Credencial y QR

Requerimientos: RF-05, RF-09, RF-10, RF-11, RF-12, RF-13, RF-14 y RF-15.

### Dependencias y orden

1. Auditar `qr_tokens`, restricciones y contratos de tiempo.
2. Definir contratos de servicio y errores sin seleccionar aún biblioteca QR.
3. Crear SQL externo y repositorio de tokens.
4. Implementar emisión para alumno activo.
5. Implementar validación de existencia, vigencia y uso único.
6. Crear vista controlada de credencial.
7. Agregar captura manual en el panel de escáner.
8. Integrar representación QR solo después de auditar bibliotecas.
9. Agregar pruebas unitarias y web con reloj controlado.

### Entradas y salidas

| Elemento | Entrada | Salida |
|---|---|---|
| Credencial | Identificador controlado de alumno | Datos permitidos y token vigente |
| Emisión | Alumno activo y hora del servidor | Token opaco con emisión y vencimiento |
| Validación | Token capturado manualmente | Válido o rechazo específico |
| Consumo | Token válido no usado | Token marcado como usado una sola vez |

### Persistencia y capas

- Tabla principal: `qr_tokens`.
- Servicio de credencial: decide si el alumno activo puede recibir token.
- Servicio de validación: aplica vigencia, integridad y uso único.
- Repositorio QR: persiste y consulta tokens mediante SQL parametrizado.
- SQL: insertar, obtener, marcar usado e invalidar de forma atómica.
- Rutas: credencial controlada y validación de token.
- Pantallas: credencial y panel de escáner con entrada manual.

No se agregará cuenta completa de alumno, cámara obligatoria ni datos
personales dentro del token.

### Pruebas y criterios de aceptación

- Alumno activo obtiene credencial; inactivo no obtiene token.
- El token cambia al cumplirse 30 segundos usando un reloj controlado.
- Un token vencido se rechaza.
- Un token consumido no puede reutilizarse.
- Un token inexistente o alterado se rechaza.
- Dos validaciones concurrentes no consumen el mismo token dos veces.
- El contenido no expone nombre, matrícula, grado, grupo o fotografía.
- La captura manual funciona sin cámara.
- Las rutas conservan autenticación, rol y CSRF donde corresponda.

## Etapa B - Movimientos e historial

Requerimientos: RF-29, RF-30, RF-33, RF-34, RF-37, RF-38, RF-46, RF-48 y
RF-49.

### Dependencias y orden

1. Exigir Etapa A integrada y estable.
2. Auditar la tabla `movimientos` y los tipos aprobados para plantel.
3. Definir contratos de movimiento y reglas de secuencia.
4. Crear SQL externo y repositorio de movimientos.
5. Implementar entrada y salida como operaciones transaccionales.
6. Integrar consumo del token y movimiento sin duplicidad.
7. Implementar consulta básica por alumno.
8. Crear listado y detalle web.
9. Implementar estado vacío “sin resultados”.
10. Completar pruebas unitarias, integración y web.

### Entradas y salidas

| Elemento | Entrada | Salida |
|---|---|---|
| Entrada | Token válido, alumno y usuario escáner | Movimiento de entrada completo |
| Salida | Token válido, entrada activa y usuario escáner | Movimiento de salida completo |
| Rechazo | Secuencia inconsistente | Motivo claro, sin movimiento inválido |
| Historial | Alumno seleccionado | Movimientos básicos ordenados |
| Detalle | Identificador de movimiento | Alumno, fecha/hora, tipo, punto y responsable |

### Persistencia y capas

- Tabla principal: `movimientos`.
- Tablas relacionadas: `alumnos`, `usuarios` y `qr_tokens`.
- Servicio de movimientos: secuencia, tipo, consistencia y coordinación.
- Repositorio: escritura transaccional y consultas, sin reglas de interfaz.
- SQL: último movimiento, insertar, listar por alumno y obtener detalle.
- Rutas: validar/registrar, historial por alumno y detalle.
- Pantallas: resultado de escaneo, historial básico y detalle.

No se usarán áreas internas, dispositivos fijos, tutores ni notificaciones.
`punto_plantel` deberá representar el acceso principal sin convertirlo en un
módulo de áreas.

### Pruebas y criterios de aceptación

- Entrada válida persiste todos los campos de RF-33.
- Salida válida requiere una entrada previa activa.
- Doble entrada o doble salida consecutiva se rechaza.
- Un rechazo no crea un movimiento.
- El token se consume una sola vez junto con el movimiento.
- El resultado del escaneo informa éxito o causa de rechazo.
- El historial muestra los movimientos del alumno solicitado.
- El detalle presenta alumno, fecha/hora, tipo, punto y responsable.
- Una consulta vacía muestra “sin resultados”, distinta de un error técnico.
- Las pruebas usan SQLite temporal y no `data/edupass.sqlite`.

## Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Biblioteca QR elegida sin auditoría | Dependencia innecesaria o insegura | Evaluar mantenimiento, licencia, API y pruebas antes de seleccionarla. |
| Desfase de reloj | Tokens aceptados o rechazados incorrectamente | Usar hora del servidor y reloj inyectable en pruebas. |
| Carrera de uso único | Dos movimientos para un token | Transacción y actualización atómica condicionada por estado. |
| Acoplar validación y movimientos | Difícil prueba y mantenimiento | Contratos separados y coordinación explícita en servicio. |
| Concurrencia SQLite | Bloqueos durante demostración | Operaciones cortas, transacciones acotadas y sin conexión global. |
| Cámara o permisos del navegador | Demo bloqueada por hardware | Mantener captura manual como flujo obligatorio. |
| Acceso desde teléfono | Diferencias de red y navegador | Probar red privada, host, firewall y navegadores disponibles. |
| Exceso de alcance | Incremento incompleto | No agregar áreas, tutores, push, filtros avanzados ni aplicación nativa. |
| Fotografías como rutas locales | Recursos no visibles desde otro equipo | No mostrar ni cargar fotografía en el flujo web 1.0. |

## Definición de terminado

Semana 12 termina solamente si:

- los 17 RF de ambas etapas tienen evidencia acorde con su estado;
- el flujo manual completo funciona desde credencial hasta historial;
- QR vence a 30 segundos y es de un solo uso;
- no se exponen datos personales en el token;
- las reglas de entrada, salida y duplicidad son transaccionales;
- existen pruebas normales, límite, error, integración y autorización;
- la suite completa termina en `OK` con bases temporales;
- las pantallas son utilizables en escritorio y móvil disponible;
- se actualizan trazabilidad, README y bitácora;
- no se agregan funciones de Nivel 3;
- se crea un commit revisado y se congela el desarrollo funcional grande.
