# Evidencias y pruebas de Semana 11

## 1. Comandos utilizados

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -p "test_*.py"
git branch --show-current
git rev-parse HEAD
git rev-parse origin/master
git status --short
git status -sb
git diff --check
git log -5 --oneline
```

Para la ejecución web local se documentó:

```powershell
$env:PYTHONPATH="src"
$env:EDUPASS_SECRET_KEY="<valor-local-privado>"
python -m edupass.web
```

El marcador anterior no es una clave real y no se almacena en el repositorio.

## 2. Evolución y distribución de pruebas

| Corte | Total | Resultado |
|---|---:|---|
| Alumnos y persistencia | 75 | OK |
| Después de autenticación | 137 | OK |
| Después de capa web | 172 | OK |

| Grupo | Cantidad |
|---|---:|
| Database manager | 9 |
| Repositorio de alumnos | 25 |
| Servicio de alumnos | 41 |
| Repositorio de roles | 8 |
| Repositorio de usuarios | 14 |
| Servicio de roles | 6 |
| Servicio de autenticación | 26 |
| Script de usuarios demo | 8 |
| Fábrica web | 8 |
| Autenticación web | 13 |
| Roles web | 6 |
| Alumnos web | 8 |
| **Total** | **172** |

No se ejecutó una herramienta de cobertura y no se declara un porcentaje.

## 3. Ejecución documental inicial

```text
Ran 172 tests in 22.202s
OK
```

Tiempo total medido por PowerShell: `22.851s`.

La advertencia del logger sobre la imposibilidad simulada de obtener el listado
administrativo corresponde a una prueba controlada de error de repositorio. No
produjo error ni fallo en `unittest`.

## 4. Ejecución documental final

```text
Ran 172 tests in 24.428s
OK
```

Tiempo total medido por PowerShell: `25.178s`.

La misma advertencia controlada del caso de error del listado apareció durante
la ejecución y no produjo errores ni fallos.

## 5. Aislamiento de datos

- Las pruebas crean bases SQLite temporales y aisladas.
- `data/edupass.sqlite` no se usa ni se modifica durante la suite.
- Las pruebas no inician un servidor web real.
- La validación manual publicada usó una base temporal fuera del repositorio y
  la eliminó al terminar.
- No se utilizan datos personales reales.

## 6. Rutas y controles verificados

| Evidencia técnica | Verificación |
|---|---|
| `/login` | Render, CSRF, autenticación válida y errores genéricos. |
| `/logout` | Solo `POST`, exige autenticación y CSRF, limpia sesión. |
| `/admin` | Acceso exclusivo de administrador. |
| `/admin/alumnos` | Listado de seis campos, vacío y error controlado. |
| `/scanner` | Acceso exclusivo de escáner y marcador honesto. |
| 403 | Acceso cruzado por rol rechazado. |
| 404 | Ruta inexistente usa respuesta controlada. |
| Sesión | Permanente, expiración configurable y recarga de usuario activo. |
| Cookies | `HttpOnly` y `SameSite=Lax`. |
| Configuración | Falta de `SECRET_KEY` y valores inválidos producen error claro. |

## 7. No exposición de información

Las pruebas y revisiones verifican que:

- `password_hash` no forma parte del usuario de sesión ni de respuestas
  seguras;
- las contraseñas no aparecen en plantillas, README ni logs;
- el listado web no recibe ni muestra fotografía o ruta de fotografía;
- `SECRET_KEY` no aparece con un valor real en archivos versionados;
- `.env.example` contiene nombres y valores no sensibles;
- no existe un archivo `.env`;
- no se versionan bases SQLite locales.

## 8. Validación manual

La auditoría técnica publicada comprobó con una base temporal:

1. inicio del proceso web sin traceback;
2. respuesta de la pantalla de login;
3. autenticación de administrador;
4. autenticación de escáner;
5. separación de acceso entre paneles;
6. listado administrativo;
7. cierre de sesión;
8. cierre del servidor y eliminación del entorno temporal.

Las capturas finales de este cierre agregan evidencia funcional con cuentas y
alumnos ficticios. La vista responsiva fue comprobada en Chrome a 390 por 812
píxeles; esta verificación no equivale a una validación pixel-perfect ni
acredita todos los navegadores.

## 9. Evidencia Git

Commits técnicos:

- `2e1c520e7cd51e57937d16b1321410c9ca8584ac`
- `3520ddd797685773e3148932eb6b4bb1a70f2a3c`

Al preparar las evidencias, `master` y `origin/master` apuntaban a
`39733400b7cf6b353afc2d00dcc7aa9ff90d99de`, sin cambios rastreados ni staging.
La carpeta `docs/presentacion_segundo_parcial/` permaneció sin rastrear y
protegida.

## 10. Evidencias visuales completadas

El [inventario de evidencias](evidencias_visuales/inventario_evidencias.md)
documenta estado, resultado, limitación y requerimientos relacionados.

| ID | Evidencia | Estado |
|---|---|---|
| E-11-01 | [Login web](evidencias_visuales/E-11-01_login_web.png) | Completada |
| E-11-01B | [Error de credenciales](evidencias_visuales/E-11-01B_login_error_credenciales.png) | Completada con observación |
| E-11-02 | [Dashboard de administrador](evidencias_visuales/E-11-02_dashboard_administrador.png) | Completada |
| E-11-03A | [Listado vacío](evidencias_visuales/E-11-03A_listado_vacio.png) | Completada como caso límite |
| E-11-03B | [Listado con alumnos](evidencias_visuales/E-11-03B_listado_con_alumnos.png) | Completada |
| E-11-04 | [Dashboard de escáner](evidencias_visuales/E-11-04_dashboard_escaner.png) | Completada |
| E-11-05 | [Error 403](evidencias_visuales/E-11-05_error_403.png) | Completada |
| E-11-06 | [Error 404](evidencias_visuales/E-11-06_error_404.png) | Completada |
| E-11-07 | [Vista responsiva](evidencias_visuales/E-11-07_vista_responsive.png) | Completada |
| E-11-08 | [Suite de 172 pruebas](evidencias_visuales/E-11-08_pruebas_172_ok.png) | Completada con observación |
| E-11-09 | [Historial y estado Git](evidencias_visuales/E-11-09_commits_git.png) | Completada con observación |
| E-11-10 | [GitHub actualizado](evidencias_visuales/E-11-10_github_actualizado.png) | Completada |

### Datos ficticios y privacidad

- Usuarios: `Administrador Demo` y `Personal de Escaneo`.
- Alumnos: `Ana López Demo` (`DEMO001`, activo) y `Carlos Pérez Demo`
  (`DEMO002`, inactivo).
- E-11-03A utilizó una SQLite temporal aislada para no borrar registros.
- E-11-03B ocultó en el navegador filas preexistentes antes de la captura; la
  base local no fue alterada para proteger información ajena a la demostración.
- Ninguna captura contiene contraseña, `SECRET_KEY`, fotografía, ruta de
  fotografía o datos personales reales.
- E-11-10 fue recortada únicamente para retirar información pública
  irrelevante de la barra lateral.

La ejecución mostrada en E-11-08 terminó con:

```text
Ran 172 tests in 21.643s
OK
```

Windows no expuso una ventana de consola capturable en esta sesión. Para E-11-08
y E-11-09 se guardó la salida real en archivos temporales, se abrió en Chrome y
se capturó sin modificar el contenido. Los registros temporales se eliminaron.

QR, movimientos e historial continúan pendientes para Semana 12 conforme al
alcance aprobado. Su ausencia no representa un incumplimiento de Semana 11.
