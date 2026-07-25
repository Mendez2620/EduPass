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

Esta evidencia no sustituye las capturas finales ni acredita todavía todos los
navegadores o tamaños de pantalla.

## 9. Evidencia Git

Commits técnicos:

- `2e1c520e7cd51e57937d16b1321410c9ca8584ac`
- `3520ddd797685773e3148932eb6b4bb1a70f2a3c`

Antes del cierre documental, `master` y `origin/master` apuntaban a
`3520ddd797685773e3148932eb6b4bb1a70f2a3c`, sin cambios rastreados ni staging.
La carpeta `docs/presentacion_segundo_parcial/` permanecía sin rastrear y
protegida. El commit de esta documentación será local y no se publicará, por lo
que el remoto conservará el SHA técnico anterior.

## 10. Evidencias visuales pendientes

No se crearon capturas en este cierre. Deben capturarse posteriormente:

1. Login.
2. Dashboard de administrador.
3. Listado de alumnos.
4. Dashboard de escáner.
5. Error 403.
6. Error 404.
7. Vista móvil.
8. Salida de 172 pruebas.
9. Historial de commits.
10. Repositorio GitHub actualizado.
