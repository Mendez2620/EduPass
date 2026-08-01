# EduPass

## Descripción

EduPass es un sistema académico de control escolar desarrollado en Python como prototipo local para una sola institución. Integra una aplicación web Flask, la interfaz administrativa de escritorio PySide6 conservada, persistencia SQLite, credenciales QR temporales y registro de entradas y salidas. Su arquitectura modular separa interfaces, servicios, repositorios, SQL externo y administración de la base de datos.

El proyecto sirve para desarrollo, pruebas y demostración académica. No se presenta como sistema productivo ni como despliegue final.

## Estado actual

Al cierre técnico de Semana 13 están implementados y probados:

- persistencia SQLite e inicialización idempotente;
- CRUD de alumnos en PySide6 y en la web;
- CRUD web de administradores y escáneres;
- cuentas alumno vinculadas uno a uno con alumnos existentes;
- autenticación y navegación separadas para `administrador`, `escaner` y `alumno`;
- credencial QR temporal, renovación, vigencia de 30 segundos y uso único;
- movimientos transaccionales de entrada y salida;
- historial administrativo y personal con detalle y paginación;
- captura de QR mediante cámara y alternativa manual;
- modos HTTPS `off`, `proxy` y `direct`;
- portal personal del alumno;
- 892 pruebas automatizadas en estado `OK`.

La existencia de tablas estructurales no implica que todos sus dominios sean funcionales. No están implementados notificaciones push, un flujo completo de tutores, áreas o dispositivos, intentos rechazados persistentes, aplicación móvil nativa, operación offline, reportes exportables, multiinstitución ni despliegue productivo.

## Roles

| Rol | Funciones autorizadas |
|---|---|
| Administrador | Administrar alumnos, administradores, escáneres y cuentas alumno; generar credenciales administrativas; consultar historial administrativo. |
| Escáner | Registrar movimientos, capturar QR mediante cámara y utilizar la captura manual. |
| Alumno | Consultar su perfil, generar o renovar su credencial y consultar exclusivamente su historial y sus detalles. |

Las rutas validan el nombre del rol en el servidor. El portal del alumno resuelve su identidad desde la sesión y el vínculo `usuario_alumno`; no acepta un `alumno_id` del navegador para decidir qué alumno consultar. Las comprobaciones de pertenencia devuelven un 404 genérico para movimientos ajenos o inexistentes, evitando revelar datos mediante IDOR.

## Flujo funcional

1. El administrador registra un alumno.
2. El administrador crea una cuenta vinculada al alumno.
3. El alumno inicia sesión y accede a su panel personal.
4. El alumno genera un QR opaco con vigencia de 30 segundos.
5. El escáner selecciona **Entrada** o **Salida**.
6. El escáner captura el QR mediante cámara o pega el token en el campo manual.
7. El operador confirma explícitamente el movimiento.
8. El backend valida rol, alumno, QR y secuencia, y registra consumo y movimiento en una transacción.
9. El alumno y el administrador consultan el historial de acuerdo con sus permisos.

## Arquitectura

```text
Interfaz PySide6             Interfaz web Flask
        \                         /
         \                       /
          +---- Servicios de dominio ----+
          | alumnos                      |
          | auth                         |
          | credencial_qr                |
          | movimientos                  |
          | historial                    |
          | cuentas alumno               |
          | portal alumno                |
          +---------------+--------------+
                          |
                    Repositorios
                          |
                SQL externo parametrizado
                          |
                   DatabaseManager
                          |
                        SQLite
```

- Las interfaces capturan solicitudes y presentan resultados.
- Las rutas Flask no ejecutan SQL directamente.
- Los servicios validan datos y aplican reglas de negocio.
- Los repositorios controlan conexiones, cursores y transacciones.
- Las consultas se almacenan en archivos SQL externos y reciben parámetros por separado.
- `DatabaseManager` inicializa el esquema y activa llaves foráneas por conexión.

## Seguridad

El cierre técnico incorpora:

