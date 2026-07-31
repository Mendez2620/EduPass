# Semana 12

## Objetivo

Implementar y verificar el flujo técnico que parte de una credencial QR
temporal y culmina en movimientos de entrada y salida consultables por el
administrador.

## Etapa A — Terminada

La Etapa A está terminada para el prototipo académico:

- generación y renovación de tokens para alumnos activos;
- persistencia exclusiva del hash SHA-256;
- vigencia calculada en UTC;
- invalidación de tokens anteriores;
- consumo atómico de un solo uso;
- credencial visible únicamente en una sesión administrativa;
- QR SVG generado en memoria y alternativa de captura manual;
- validación exclusiva para personal de escaneo;
- controles de rol, CSRF y respuestas sin caché.

Sus catorce evidencias visuales definitivas permanecen documentadas en el
inventario de Etapa A.

## Etapa B — Implementación técnica terminada

La Etapa B implementa:

- registro transaccional de entrada y salida;
- reglas de secuencia histórica;
- consumo QR e inserción del movimiento en una sola transacción;
- rollback total y concurrencia controlada;
- responsable escáner, hora UTC y punto `acceso_principal`;
- selector Entrada/Salida y mensajes públicos controlados;
- historial administrativo por alumno;
- estado vacío, paginación de 50 y detalle;
- controles de rol, CSRF y prevención de IDOR;
- interfaz responsive y prevención de doble envío;
- 484 pruebas en estado `OK`.

Los commits técnicos son:

- `e292e59766fbdffe7eeebf6f568eaf6e6f2add36`: núcleo transaccional;
- `0f15315d0a1edddeddb0f7c7ad41accb754ee958`: integración web e historial.

Las catorce evidencias visuales definitivas de Etapa B fueron capturadas y
validadas mediante una demostración temporal aislada. La documentación y las
evidencias de Etapa B fueron publicadas en el commit `f15b7e2a`. EduPass 1.0 no
está completamente cerrado.

## Documentos

- [Contrato técnico de Etapa A](contrato_tecnico.md)
- [Implementación QR](implementacion_qr.md)
- [Contrato de Etapa B](contrato_etapa_b.md)
- [Implementación de movimientos](implementacion_movimientos.md)
- [Bitácora Codex de Etapa B](bitacora_codex_etapa_b.md)
- [Evidencias y pruebas](evidencias_y_pruebas.md)
- [Inventario visual de Etapa B](evidencias_visuales_etapa_b/inventario_evidencias.md)
- [Matriz de trazabilidad](matriz_trazabilidad.md)
- [Limitaciones y pendientes](limitaciones_y_pendientes.md)

## Commits técnicos auditados

- `5df3b12`: persistencia y servicios de QR temporal.
- `d08bd2e`: credencial y validación QR web.
- `452cf20`: corrección del aviso obsoleto del panel y prueba de regresión.
- `e292e59`: movimientos transaccionales con QR.
- `0f15315`: integración web, historial y pruebas.

## Pruebas

La Etapa A cerró con 317 pruebas. El núcleo de movimientos agregó 64 para un
subtotal de 381. La integración web agregó o ajustó 103, por lo que el total
actual es de 484 pruebas en estado `OK`.

Desde la raíz:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -p "test_*.py"
```

Las pruebas usan bases temporales y no escriben en la base local del proyecto.

## Uso académico

EduPass es un prototipo para una sola escuela, pensado para ejecución local o
en una red privada. SQLite y HTTP local son adecuados para la demostración
académica, no para un despliegue multiusuario de producción. Continúan
pendientes el CRUD web completo, el rol e interfaz del alumno, la cámara, los
intentos rechazados, HTTPS productivo y otras funciones posteriores.
