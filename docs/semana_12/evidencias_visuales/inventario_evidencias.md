# Inventario de evidencias visuales — Semana 12, Etapa A

| Identificador | Archivo | Descripción | Estado | Resultado demostrado | Limitación u observación | RF o RNF relacionado |
|---|---|---|---|---|---|---|
| E-12-01 | [E-12-01_listado_credencial.png](E-12-01_listado_credencial.png) | Listado administrativo de alumnos y acceso a credenciales. | Completada. | El alumno activo permite generar credencial y el alumno inactivo mantiene la acción deshabilitada. | Datos académicos ficticios. | RF-05, RF-09. |
| E-12-02 | [E-12-02_credencial_qr.png](E-12-02_credencial_qr.png) | Credencial digital con QR temporal. | Completada con observación. | Se muestran la credencial administrativa, el QR, la vigencia y la alternativa manual. | El token temporal quedó invalidado y ya no es utilizable. | RF-09, RF-10, RF-11, RF-15. |
| E-12-03 | [E-12-03_renovacion_token.png](E-12-03_renovacion_token.png) | Renovación e invalidación de credencial temporal. | Completada. | La credencial puede renovarse y el token anterior deja de ser válido. | La validación corresponde al flujo temporal de Etapa A. | RF-11, RF-12, RF-14. |
| E-12-04 | [E-12-04_formulario_escaner.png](E-12-04_formulario_escaner.png) | Formulario de captura manual para personal de escaneo. | Completada. | Existe un flujo manual claro para validar el token sin cámara. | La cámara continúa pendiente. | RF-10 y RNF de usabilidad. |
| E-12-05 | [E-12-05_token_valido.png](E-12-05_token_valido.png) | Validación correcta de un token vigente. | Completada. | El token válido se consume sin registrar movimientos. | Etapa A valida la credencial, pero no implementa movimientos. | RF-12 y RF-13. |
| E-12-06 | [E-12-06_token_reutilizado.png](E-12-06_token_reutilizado.png) | Rechazo de un token ya consumido. | Completada. | Se demuestra la restricción de un solo uso. | El intento rechazado no se persiste. | RF-12 y RF-13. |
| E-12-07 | [E-12-07_token_vencido.png](E-12-07_token_vencido.png) | Rechazo de un token vencido. | Completada. | Se demuestra el control de vigencia temporal. | El intento rechazado no se persiste. | RF-12 y RF-13. |
| E-12-08 | [E-12-08_token_invalido.png](E-12-08_token_invalido.png) | Rechazo de un token inválido. | Completada. | Se demuestra el rechazo seguro de entradas no válidas. | No se exponen detalles sensibles. | RF-14 y RF-15. |
| E-12-09 | [E-12-09_alumno_inactivo.png](E-12-09_alumno_inactivo.png) | Alumno inactivo sin generación de credencial. | Completada con observación. | La captura muestra estado inactivo, botón deshabilitado y ausencia de QR. | El backend respondió HTTP 409 en una comprobación real con CSRF, aunque el mensaje no aparece dentro de la imagen. | RF-05. |
| E-12-10 | [E-12-10_error_403_rol.png](E-12-10_error_403_rol.png) | Acceso denegado por control de rol. | Completada. | Un rol no autorizado recibe la respuesta 403 esperada. | La captura no muestra información privada de la sesión. | RNF de seguridad y control de roles. |
| E-12-11 | [E-12-11_credencial_responsive.png](E-12-11_credencial_responsive.png) | Credencial digital en presentación móvil. | Completada con observación. | El contenido se adapta al ancho móvil sin perder la información funcional. | Viewport validado en 390 × 812. La captura de página completa mide 390 × 1755. | RF-10 y RNF responsive. |
| E-12-12 | [E-12-12_pruebas_317_ok.png](E-12-12_pruebas_317_ok.png) | Ejecución real de la suite completa. | Completada con observación. | La suite ejecutó 317 pruebas con resultado OK, cero errores y cero fallos. | Salida real de unittest mostrada mediante HTML temporal servido por localhost. | RNF de pruebas. |
| E-12-13 | [E-12-13_commits_git.png](E-12-13_commits_git.png) | Estado real de Git y commits recientes. | Completada con observación. | Se demuestra la rama master sincronizada, divergencia 0/0, commits auditados y staging vacío. | Salida real de Git mostrada mediante HTML temporal servido por localhost; las evidencias aún no estaban comprometidas. | RNF de control de versiones. |
| E-12-14 | [E-12-14_github_actualizado.png](E-12-14_github_actualizado.png) | Repositorio EduPass actualizado en GitHub. | Completada. | GitHub muestra master, el commit 531f043 y contenido de Semana 12. | Verificación remota realizada antes de incorporar este paquete local de evidencias. | RNF de documentación y control de versiones. |

## Notas

- Todos los nombres y matrículas utilizados son ficticios.
- Los correos utilizan el dominio reservado `edupass.test`.
- No se utilizó `data/edupass.sqlite`.
- Las bases temporales fueron eliminadas.
- Los tokens visibles dejaron de ser utilizables.
- No aparecen contraseñas ni `SECRET_KEY`.
- No aparecen fotografías ni rutas de fotografías.
- No aparecen datos personales reales.
- No se registraron movimientos.
- No se persistieron intentos rechazados.
- No se implementó cámara.
- No se implementó historial.
- Etapa B continúa pendiente.
- E-12-09 se conserva con observación porque la respuesta HTTP 409 fue verificada, pero el mensaje no aparece en la captura.
- E-12-11 fue validada con viewport 390 × 812, aunque la captura de página completa mide 390 × 1755.
- E-12-12 y E-12-13 muestran salidas reales mediante HTML temporal servido por localhost.
