# Inventario de evidencias visuales — Semana 12, Etapa B

Las identidades empleadas son completamente ficticias y pertenecen al dominio
reservado `edupass.test`. La demostración utilizó una base SQLite temporal fuera
del repositorio; no se utilizó `data/edupass.sqlite`. Los tokens empleados
quedaron inutilizados al finalizar el flujo y ninguno se reproduce en este
documento.

| ID | Archivo | Función demostrada | Escenario | Resultado | Datos utilizados | Observaciones |
|---|---|---|---|---|---|---|
| E-12-B-01 | [E-12-B-01_formulario_movimiento.png](E-12-B-01_formulario_movimiento.png) | Captura manual de movimiento | Formulario de escáner con selector y campo vacío | Formulario disponible para Entrada o Salida | Personal de escaneo ficticio | El token no aparece en la captura. |
| E-12-B-02 | [E-12-B-02_entrada_registrada.png](E-12-B-02_entrada_registrada.png) | Registro de entrada | Primera entrada de Ana Etapa B | Entrada registrada correctamente | Alumna y personal ficticios | El campo quedó limpio tras el envío. |
| E-12-B-03 | [E-12-B-03_doble_entrada_rechazada.png](E-12-B-03_doble_entrada_rechazada.png) | Regla de secuencia | Segunda entrada sin salida previa | Rechazo visual confirmado | Alumna y personal ficticios | La conservación del QR se confirmó mediante prueba automatizada y consulta técnica a la base temporal. |
| E-12-B-04 | [E-12-B-04_salida_registrada.png](E-12-B-04_salida_registrada.png) | Registro de salida | Salida posterior al rechazo | Salida registrada correctamente | Alumna y personal ficticios | Se utilizó el QR que permaneció activo tras el rechazo. |
| E-12-B-05 | [E-12-B-05_nueva_entrada.png](E-12-B-05_nueva_entrada.png) | Continuidad de secuencia | Nueva entrada posterior a la salida | Entrada registrada correctamente | Alumna y personal ficticios | Confirma la secuencia Entrada–Salida–Entrada. |
| E-12-B-06 | [E-12-B-06_historial_vacio.png](E-12-B-06_historial_vacio.png) | Estado vacío de historial | Luis Sin Movimientos | Mensaje de ausencia de movimientos | Alumno ficticio sin movimientos | No se crearon movimientos para este alumno. |
| E-12-B-07 | [E-12-B-07_historial_movimientos.png](E-12-B-07_historial_movimientos.png) | Historial administrativo | Historial de Ana Etapa B | Tres movimientos en orden descendente | Alumna y responsable ficticios | Muestra Entrada, Salida y Entrada, punto de acceso y responsable. |
| E-12-B-08 | [E-12-B-08_detalle_movimiento.png](E-12-B-08_detalle_movimiento.png) | Detalle administrativo | Consulta del movimiento más reciente | Detalle seguro disponible | Datos ficticios del movimiento | No expone el token ni su hash. |
| E-12-B-09 | [E-12-B-09_admin_403_escaner.png](E-12-B-09_admin_403_escaner.png) | Separación de roles | Administrador intenta abrir el registro del escáner | Acceso no autorizado, 403 | Cuenta administrativa ficticia | Conserva el control de acceso del módulo. |
| E-12-B-10 | [E-12-B-10_escaner_403_historial.png](E-12-B-10_escaner_403_historial.png) | Separación de roles | Escáner intenta abrir el historial administrativo | Acceso no autorizado, 403 | Cuenta de escáner ficticia | Conserva la exclusividad del panel administrativo. |
| E-12-B-11 | [E-12-B-11_formulario_responsive.png](E-12-B-11_formulario_responsive.png) | Presentación responsive del escáner | Formulario en viewport 390 × 812 | Controles visibles y sin superposición | Cuenta de escáner ficticia | El campo de token está vacío. |
| E-12-B-12 | [E-12-B-12_historial_responsive.png](E-12-B-12_historial_responsive.png) | Presentación responsive del historial | Historial en viewport 390 × 812 | Vista usable con contenedor de tabla | Alumna ficticia | La tabla conserva su contenido en pantalla móvil. |
| E-12-B-13 | [E-12-B-13_pruebas_484_ok.png](E-12-B-13_pruebas_484_ok.png) | Validación automatizada | Suite completa de `unittest` | 484 pruebas, cero errores y cero fallos | Bases temporales de prueba | Corresponde a la salida real necesaria de la ejecución. |
| E-12-B-14 | [E-12-B-14_commits_etapa_b.png](E-12-B-14_commits_etapa_b.png) | Estado local de Git | Auditoría anterior al commit documental y al push | Dos commits técnicos locales; 0 detrás y 2 delante | Repositorio local | Registra `e292e59`, `0f15315` y la divergencia previa al cierre documental. |

Las evidencias se revisaron visualmente para excluir contraseñas, claves,
cookies, tokens reutilizables, hashes, rutas personales y datos reales.
