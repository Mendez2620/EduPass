# Inventario de evidencias visuales

Capturas automáticas de EduPass real con SQLite temporal y datos ficticios. Las dimensiones reportadas son las dimensiones PNG efectivas del navegador. Se ejercitaron además los viewports solicitados de 390 × 844, 768 × 1024 y 1366 × 768; el backend del navegador descuenta su marco en algunas capturas.

| Evidencia | Dimensiones | SHA-256 | Observación |
|---|---:|---|---|
| [01_panel_administrador.png](01_panel_administrador.png) | 1351 × 760 | `ca84a4b0963048cfbb35bbc268d6046454763c7fbf9e793c619bae3a0a6e24a3` | Panel administrativo |
| [02_alumnos_integrados.png](02_alumnos_integrados.png) | 1351 × 760 | `9cc853261977c5ebdb90848c83e960f36f1356b190917dee465c723e99ac2d89` | Listado integrado |
| [03_alta_alumno_cuenta.png](03_alta_alumno_cuenta.png) | 1351 × 760 | `6cf5675913ca30e47724389097210be401c0b339a46d42261468172498d9d8f0` | Alta sin contraseña manual |
| [04_edicion_alumno_acceso.png](04_edicion_alumno_acceso.png) | 1351 × 760 | `9a47f0c18397618b4cd72365494bd83b15daa85f85a34c9e462c21b2bcb55eb8` | Edición escolar y acceso |
| [05_administradores.png](05_administradores.png) | 1366 × 768 | `036407b253aa5434e89e0b70af25619e38f406f1bcd0c05ea962518c6cf2cba2` | Gestión de administradores |
| [06_escaneres.png](06_escaneres.png) | 1366 × 768 | `6b63f9050666f0dadcbdbd45485f964299823906805a9ff7a10b61d1785695d4` | Gestión de escáneres |
| [07_cambio_password_obligatorio.png](07_cambio_password_obligatorio.png) | 1366 × 768 | `142df27d4d45998ce62be81a93d3db6716894175e8f746cf0432c3487a6bbbc5` | Sin contraseña temporal visible |
| [08_portal_alumno.png](08_portal_alumno.png) | 1366 × 768 | `869056c42c4d71d492652c384655d457219fa559dc8a8619016e419371946a9d` | Portal tras cambio correcto |
| [09_credencial_qr.png](09_credencial_qr.png) | 1351 × 760 | `c0dd49ec39e963fbf56468aa3ea9d94364e04d6382d5acfc71c64cf118031ccf` | QR visible, matrícula enmascarada, sin token textual |
| [10_escaner_movil_menu_cerrado.png](10_escaner_movil_menu_cerrado.png) | 390 × 843 | `0ca76daebecc5c9cee1a2ab74719d0a60951f68d8424334440865005b37d28f6` | Viewport móvil 390 × 844; menú cerrado |
| [11_interfaz_camara.png](11_interfaz_camara.png) | 375 × 811 | `61086f6acc27a3b8080250b8fe8de6ffcb4735fd6caf65cab5ba01318e9892a0` | Captura interna del viewport 390 × 844; guía, controles y respaldo manual; sin cámara física |
| [12_entrada_registrada.png](12_entrada_registrada.png) | 1265 × 712 | `d6c26335e341b1ebdfd46a1689985e3dd1b3b341da78cf017cea797add9c625f` | Entrada real enfocada |
| [13_salida_registrada.png](13_salida_registrada.png) | 1265 × 712 | `4506525d72085395aec29257ce82c128bd5e7a761b4540fd338fc80ef381a4fa` | Salida real enfocada |
| [14_notificaciones.png](14_notificaciones.png) | 1265 × 712 | `737ee3b4f61067bf061eed7cee8ca5636eb807b1822b9f756c8b4183e1f0a76f` | Notificaciones internas |
| [15_historial_alumno.png](15_historial_alumno.png) | 1265 × 712 | `46e000907fd4853aaf2c61d0e879a4acf2488b8160298549995f072b1cd44c14` | Historial personal |
| [16_error_controlado.png](16_error_controlado.png) | 1265 × 712 | `b421a98700b1ebe00936a5265c521b510c2e7785509bc4a0afde6fe674a3c7cb` | Reutilización rechazada sin detalles técnicos |
| [17_suite_final_ok.png](17_suite_final_ok.png) | 1366 × 768 | `837d38fa025a29bf532d99ba41140847c4424fc99fc17070e719db5b5c9e35ce` | Transcripción gráfica de salida real: 964, OK |
| [18_git_estado_historial.png](18_git_estado_historial.png) | 1366 × 768 | `fc9be617fa771107faafbb3c1c36ea08b48c42b2f1796817f4fc51efe4f76054` | Transcripción gráfica de `git status -sb` y log real |

## Revisión de privacidad

No se observan contraseñas, temporales, secretos, tokens textuales, hashes de credenciales, cookies, SQL, traceback, rutas SQLite, rutas locales, IP externas, túneles, datos reales ni pestañas personales. Los correos usan el dominio reservado `.example`. Los SHA-256 de esta tabla son firmas de los PNG, no hashes de autenticación.
