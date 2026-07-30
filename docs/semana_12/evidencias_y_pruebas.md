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

## Evidencias visuales definitivas de Etapa A

El [inventario de evidencias visuales](evidencias_visuales/inventario_evidencias.md)
reúne las catorce capturas definitivas. Todas emplean nombres y matrículas
ficticios; los correos de demostración utilizan el dominio reservado
`edupass.test`. Las validaciones funcionales usaron SQLite temporal y aislada,
sin escribir en `data/edupass.sqlite`, y las bases temporales fueron eliminadas.

| Identificador | Descripción | Estado | Archivo |
|---|---|---|---|
| E-12-01 | Listado administrativo y acceso a credenciales. | Completada. | [E-12-01](evidencias_visuales/E-12-01_listado_credencial.png) |
| E-12-02 | Credencial digital con QR temporal. | Completada con observación. | [E-12-02](evidencias_visuales/E-12-02_credencial_qr.png) |
| E-12-03 | Renovación de la credencial temporal. | Completada. | [E-12-03](evidencias_visuales/E-12-03_renovacion_token.png) |
| E-12-04 | Captura manual para personal de escaneo. | Completada. | [E-12-04](evidencias_visuales/E-12-04_formulario_escaner.png) |
| E-12-05 | Token válido y consumido. | Completada. | [E-12-05](evidencias_visuales/E-12-05_token_valido.png) |
| E-12-06 | Rechazo de token reutilizado. | Completada. | [E-12-06](evidencias_visuales/E-12-06_token_reutilizado.png) |
| E-12-07 | Rechazo de token vencido. | Completada. | [E-12-07](evidencias_visuales/E-12-07_token_vencido.png) |
| E-12-08 | Rechazo de token inválido. | Completada. | [E-12-08](evidencias_visuales/E-12-08_token_invalido.png) |
| E-12-09 | Alumno inactivo sin credencial. | Completada con observación. | [E-12-09](evidencias_visuales/E-12-09_alumno_inactivo.png) |
| E-12-10 | Respuesta 403 por control de rol. | Completada. | [E-12-10](evidencias_visuales/E-12-10_error_403_rol.png) |
| E-12-11 | Credencial en presentación móvil. | Completada con observación. | [E-12-11](evidencias_visuales/E-12-11_credencial_responsive.png) |
| E-12-12 | Suite completa de 317 pruebas. | Completada con observación. | [E-12-12](evidencias_visuales/E-12-12_pruebas_317_ok.png) |
| E-12-13 | Estado real de Git y commits. | Completada con observación. | [E-12-13](evidencias_visuales/E-12-13_commits_git.png) |
| E-12-14 | Repositorio actualizado en GitHub. | Completada. | [E-12-14](evidencias_visuales/E-12-14_github_actualizado.png) |

La revisión de privacidad confirmó que las evidencias no muestran contraseñas,
`SECRET_KEY`, cookies, rutas privadas, fotografías, rutas de fotografías ni
datos personales reales. Los tokens visibles en E-12-02 y E-12-11 eran
ficticios y temporales; fueron invalidados o vencieron y ya no son utilizables.
No se reproducen en esta documentación.

E-12-09 muestra el alumno inactivo, el botón deshabilitado y la ausencia de QR.
El backend respondió HTTP 409 en una comprobación real con CSRF, aunque el
mensaje no quedó visible en la captura. E-12-11 fue validada con viewport
390 × 812; su captura de página completa mide 390 × 1755.

E-12-12 y E-12-13 presentan las salidas reales de unittest y Git mediante HTML
temporal servido por localhost, ya eliminado. La suite concluyó con 317 pruebas,
resultado `OK`, cero errores y cero fallos. GitHub mostraba `master`, el commit
`531f043` y la documentación de Semana 12 al momento de E-12-14.

La validación de Etapa A registró cero movimientos y persistió cero intentos
rechazados. La cámara, los movimientos y el historial continúan pendientes, al
igual que Etapa B. Etapa A está implementada para el flujo administrativo del
prototipo, con la limitación de que la credencial sólo se presenta desde una
sesión administrativa.
