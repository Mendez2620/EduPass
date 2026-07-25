# EduPass

EduPass es un proyecto académico de control escolar desarrollado en Python con una arquitectura modular. Su objetivo general es administrar alumnos, credenciales QR, accesos, movimientos y notificaciones. En el avance actual se implementaron la persistencia SQLite, el módulo administrativo de alumnos, la autenticación modular y una interfaz web inicial; el sistema completo aún no está terminado.

## Alcance del MVP

- Una sola escuela.
- QR temporal de 30 segundos y de un solo uso.
- Validación en línea.
- Notificaciones push.
- Consulta en pantalla del historial.
- Sin transporte escolar, pagos, calificaciones, reconocimiento facial, geolocalización en tiempo real, modo offline avanzado, exportación de reportes ni multiinstitución.

Los puntos anteriores describen el alcance general planeado. En el corte actual están implementados la persistencia inicial, el módulo administrativo de alumnos, la autenticación por rol y el primer incremento web.

## Estado actual del desarrollo

Hasta la Semana 11 se encuentran implementados y comprobados:

- inicialización de SQLite mediante `database_manager.py` y `schema.sql`;
- repositorio del módulo de alumnos;
- consultas SQL externas y parametrizadas;
- servicio de alumnos con validación y normalización;
- pruebas automatizadas con `unittest`;
- demostración funcional por consola;
- prototipo administrativo de escritorio con PySide6 y Qt Designer;
- persistencia local de alumnos comprobada entre ejecuciones.
- autenticación modular para administrador y personal de escaneo;
- sesiones web con Flask-Login y protección CSRF con Flask-WTF;
- panel web administrativo y listado de alumnos de solo lectura;
- panel de escaneo que identifica honestamente el trabajo pendiente.

No se consideran implementados todavía QR, tutores, movimientos, notificaciones, áreas, dispositivos, historial completo ni auditoría funcional. Los archivos base de esos módulos son únicamente placeholders de la estructura modular.

## Evolución por semanas

### Semanas 7 y 8: persistencia inicial

El primer módulo implementado fue `src/edupass/persistence/database_manager.py`. Se eligió para preparar la conexión SQLite, aplicar el esquema definido en `schema.sql` y proporcionar la base técnica para los módulos posteriores.

Para inicializar o verificar manualmente la base local:

```powershell
python src\edupass\persistence\database_manager.py
```

El archivo `data/edupass.sqlite` se genera automáticamente y está ignorado por Git. Durante la Semana 8 se añadieron nueve pruebas unitarias de inicialización, tablas, restricciones y manejo de errores del esquema.

### Semana 9: módulo funcional de alumnos

El avance integra repositorio, SQL externo, servicio, demostración por consola e interfaz gráfica para registrar, consultar, editar, activar y desactivar alumnos. También se comprobó manualmente la persistencia entre cierres de la aplicación.

### Semanas 10 y 11: autenticación y web inicial

La autenticación modular permite crear cuentas de demostración con contraseñas hasheadas, autenticar usuarios activos y validar los roles `administrador` y `escaner`. La interfaz web reutiliza esos servicios, agrega sesiones, CSRF, separación estricta por rol y un listado administrativo de alumnos de solo lectura.

La interfaz PySide6 continúa disponible para el módulo administrativo de escritorio. La interfaz web es un cliente separado para navegación desde un navegador moderno; ambas reutilizan servicios existentes y ninguna reemplaza las reglas de negocio.

## Prototipo de escritorio con PySide6

Durante la Semana 9 se desarrolló una interfaz de escritorio con Python, PySide6, Qt Designer y SQLite como prototipo funcional del panel administrativo de alumnos. Su finalidad es integrar, demostrar y validar visualmente el módulo actual.

Esta pantalla no constituye la interfaz definitiva de todos los usuarios ni redefine EduPass como una aplicación exclusivamente de escritorio. La compatibilidad con navegadores, dispositivos móviles, tablets y diseños adaptables continúa pendiente. En particular, la interfaz actual no acredita todavía los requerimientos no funcionales de compatibilidad web o móvil.

La separación entre interfaz, servicio y persistencia permite reemplazar o complementar la interfaz de escritorio con clientes web o móviles sin reescribir por completo las reglas de negocio.

## Requerimientos funcionales implementados

- **RF-01 - Registrar alumnos:** guarda nombre, matrícula, grado, grupo, fotografía opcional y estado.
- **RF-02 - Impedir matrículas duplicadas:** elimina espacios externos, convierte la matrícula a mayúsculas, realiza una comprobación previa y utiliza una restricción `UNIQUE` en SQLite.
- **RF-03 - Editar alumnos:** actualiza nombre, matrícula, grado, grupo y fotografía, conservando el estado durante la edición.
- **RF-04 - Activar o desactivar alumnos:** cambia el estado entre `activo` e `inactivo` mediante operaciones idempotentes y persistentes.

