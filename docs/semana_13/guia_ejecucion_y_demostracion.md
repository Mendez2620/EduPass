# Guía de ejecución y demostración de EduPass

## 1. Requisitos

- Windows con PowerShell.
- Python compatible con las versiones declaradas en `requirements.txt`.
- Git para verificar el estado del proyecto.
- Navegador moderno para la interfaz Flask.
- Microsoft Visual C++ y requisitos propios de PySide6 cuando se use la interfaz de escritorio.
- Cámara disponible sólo para la prueba física opcional.
- Datos completamente ficticios.

Ejecuta todos los comandos desde la raíz del repositorio.

## 2. Instalación

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH="src"
```

Las dependencias declaradas son PySide6, Flask, Flask-Login, Flask-WTF y qrcode. SQLite se incluye mediante la biblioteca estándar de Python. ZXing Browser ya está incorporado como recurso estático local y no requiere instalar Node.js.

## 3. Variables de entorno

El proyecto no carga `.env` automáticamente. `.env.example` es sólo una referencia; configura las variables en la sesión de PowerShell.

```powershell
$env:PYTHONPATH="src"
$env:EDUPASS_SECRET_KEY="<valor-local-privado>"
$env:EDUPASS_DATABASE_PATH="data\edupass.sqlite"
$env:EDUPASS_SESSION_MINUTES="30"
$env:EDUPASS_HOST="127.0.0.1"
$env:EDUPASS_PORT="5000"
$env:EDUPASS_HTTPS_MODE="off"
```

Sustituye el marcador de la clave por un valor privado. No lo uses literalmente, no lo guardes en documentación y no versiones un archivo `.env` real.

Variables condicionales de modo directo:

```powershell
$env:EDUPASS_SSL_CERT="<ruta-externa-certificado>"
$env:EDUPASS_SSL_KEY="<ruta-externa-clave>"
```

## 4. Creación del primer administrador

```powershell
$env:PYTHONPATH="src"
python scripts\create_demo_user.py
```

Selecciona el rol `administrador`. El script solicita la contraseña sin mostrarla y sólo admite `administrador` o `escaner`. No crea alumnos ni cuentas alumno.

Para la demostración usa una contraseña temporal privada que no aparezca en capturas, terminales compartidas ni archivos. Las cuentas alumno se crean posteriormente desde el panel administrativo.

## 5. Modo HTTP local

```powershell
$env:PYTHONPATH="src"
$env:EDUPASS_SECRET_KEY="<valor-local-privado>"
$env:EDUPASS_DATABASE_PATH="data\edupass.sqlite"
$env:EDUPASS_HTTPS_MODE="off"
$env:EDUPASS_HOST="127.0.0.1"
$env:EDUPASS_PORT="5000"
python -m edupass.web
```

Abre `http://127.0.0.1:5000` únicamente en el equipo local. Este modo conserva el comportamiento HTTP histórico, no utiliza `ProxyFix` y no marca las cookies como `Secure`.

## 6. Modo HTTPS proxy con VS Code

Configura y arranca Flask:

```powershell
$env:PYTHONPATH="src"
$env:EDUPASS_SECRET_KEY="<valor-local-privado>"
$env:EDUPASS_DATABASE_PATH="data\edupass.sqlite"
$env:EDUPASS_HTTPS_MODE="proxy"
$env:EDUPASS_HOST="127.0.0.1"
$env:EDUPASS_PORT="5000"
python -m edupass.web
```

Después:

1. Abre la vista **Ports** de VS Code.
2. Selecciona **Forward a Port**.
3. Indica el puerto `5000`.
4. Conserva visibilidad **Private** siempre que sea posible.
5. Abre desde el dispositivo la dirección HTTPS generada por VS Code.
6. Si la demostración exige visibilidad **Public**, úsala sólo temporalmente y con datos ficticios.
7. Cierra el túnel al terminar.

En este modo Flask escucha por HTTP en `127.0.0.1`; el navegador recibe HTTPS desde el proxy. No registres una URL temporal en documentación o evidencias.

