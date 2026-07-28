# Evidencias y pruebas

## Evolución

| Etapa | Total | Resultado |
|---|---:|---|
| Base previa de Semana 11 | 172 | OK |
| Núcleo QR | 242 | OK |
| Integración web | 316 | OK |
| Auditoría y prueba de regresión | 317 | OK |

Las 70 pruebas del núcleo se distribuyen en:

- repositorio QR: 24;
- servicio de credencial: 23;
- servicio de validación: 23.

Las 74 pruebas web agregadas se distribuyen en:

- renderizador QR: 14;
- credencial web: 30;
- validación QR web: 30.

La auditoría añadió una prueba a `test_web_roles.py` para verificar que el panel
administrativo informe que la credencial QR ya está disponible.

## Comandos y resultados de auditoría

```powershell
$env:PYTHONPATH="src"
python -m unittest tests.test_qr_token_repository
python -m unittest tests.test_credencial_service
python -m unittest tests.test_validacion_qr_service
python -m unittest tests.test_qr_renderer
python -m unittest tests.test_web_credencial
python -m unittest tests.test_web_qr_validation
python -m unittest tests.test_web_roles
python -m unittest discover -s tests -p "test_*.py"
```

| Suite | Pruebas | Duración unittest | Resultado |
|---|---:|---:|---|
| `test_qr_token_repository` | 24 | 2.482 s | OK |
| `test_credencial_service` | 23 | 2.472 s | OK |
| `test_validacion_qr_service` | 23 | 2.293 s | OK |
| `test_qr_renderer` | 14 | 0.118 s | OK |
| `test_web_credencial` | 30 | 11.470 s | OK |
| `test_web_qr_validation` | 30 | 11.233 s | OK |
| `test_web_roles`, antes de la corrección | 6 | 2.466 s | OK |
| `test_web_roles`, después de la corrección | 7 | 2.247 s | OK |

La suite inicial de auditoría ejecutó 316 pruebas en 45.919 s (`OK`). Después de
la corrección, la suite ejecutó 317 pruebas en 47.317 s (`OK`). Puede aparecer la
advertencia controlada del listado administrativo; no produjo error ni fallo.

No se midió porcentaje de cobertura.

## Validación manual aislada

Se utilizó una base SQLite temporal fuera del repositorio con usuarios y alumnos
ficticios. Se verificó:

- acceso y separación de administrador y escáner;
- listado con generación habilitada para alumno activo y deshabilitada para
  alumno inactivo;
- rechazo de alumno inactivo también desde el servicio;
- matrícula enmascarada, SVG en memoria, token manual y vigencia de 30 segundos;
- renovación manual y automática, con invalidación del token anterior;
- consumo válido, segundo uso rechazado, token alterado rechazado y token
  vencido rechazado;
- visitante redirigido, roles incorrectos con 403 y GET sobre rutas POST con 405;
- cero movimientos y cero intentos rechazados persistidos;
- cero archivos SVG o PNG creados;
- cierre del servidor sin traceback y eliminación de la base temporal.

La interfaz fue revisada en anchos de 390, 768 y 1366 píxeles sin desbordamientos
funcionales observados. Las pruebas web verifican CSRF, roles, encabezados de
seguridad y ausencia de datos sensibles en respuestas.

Las capturas visuales definitivas se documentarán en un cierre separado.
