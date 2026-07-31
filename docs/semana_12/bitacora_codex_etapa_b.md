# Bitácora Codex de Semana 12, Etapa B

## 1. Auditoría y contrato técnico

- **Objetivo:** definir el alcance transaccional y verificar la línea base.
- **Decisiones:** QR y movimiento debían confirmarse en una sola transacción;
  los rechazos de secuencia no debían consumir el QR; el responsable y la hora
  procederían del backend.
- **Archivos revisados:** esquema, servicios QR, repositorios, errores,
  constantes y pruebas existentes.
- **Pruebas:** la línea base previa al núcleo fue de 317 pruebas en estado OK.
- **Resultado:** contrato aprobado para entrada, salida, secuencia, rollback y
  concurrencia.
- **Commit:** no aplicaba todavía.
- **Observaciones:** no hubo push durante la intervención.

## 2. Implementación del núcleo

- **Objetivo:** implementar movimientos transaccionales con QR.
- **Decisiones:** SQL externo, `BEGIN IMMEDIATE`, consumo condicional,
  serialización UTC, punto `acceso_principal`, área y dispositivo nulos.
- **Archivos principales:** `schema.sql`, `time_utils.py`,
  `_qr_consumption.py`, `movimiento_repository.py`,
  `movimientos_service.py`, consultas SQL de movimientos y dos suites nuevas.
- **Pruebas:** 64 pruebas nuevas de repositorio y servicio; subtotal de 381.
- **Resultado:** atomicidad, rollback, concurrencia y secuencias validados.
- **Commit:** `e292e59766fbdffe7eeebf6f568eaf6e6f2add36`.
- **Observaciones:** 17 archivos; sin integración web ni documentación; no hubo
  push durante la intervención.

## 3. Implementación web e historial

- **Objetivo:** registrar movimientos desde el escáner y consultarlos desde el
  panel administrativo.
- **Decisiones:** selector obligatorio, responsable obtenido del usuario
  autenticado, mensajes públicos controlados, historial paginado a 50,
  detalle con comprobación alumno-movimiento y JavaScript limitado a prevenir
  doble envío.
- **Archivos principales:** servicio de historial, consultas de historial,
  formularios, rutas del escáner y administrador, plantillas, CSS, JavaScript y
  suites web.
- **Pruebas:** 103 pruebas nuevas o ajustadas; total de 484.
- **Resultado:** entrada, salida, estado vacío, historial, detalle, roles,
  CSRF, IDOR, responsive y privacidad validados.
- **Commit:** `0f15315d0a1edddeddb0f7c7ad41accb754ee958`.
- **Observaciones:** 22 archivos; sin documentación; no hubo push durante la
  intervención.

## 4. Ajuste de prueba histórica

- **Objetivo:** alinear una regresión del panel de escáner con la interfaz ya
  aprobada.
- **Decisiones:** exigir exclusivamente **Registro de movimientos**,
  **Registrar entrada o salida** y la explicación positiva de entradas y
  salidas; conservar ruta, ausencia de cámara y finalidad del caso.
- **Archivo:** `tests/test_web_roles.py`.
- **Pruebas:** 7 casos de roles y suite completa de 484, ambos en OK.
- **Resultado:** no se eliminó el caso ni se redujo el número de aserciones.
- **Commit:** incluido en `0f15315d0a1edddeddb0f7c7ad41accb754ee958`.
- **Observaciones:** no hubo push durante la intervención.

## 5. Preparación documental

- **Objetivo:** documentar de forma verificable el contrato, la implementación,
  las pruebas, la trazabilidad y los pendientes de Etapa B.
- **Decisiones:** conservar íntegra la evidencia de Etapa A; declarar la
  implementación técnica de Etapa B terminada; capturar y validar las
  evidencias visuales; mantener el commit documental y la publicación como
  pendientes.
- **Archivos:** tres documentos nuevos, cuatro documentos de Semana 12
  actualizados, un inventario y catorce PNG.
- **Pruebas:** antes de editar se ejecutaron 484 pruebas con cero errores y cero
  fallos.
- **Resultado:** demostración temporal completada y catorce evidencias visuales
  capturadas y validadas; documentación técnica preparada para revisión.
- **Commit:** pendiente.
- **Observaciones:** el
  [inventario visual de Etapa B](evidencias_visuales_etapa_b/inventario_evidencias.md)
  registra la evidencia funcional, responsive y técnica. No se hizo staging,
  commit ni push en esta preparación.