## 7. Modo HTTPS directo

```powershell
$env:PYTHONPATH="src"
$env:EDUPASS_SECRET_KEY="<valor-local-privado>"
$env:EDUPASS_DATABASE_PATH="data\edupass.sqlite"
$env:EDUPASS_HTTPS_MODE="direct"
$env:EDUPASS_HOST="127.0.0.1"
$env:EDUPASS_PORT="5000"
$env:EDUPASS_SSL_CERT="<ruta-externa-certificado>"
$env:EDUPASS_SSL_KEY="<ruta-externa-clave>"
python -m edupass.web
```

El certificado y la clave deben existir fuera del repositorio. EduPass no los genera, no usa `adhoc` y no vuelve silenciosamente a HTTP. El navegador o dispositivo debe confiar en el certificado. Este modo está cubierto por pruebas automatizadas, pero no se declara una ejecución real validada con certificados externos.

## 8. Preparación de datos ficticios

Orden recomendado:

1. Crear el primer administrador con el script interactivo.
2. Iniciar la aplicación web.
3. Registrar alumnos ficticios desde `/admin/alumnos`.
4. Crear una cuenta de escáner desde `/admin/escaneres`.
5. Crear una cuenta alumno desde `/admin/cuentas-alumnos` y vincularla a un alumno activo.
6. Cerrar sesión e iniciar sesión por separado en cada perfil.

No reutilices correos, matrículas, fotografías ni contraseñas de personas reales. Antes de demostrar movimientos, prepara al menos dos alumnos ficticios para comprobar también el aislamiento.

## 9. Demostración del administrador

- [ ] Iniciar sesión como administrador.
- [ ] Registrar un alumno ficticio.
- [ ] Editar datos escolares sin cambiar el estado indebidamente.
- [ ] Desactivar y reactivar el alumno mediante `POST`.
- [ ] Crear y editar un administrador.
- [ ] Comprobar la protección del último administrador activo.
- [ ] Crear y editar una cuenta escáner.
- [ ] Crear una cuenta alumno vinculada.
- [ ] Confirmar que el correo y la contraseña se editan por flujos separados.
- [ ] Generar y renovar una credencial administrativa.
- [ ] Consultar historial vacío, historial con registros y detalle.
- [ ] Confirmar que no existen acciones de eliminación física o desvinculación.

## 10. Demostración del escáner

- [ ] Iniciar sesión como escáner.
- [ ] Abrir **Escanear o registrar movimiento**.
- [ ] Confirmar que existe selector de Entrada/Salida.
- [ ] Activar la cámara sólo mediante el botón.
- [ ] Comprobar que detectar un QR llena el campo sin enviar el formulario.
- [ ] Confirmar manualmente el movimiento.
- [ ] Repetir el flujo mediante captura manual como respaldo.
- [ ] Registrar una entrada válida.
- [ ] Intentar una segunda entrada consecutiva y confirmar el rechazo.
- [ ] Verificar que el QR de un solo uso no puede reutilizarse tras un movimiento válido.
- [ ] Generar otro QR y registrar la salida.
- [ ] Cancelar la cámara y comprobar que los tracks se detienen.

## 11. Demostración del alumno

- [ ] Iniciar sesión con una cuenta alumno activa y vinculada.
- [ ] Confirmar redirección al panel personal.
- [ ] Revisar perfil y aviso de datos de sólo lectura.
- [ ] Generar una credencial QR propia.
- [ ] Renovarla y confirmar que el QR anterior queda invalidado.
- [ ] Consultar historial propio y detalle.
- [ ] Confirmar que no existe selector de alumno.
- [ ] Intentar agregar `alumno_id` a la query y confirmar que la identidad no cambia.
- [ ] Intentar abrir el movimiento de otro alumno y confirmar 404 genérico.
- [ ] Confirmar respuestas 403 en rutas administrativas y del escáner.
- [ ] Cerrar sesión mediante el formulario `POST`.

## 12. Prueba física con teléfono

Esta validación permanece pendiente. No marques las casillas hasta realizarla realmente:

