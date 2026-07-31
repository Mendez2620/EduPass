# Limitaciones y pendientes

## Terminados técnicamente en Etapa B

- registro transaccional de entrada;
- registro transaccional de salida;
- reglas de secuencia histórica;
- consumo QR y movimiento con commit único o rollback total;
- concurrencia controlada sobre el mismo QR;
- integración web del escáner;
- historial administrativo por alumno;
- estado vacío y paginación de 50;
- detalle de movimiento con prevención de IDOR;
- navegación, mensajes y presentación responsive;
- suite completa de 484 pruebas.

## Limitaciones actuales

1. La credencial continúa disponible únicamente en sesión administrativa.
2. La captura del token es manual.
3. La cámara no está implementada.
4. Los intentos rechazados no se persisten.
5. Área y dispositivo permanecen nulos en los movimientos.
6. SQLite no es una solución de producción multiusuario.
7. HTTP local se usa únicamente para el prototipo.
8. No se midió porcentaje de cobertura.
9. Las catorce evidencias visuales definitivas de Etapa B están capturadas y
   validadas en su inventario.
10. El commit documental y el push siguen pendientes.

## Siguiente incremento

- CRUD web de alumnos;
- CRUD web de administradores;
- CRUD web de escáneres;
- creación web controlada de cuentas;
- definición de vinculación entre usuario y alumno.

Estas funciones no forman parte de la implementación técnica cerrada en los dos
commits de Etapa B.

## Semana 13

- rol alumno;
- panel personal del alumno;
- historial personal;
- revisión del flujo de vinculación usuario-alumno;
- cierre adicional de documentación y operación aprobado para esa semana.

La planificación definitiva de Semana 13 debe respetar el alcance que se
apruebe antes de iniciar implementación.

## Mejoras futuras

- cámara;
- persistencia de intentos rechazados;
- HTTPS productivo;
- rate limiting distribuido;
- multiinstitución;
- tutores;
- notificaciones;
- áreas internas funcionales;
- dispositivos fijos funcionales;
- reportes;
- exportación;
- aplicación móvil;
- despliegue público.

EduPass 1.0 no debe considerarse completamente cerrado mientras sigan
pendientes el alcance administrativo adicional, el rol alumno y el cierre
aprobado de Semana 13.
