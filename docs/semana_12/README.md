# Semana 12 - Etapa A

## Objetivo

Implementar y verificar la credencial digital administrativa de EduPass con un
token QR temporal, opaco, de 30 segundos y de un solo uso.

## Alcance y estado

La Etapa A está implementada para el prototipo académico:

- generación y renovación de tokens para alumnos activos;
- persistencia exclusiva del hash SHA-256;
- vigencia calculada en UTC;
- invalidación de tokens anteriores;
- consumo atómico de un solo uso;
- credencial visible únicamente en una sesión administrativa;
- QR SVG generado en memoria y alternativa de captura manual;
- validación exclusiva para personal de escaneo;
- controles de rol, CSRF y respuestas sin caché.

La Etapa B está pendiente. No se registran movimientos ni historial. Tampoco se
incluyen cámara, cuenta de alumno, portal público, aplicación móvil,
notificaciones, tutores, áreas funcionales o dispositivos funcionales.

## Documentos

- [Contrato técnico](contrato_tecnico.md)
- [Implementación QR](implementacion_qr.md)
- [Evidencias y pruebas](evidencias_y_pruebas.md)
- [Matriz de trazabilidad](matriz_trazabilidad.md)
- [Limitaciones y pendientes](limitaciones_y_pendientes.md)

## Commits técnicos auditados

- `5df3b12`: persistencia y servicios de QR temporal.
- `d08bd2e`: credencial y validación QR web.
- `452cf20`: corrección del aviso obsoleto del panel y prueba de regresión.

## Pruebas

La evolución registrada fue de 172 pruebas previas a 242 tras el núcleo y 316
tras la integración web. La auditoría agregó una prueba de regresión, por lo que
el total actual es de 317 pruebas en estado `OK`.

Desde la raíz:

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -p "test_*.py"
```

Las pruebas usan SQLite temporal y no escriben en `data/edupass.sqlite`.

## Uso académico

EduPass es un prototipo para una sola escuela, pensado para ejecución local o
en una red privada. SQLite y HTTP local son adecuados para la demostración
académica, no para un despliegue multiusuario de producción.