- [ ] Iniciar EduPass en modo `proxy`.
- [ ] Reenviar el puerto 5000 desde **Ports**.
- [ ] Abrir la dirección HTTPS en el teléfono.
- [ ] Iniciar sesión como escáner.
- [ ] Conceder permiso de cámara.
- [ ] Confirmar detección del QR.
- [ ] Confirmar que no hay envío automático.
- [ ] Seleccionar y confirmar el movimiento.
- [ ] Cancelar la cámara y comprobar su cierre.
- [ ] Repetir con permiso de cámara denegado.
- [ ] Verificar que la captura manual continúa disponible.
- [ ] Revisar el diseño móvil sin desbordamientos a un ancho aproximado de 390 px.
- [ ] Cerrar sesión, detener el servidor y cerrar el túnel.

## 13. Seguridad de la demostración

- Utiliza únicamente identidades, correos y matrículas ficticios.
- Usa contraseñas temporales privadas y no las muestres en pantalla.
- Prefiere un túnel privado.
- Habilita visibilidad pública sólo durante el tiempo imprescindible.
- No expongas la base persistente ni fotografías reales.
- No copies tokens QR, cookies o claves en notas o chats.
- Detén el servidor al terminar.
- Cierra el túnel y verifica que el puerto ya no está reenviado.
- Si utilizaste una base temporal, elimina sólo esa ruta exacta después de verificarla.

## 14. Ejecución de pruebas

```powershell
$env:PYTHONPATH="src"
python -m unittest discover -s tests -p "test_*.py"
```

Resultado de referencia aprobado:

```text
Ran 892 tests
OK
```

Las pruebas crean SQLite temporales y no deben modificar `data\edupass.sqlite`. No se declara porcentaje de cobertura. Las advertencias controladas de errores de repositorio simulados no son fallos si la salida final indica `OK`.

## 15. Limpieza

1. Cierra sesión en los perfiles usados.
2. Detén únicamente el proceso de EduPass iniciado para la demostración.
3. Verifica que el puerto 5000 ya no tiene listener.
4. Cierra el túnel de VS Code.
5. Elimina únicamente bases temporales creadas para la sesión.
6. No borres `data\edupass.sqlite` si se eligió persistencia local.
7. No uses `git clean`, comodines ni borrado recursivo sobre el repositorio.
8. Comprueba `git status --short`; los datos de ejecución no deben aparecer como archivos rastreados.

## 16. Solución de problemas

| Problema | Causa probable | Acción segura |
|---|---|---|
| Falta `SECRET_KEY` | No se configuró `EDUPASS_SECRET_KEY` fuera de pruebas. | Define un valor privado en la sesión y reinicia. |
| Puerto ocupado | Otro proceso escucha en el puerto seleccionado. | Identifica el proceso; cambia `EDUPASS_PORT` o detén sólo el proceso que controlas. |
| Cámara bloqueada por contexto inseguro | La página no usa HTTPS ni localhost. | Usa localhost o el modo proxy/direct correctamente configurado. |
| Permiso de cámara rechazado | El navegador o usuario denegó acceso. | Revisa permisos o utiliza captura manual. |
| Cámara no disponible | No existe dispositivo o API compatible. | Usa captura manual; no elimines ese respaldo. |
| Cuenta inactiva | El administrador desactivó el usuario. | Reactiva la cuenta desde el panel administrativo si corresponde. |
| Alumno inactivo | El registro escolar está desactivado. | Reactiva primero el alumno y luego la cuenta, con autorización administrativa. |
| Certificado inexistente | `EDUPASS_SSL_CERT` no apunta a un archivo. | Corrige la ruta externa; no guardes el certificado en el repositorio. |
| Clave inexistente | `EDUPASS_SSL_KEY` no apunta a un archivo. | Corrige la ruta externa; no uses fallback inseguro. |
| Túnel cerrado | El puerto reenviado dejó de estar disponible. | Vuelve a reenviar el puerto y usa la nueva dirección sin documentarla. |