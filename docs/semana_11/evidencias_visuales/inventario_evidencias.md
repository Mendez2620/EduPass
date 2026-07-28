# Inventario de evidencias visuales - Semana 11

Las capturas utilizan exclusivamente cuentas y alumnos ficticios. Los registros
preexistentes de la base local se ocultaron en el navegador antes de capturar
el listado para evitar exponer información ajena a la demostración.

| Identificador | Archivo | Descripción | Estado | Resultado demostrado | Limitación | Requerimiento relacionado |
|---|---|---|---|---|---|---|
| E-11-01 | [E-11-01_login_web.png](E-11-01_login_web.png) | Pantalla inicial de autenticación web. | Completada | Formulario de correo y contraseña, acceso autorizado y alcance local. | Los textos visibles conservan la ortografía actual del sistema. | RF-16, RNF-06 |
| E-11-01B | [E-11-01B_login_error_credenciales.png](E-11-01B_login_error_credenciales.png) | Validación negativa con credenciales ficticias incorrectas. | Completada con observación | Mensaje genérico sin exponer contraseña ni causa interna. | El correo mostrado es ficticio; el campo de contraseña está vacío. | RF-16, RNF-21 |
| E-11-02 | [E-11-02_dashboard_administrador.png](E-11-02_dashboard_administrador.png) | Panel del usuario Administrador Demo. | Completada | Rol administrador, acceso al listado y aviso de funciones pendientes. | QR y movimientos se mencionan como siguiente incremento. | RF-16, RNF-12 |
| E-11-03A | [E-11-03A_listado_vacio.png](E-11-03A_listado_vacio.png) | Caso límite del listado sin alumnos. | Completada como caso límite | Mensaje controlado cuando no existen registros. | Se utilizó una SQLite temporal aislada; no se borraron alumnos de la base local. | RF-01, RNF-21 |
| E-11-03B | [E-11-03B_listado_con_alumnos.png](E-11-03B_listado_con_alumnos.png) | Listado con dos alumnos ficticios y estados distintos. | Completada | Persistencia de DEMO001 activo y DEMO002 inactivo; seis columnas de solo lectura. | Se ocultaron visualmente filas preexistentes por privacidad, sin modificar la base. | RF-01, RF-04 |
| E-11-04 | [E-11-04_dashboard_escaner.png](E-11-04_dashboard_escaner.png) | Panel de Personal de Escaneo. | Completada | Separación por rol y mensaje honesto sobre QR pendiente. | No existe escaneo funcional en Semana 11. | RF-16, RNF-12 |
| E-11-05 | [E-11-05_error_403.png](E-11-05_error_403.png) | Acceso del rol escáner a `/admin`. | Completada | Respuesta 403 controlada, sin traceback. | La evidencia corresponde al acceso cruzado entre los dos roles aprobados. | RF-16, RNF-12, RNF-33 |
| E-11-06 | [E-11-06_error_404.png](E-11-06_error_404.png) | Solicitud a `/no-existe`. | Completada | Respuesta 404 y enlace seguro. | No representa un error interno del servidor. | RNF-21 |
| E-11-07 | [E-11-07_vista_responsive.png](E-11-07_vista_responsive.png) | Listado administrativo a 390 por 812 píxeles. | Completada | Navegación adaptable, ausencia de superposición y tabla desplazable. | Las columnas posteriores requieren desplazamiento horizontal; no acredita validación pixel-perfect. | RNF-29, RNF-30 |
| E-11-08 | [E-11-08_pruebas_172_ok.png](E-11-08_pruebas_172_ok.png) | Registro real de la suite abierto y capturado en Chrome. | Completada con observación | Comando, `Ran 172 tests in 21.643s` y `OK`. | Windows no expuso una ventana de consola capturable; se representó sin alterar el registro real guardado temporalmente. | RNF-31, RNF-32, RNF-33 |
| E-11-09 | [E-11-09_commits_git.png](E-11-09_commits_git.png) | Registro real de comandos Git abierto y capturado en Chrome. | Completada con observación | Seis commits, rama sincronizada y SHA local/remoto iguales. | La salida muestra las carpetas de evidencias aún sin rastrear; no hubo staging. | RNF-37 |
| E-11-10 | [E-11-10_github_actualizado.png](E-11-10_github_actualizado.png) | Repositorio público EduPass en la rama `master`. | Completada | Commit documental `3973340`, estructura principal y README disponibles. | Se recortó únicamente la barra lateral con información pública irrelevante. | RNF-37 |

## Observaciones

- Los textos `Iniciar sesion`, `Contrasena`, `Administracion`, `Matricula`,
  `Escaneo` y `Prototipo academico` aparecen sin acento en la interfaz actual.
  No se modificaron porque este cierre prohíbe cambios de código o plantillas.
- `Administrador Demo`, `Personal de Escaneo`, `Ana López Demo` y
  `Carlos Pérez Demo` son nombres ficticios creados exclusivamente para estas
  evidencias.
- No se muestran contraseñas, claves de sesión, rutas de fotografía, fotografías
  ni datos personales reales.

QR, movimientos e historial continúan pendientes para Semana 12 conforme al
alcance aprobado. Su ausencia no representa un incumplimiento de Semana 11.
