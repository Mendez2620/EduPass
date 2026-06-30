# Decision de persistencia

EduPass requiere persistencia de datos porque debe conservar informacion escolar e historial de movimientos despues de cerrar el programa.

La opcion seleccionada para la primera version academica es SQLite. Esta decision mantiene el proyecto simple, evita depender de un servidor externo y permite manejar relaciones basicas entre alumnos, tutores, usuarios, areas, dispositivos, movimientos, notificaciones e intentos rechazados.

El modulo responsable sera `persistence/database_manager.py`.

