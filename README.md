# EduPass

EduPass es una utileria academica de control escolar para registrar entradas, salidas y movimientos relevantes de alumnos mediante una credencial digital con codigo QR temporal.

## Alcance del MVP

- Una sola escuela.
- QR temporal de 30 segundos.
- QR de un solo uso.
- Validacion en linea.
- Notificaciones push.
- Consulta en pantalla de historial.
- Sin transporte escolar, pagos, calificaciones, reconocimiento facial, geolocalizacion en tiempo real, modo offline avanzado, exportacion de reportes ni multiinstitucion.

## Decision de persistencia

EduPass requiere guardar informacion despues de cerrar el programa: alumnos, tutores, usuarios, roles, dispositivos fijos, areas internas, movimientos, notificaciones push, historial e intentos de escaneo rechazados.

Para una primera version academica se usara SQLite por ser simple, local y suficiente para un MVP de una sola escuela.

## Primer modulo a implementar

El primer modulo a implementar sera `persistence/database_manager.py`, responsable de preparar la conexion a SQLite e inicializar el esquema definido en `schema.sql`.

## Ejecucion del primer modulo

Para inicializar la base de datos local y crear las tablas definidas en `schema.sql`, ejecuta:

```powershell
python src\edupass\persistence\database_manager.py
```

El archivo `data/edupass.sqlite` se genera automaticamente al ejecutar `database_manager.py`. Este archivo no se sube al repositorio porque esta ignorado en `.gitignore`.

Para ejecutar la prueba basica del modulo de persistencia:

```powershell
python -m unittest tests\test_database_manager.py
```

## Pruebas unitarias

Las pruebas actuales corresponden al modulo `src/edupass/persistence/database_manager.py` y usan `unittest`.

Para ejecutarlas:

```powershell
python -m unittest tests\test_database_manager.py
```

Las pruebas usan una base temporal de prueba dentro de `.test_tmp/` y no modifican `data/edupass.sqlite`.

Actualmente validan la creacion de la base SQLite, las tablas esperadas, el caso limite de doble inicializacion, el error por `schema.sql` faltante y columnas o restricciones relacionadas con RF-02, RF-33, RF-44 y RF-50.