Estos requerimientos corresponden únicamente al módulo implementado en este corte.

## Arquitectura

```text
Interfaz PySide6 / Script de demostración / Pruebas
                         |
                         v
                alumnos_service.py
                         |
                         v
                alumno_repository.py
                         |
                         v
        archivos SQL externos parametrizados
                         |
                         v
                database_manager.py
                         |
                         v
                       SQLite
```

- **Interfaz:** captura datos y muestra resultados; no contiene SQL ni reglas de negocio.
- **Servicio:** valida, normaliza, aplica reglas y traduce casos como alumnos inexistentes o matrículas duplicadas.
- **Repositorio:** ejecuta la persistencia, carga SQL externo, administra conexiones y transacciones y convierte filas en diccionarios.
- **Database manager:** inicializa SQLite, aplica `schema.sql` y proporciona conexiones.
- **Archivos SQL:** contienen consultas parametrizadas, sin datos concatenados ni SQL dinámico.
- **SQLite:** conserva localmente la información del prototipo.

La interfaz consume únicamente el servicio y no accede directamente al repositorio.

## SQL externo

Las consultas del módulo se encuentran en `src/edupass/persistence/sql/alumnos/`:

- `insert_alumno.sql`
- `select_alumno_by_id.sql`
- `select_alumno_by_matricula.sql`
- `exists_alumno_matricula.sql`
- `update_alumno.sql`
- `update_alumno_estado.sql`

Todas utilizan parámetros `?`, seleccionan columnas explícitas en lugar de `SELECT *` y reciben los valores por separado, sin concatenarlos en las consultas.

## Estructura relevante

```text
EduPass/
|-- README.md
|-- requirements.txt
|-- scripts/
|   `-- demo_alumnos.py
|-- src/
|   `-- edupass/
|       |-- main.py
|       |-- modules/
|       |   `-- alumnos/
|       |       `-- alumnos_service.py
|       |-- persistence/
|       |   |-- database_manager.py
|       |   |-- schema.sql
|       |   |-- repositories/
|       |   |   `-- alumno_repository.py
|       |   `-- sql/
|       |       `-- alumnos/
|       |           |-- exists_alumno_matricula.sql
|       |           |-- insert_alumno.sql
|       |           |-- select_alumno_by_id.sql
|       |           |-- select_alumno_by_matricula.sql
|       |           |-- update_alumno.sql
|       |           `-- update_alumno_estado.sql
|       |-- shared/
|       |   |-- constants.py
|       |   |-- errors.py
|       |   `-- validators.py
|       `-- ui/
|           |-- __init__.py
|           |-- alumnos_window.py
|           `-- alumnos_window.ui
`-- tests/
    |-- test_database_manager.py
    |-- test_alumno_repository.py
    `-- test_alumnos_service.py