- contraseñas almacenadas mediante hash de Werkzeug;
- mensajes genéricos de autenticación;
- protección CSRF con Flask-WTF;
- logout únicamente por `POST`;
- autorización y navegación separadas por rol;
- recarga de usuarios de sesión desde SQLite;
- invalidación de la sesión del alumno si su cuenta, alumno, vínculo o rol dejan de ser válidos;
- prevención de IDOR en el portal y los detalles;
- SQL parametrizado y capas sin conexión global;
- tokens QR opacos y persistencia exclusiva de SHA-256;
- vigencia de 30 segundos, renovación e invalidación y uso único;
- transacción única para consumir QR y registrar movimiento;
- respuestas sensibles con `Cache-Control: no-store`;
- CSP específica en la credencial del alumno;
- cookies `Secure` en modos `proxy` y `direct`;
- `ProxyFix` únicamente en modo `proxy`, confiando un encabezado de protocolo y uno de host;
- certificados externos obligatorios en modo `direct`;
- cámara sin micrófono y con cámara trasera preferida;
- detección de QR sin envío automático: el operador debe confirmar.

Estas medidas forman parte de una auditoría técnica interna del prototipo; no equivalen a una auditoría profesional externa ni garantizan ausencia absoluta de vulnerabilidades.

## Instalación

Se requiere una versión de Python compatible con las dependencias declaradas. El entorno de desarrollo registrado utiliza Python 3.12.1. Las versiones aplicativas se encuentran fijadas en `requirements.txt`: PySide6, Flask, Flask-Login, Flask-WTF y qrcode.

Desde la raíz del repositorio:

```powershell
python -m pip install -r requirements.txt
```

SQLite se utiliza mediante `sqlite3`, incluido en la biblioteca estándar de Python.

## Configuración

`.env.example` es únicamente una referencia. El proyecto no carga archivos `.env` automáticamente: las variables deben configurarse en la sesión del proceso. Un archivo `.env` real, claves, certificados y otros secretos no deben versionarse.

| Variable | Propósito | Valor esperado | Requisito |
|---|---|---|---|
| `EDUPASS_SECRET_KEY` | Firma de sesión y CSRF. | Valor privado y no versionado. | Obligatoria fuera de pruebas. |
| `EDUPASS_DATABASE_PATH` | Ruta de SQLite. | Por ejemplo, `data\edupass.sqlite`. | Opcional; tiene ruta local predeterminada. |
| `EDUPASS_SESSION_MINUTES` | Duración de la sesión permanente. | Entero positivo; referencia: `30`. | Opcional. |
| `EDUPASS_HOST` | Interfaz de escucha. | Host válido; en proxy debe ser `127.0.0.1` o `localhost`. | Opcional. |
| `EDUPASS_PORT` | Puerto web. | Entero entre 1 y 65535. | Opcional. |
| `EDUPASS_HTTPS_MODE` | Modo de transporte. | `off`, `proxy` o `direct`. | Opcional; predeterminado `off`. |
| `EDUPASS_SSL_CERT` | Certificado para HTTPS directo. | Ruta a un archivo externo existente. | Obligatoria sólo en `direct`. |
| `EDUPASS_SSL_KEY` | Clave privada para HTTPS directo. | Ruta a un archivo externo existente. | Obligatoria sólo en `direct`. |

## Creación inicial de usuarios

```powershell
$env:PYTHONPATH="src"
python scripts\create_demo_user.py
```

El script solicita la contraseña sin mostrarla y sólo permite crear administradores o escáneres. No crea alumnos ni cuentas alumno. Las cuentas alumno deben crearse desde el panel administrativo y quedar vinculadas a un alumno existente.

## Ejecución web

### Modo HTTP local

```powershell
$env:PYTHONPATH="src"
$env:EDUPASS_SECRET_KEY="<valor-local-privado>"
$env:EDUPASS_DATABASE_PATH="data\edupass.sqlite"
$env:EDUPASS_HTTPS_MODE="off"
$env:EDUPASS_HOST="127.0.0.1"
$env:EDUPASS_PORT="5000"
python -m edupass.web
```

`<valor-local-privado>` es un marcador: debe sustituirse por una clave privada y nunca debe usarse literalmente ni versionarse.

### HTTPS proxy con VS Code

```powershell
$env:EDUPASS_HTTPS_MODE="proxy"
$env:EDUPASS_HOST="127.0.0.1"
$env:EDUPASS_PORT="5000"
python -m edupass.web
```

Después:

1. Abrir la vista **Ports** de VS Code.
2. Reenviar el puerto 5000.
3. Abrir la dirección HTTPS generada.
4. Preferir visibilidad **Private**.
5. Usar **Public** sólo temporalmente y con datos ficticios.
6. Cerrar el túnel al terminar.

Flask continúa escuchando mediante HTTP local y el navegador accede por HTTPS externo. Este modo está destinado a pruebas y demostración. La evidencia física final con teléfono y un túnel real sigue pendiente; no se documenta ninguna URL temporal concreta.