```

Los demás módulos presentes en la estructura todavía no contienen implementaciones funcionales completas.

## Requisitos del entorno

- Entorno de desarrollo probado: Python 3.12.1.
- PySide6 6.11.1, declarado en `requirements.txt`.
- Flask 3.1.3, Flask-Login 0.6.3 y Flask-WTF 1.3.0.
- SQLite mediante el módulo `sqlite3` de la biblioteca estándar.
- No se requieren ORM ni servidores de base de datos externos.

El proyecto utiliza una disposición `src/`. Los comandos de demostración e interfaz requieren definir `PYTHONPATH` para la sesión actual de PowerShell:

```powershell
$env:PYTHONPATH="src"
```

Esto no modifica permanentemente la configuración del sistema.

## Instalación

Desde la raíz del repositorio:

```powershell
python -m pip install -r requirements.txt
```

## Ejecución de pruebas

Para ejecutar la suite completa:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Resultado comprobado en Semana 11:

```text
Ran 172 tests
OK
```

La suite conserva las 137 pruebas anteriores y agrega 35 pruebas web de fábrica, autenticación, roles y listado de alumnos. Algunos métodos emplean `subTest` para comprobar varios valores. Las pruebas utilizan bases SQLite temporales y aisladas; no modifican `data/edupass.sqlite`.

No existen pruebas gráficas permanentes en `tests/`. La interfaz fue revisada manualmente y mediante comprobaciones offscreen temporales.

## Demostración por consola

```powershell
$env:PYTHONPATH="src"
python scripts/demo_alumnos.py
```

La demostración utiliza una SQLite temporal y no modifica `data/edupass.sqlite`. Registra y consulta un alumno, normaliza la matrícula, rechaza duplicados, edita, desactiva y activa. Al finalizar elimina automáticamente la base temporal y devuelve código `0` cuando todas las operaciones son correctas.

## Interfaz gráfica

Desde la raíz del repositorio:

```powershell
$env:PYTHONPATH="src"
python -m edupass.main
```

El comando abre la ventana **Administración de alumnos**. La interfaz permite registrar, buscar por matrícula, editar, activar, desactivar y limpiar el formulario. Utiliza `data/edupass.sqlite`, la crea si no existe y conserva los alumnos entre ejecuciones. La base local está ignorada por Git.

## Interfaz web

Define las variables para la sesión actual de PowerShell. `EDUPASS_SECRET_KEY` es obligatoria y debe recibir un valor local privado; no se almacena en el repositorio.

```powershell
$env:PYTHONPATH="src"
$env:EDUPASS_SECRET_KEY="<valor-local-privado>"
$env:EDUPASS_DATABASE_PATH="data\edupass.sqlite"
$env:EDUPASS_SESSION_MINUTES="30"
$env:EDUPASS_HOST="127.0.0.1"
$env:EDUPASS_PORT="5000"
python -m edupass.web
```

El archivo `.env.example` documenta los nombres y valores no sensibles. El proyecto no carga archivos `.env` automáticamente y `.env` está ignorado por Git.

Antes de iniciar sesión se debe crear interactivamente al menos un usuario de demostración. El script solicita la contraseña sin mostrarla ni guardarla en archivos:

```powershell
$env:PYTHONPATH="src"
python scripts\create_demo_user.py
```

La web ofrece `/admin` y `/admin/alumnos` al rol administrador. El rol `escaner` recibe una vista de alcance pendiente en `/scanner`; todavía no existe cámara, captura de token ni validación QR.

## Uso de SQLite

Cada forma de ejecución mantiene un propósito distinto:

1. **Pruebas automatizadas:** bases temporales aisladas por prueba; no modifican la base local.
2. **Demostración por consola:** base temporal eliminada automáticamente al terminar.
3. **Interfaz gráfica y web local:** `data/edupass.sqlite`, persistente entre ejecuciones e ignorada por Git.

La base persistente no debe agregarse al repositorio.

## Casos demostrables

- Registro válido y fotografía opcional.
- Normalización y rechazo de matrícula duplicada.
- Consulta por ID y por matrícula.
- Edición con conservación del estado.
- Activación y desactivación idempotentes.
- Persistencia después de cerrar y reabrir la interfaz.
- Validación de campos obligatorios.
- Manejo de alumno inexistente y errores de persistencia.

## Limitaciones actuales

- Las interfaces PySide6 y web son prototipos académicos locales; no existe aplicación móvil ni publicación en Internet.
- La cookie `Secure` está desactivada para la demostración HTTP local y debe activarse bajo HTTPS.
- SQLite no se plantea como base de producción multiusuario.
- QR, tutores, movimientos de entrada y salida, notificaciones, áreas, dispositivos e historial permanecen sin implementar.
- La vista de escaneo no usa cámara ni simula validaciones.
- La demostración no utiliza datos personales reales.
- No existe carga ni vista previa real de fotografías.
- No existe empaquetado instalable; actualmente los comandos indicados requieren `PYTHONPATH=src`.
- Los archivos `.ui` y `.sql` deberán incluirse como datos del paquete cuando se implemente el empaquetado.
- Áreas, dispositivos, historial completo y auditoría funcional continúan pendientes.

Estas limitaciones corresponden al alcance del corte actual y no representan funciones declaradas como terminadas.

## Trabajo futuro

- Integrar credenciales QR temporales y validación en línea.
- Implementar movimientos y asociar tutores.
- Incorporar notificaciones push.

- Desarrollar clientes web o móviles y adaptar el panel a navegadores.
- Agregar historial y auditoría funcional.
- Preparar migraciones, empaquetado y distribución.
- Ampliar las pruebas automatizadas y de interfaz.

## Seguridad y separación de capas

- Las consultas usan parámetros y no concatenan datos proporcionados por usuarios.
- La interfaz, las reglas de negocio y la persistencia están separadas.
- Los detalles técnicos de errores no se presentan directamente al usuario de la interfaz.
- La interfaz no accede directamente al repositorio ni a SQLite.
- La base persistente no se versiona y las pruebas no la utilizan.

Estas medidas reducen riesgos en el prototipo, pero no equivalen a una auditoría de seguridad del sistema completo.

## Recomendaciones para colaboradores

- Ejecutar los comandos desde la raíz del repositorio.
- No versionar `data/edupass.sqlite`, cachés ni bases temporales.
- Mantener SQL, reglas de negocio e interfaz en sus capas correspondientes.
- Ejecutar la suite completa antes de registrar cambios.