### HTTPS directo

```powershell
$env:EDUPASS_HTTPS_MODE="direct"
$env:EDUPASS_SSL_CERT="<ruta-externa-certificado>"
$env:EDUPASS_SSL_KEY="<ruta-externa-clave>"
python -m edupass.web
```

EduPass no genera certificados ni usa un certificado `adhoc`. Los archivos deben existir fuera del repositorio y el dispositivo cliente debe confiar en el certificado. La ejecución real con certificados externos no se declara validada todavía; si falta cualquiera de los archivos, el arranque termina con un error controlado y no utiliza un fallback HTTP.

## Cámara QR

La captura utiliza `@zxing/browser` 0.2.1 servido localmente con licencia MIT, sin CDN. Los checksums verificables están registrados en `src/edupass/web/static/vendor/zxing-browser/0.2.1/VENDOR.md`.

La cámara requiere interacción del operador, permiso del navegador y un contexto seguro. Solicita video sin audio, prefiere la cámara trasera, copia un token válido al campo y detiene los tracks. La detección no envía el formulario: el operador selecciona el movimiento y confirma. La captura manual permanece disponible.

## Interfaz de escritorio

```powershell
$env:PYTHONPATH="src"
python -m edupass.main
```

La interfaz PySide6 continúa disponible para administrar alumnos. No contiene los tres portales web; la aplicación Flask es la interfaz completa separada por roles.

## Pruebas

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -p "test_*.py"
```

Resultado aprobado al cierre de Semana 13:

```text
Ran 892 tests
OK
```

Las pruebas usan SQLite temporal y no emplean `data/edupass.sqlite` como base de prueba. Una prueba observa únicamente sus metadatos para confirmar que no cambian. No se ejecutó una herramienta de cobertura y no se declara porcentaje. Durante la auditoría integral se observaron 22 advertencias de logger provocadas por errores de repositorio simulados; fueron casos controlados, no fallos.

## Demostración por consola

```powershell
$env:PYTHONPATH="src"
python scripts\demo_alumnos.py
```

La demostración de alumnos utiliza SQLite temporal, valida el CRUD de ese módulo y elimina automáticamente su base al finalizar.

## Limitaciones

- Es un prototipo académico, no una aplicación productiva.
- El servidor de desarrollo de Flask no debe utilizarse como servidor de producción.
- SQLite no está planteado para alta concurrencia productiva.
- La prueba con teléfono y túnel HTTPS requiere evidencia física final.
- HTTPS directo requiere certificados externos y aún no tiene validación real reportada.
- Los intentos rechazados no se persisten; sólo existe su tabla estructural.
- Las notificaciones push no están implementadas.
- Tutores, áreas y dispositivos no tienen un flujo funcional completo.
- No existe aplicación móvil nativa, modo offline ni despliegue productivo.
- No se utilizan datos reales en las demostraciones aprobadas.
- No se declara compatibilidad con todos los dispositivos ni validación pixel-perfect.

## Trabajo futuro

- Persistencia controlada de intentos rechazados.
- Notificaciones y flujo funcional de tutores.
- Administración completa de áreas y dispositivos.
- Servidor web de producción y estrategia formal de migraciones.
- Despliegue controlado y endurecimiento operativo.
- Pruebas físicas en más dispositivos y navegadores.
- Empaquetado de recursos y distribución.

## Commits de Semana 13

| Orden | SHA | Mensaje |
|---:|---|---|
| 1 | `a65685f7c4dc` | `feat: agregar CRUD web seguro de alumnos` |
| 2 | `9f597fdf054d` | `feat: agregar CRUD web seguro de administradores` |
| 3 | `24969e3e27f4` | `feat: agregar CRUD web seguro de escaneres` |
| 4 | `957dcb6fbc82` | `feat: integrar camara QR y modos HTTPS` |
| 5 | `b113c37dc14c` | `feat: agregar rol y vinculacion segura de alumnos` |
| 6 | `2ec44848b7fd` | `feat: agregar administracion de cuentas de alumnos` |
| 7 | `87eef8552768` | `feat: agregar portal personal seguro del alumno` |

## Resultado

La auditoría integral de Semana 13 obtuvo la clasificación **A. APROBADO** con 892 pruebas en estado `OK` y sin bloqueadores funcionales. El proyecto puede pasar a documentación y preparación de publicación. Permanecen pendientes la evidencia física con teléfono, el cierre documental y la publicación final.