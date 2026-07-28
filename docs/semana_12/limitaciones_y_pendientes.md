# Limitaciones y pendientes

## Limitaciones actuales

1. La credencial está disponible únicamente en una sesión administrativa.
2. El alumno no tiene cuenta propia.
3. No existe URL pública de credencial.
4. No existe captura por cámara.
5. La captura manual del token es obligatoria.
6. La validación no registra movimientos.
7. No existe historial funcional.
8. Los intentos rechazados no se persisten en esta etapa.
9. No existe limpieza física automática de tokens antiguos.
10. SQLite no es una solución de producción multiusuario.
11. La renovación automática depende de JavaScript.
12. El backend sigue siendo la autoridad del tiempo y del estado.
13. El token original no puede recuperarse desde su hash.
14. Un token mostrado existe solo en la respuesta inmediata de generación.
15. HTTP local se usa únicamente para el prototipo.
16. HTTPS es obligatorio antes de un despliegue real.
17. El rate limiting distribuido queda pendiente.
18. No se midió porcentaje de cobertura.
19. Las evidencias visuales finales quedan para un cierre separado.
20. La Etapa B está pendiente.

## Alcance propuesto para Etapa B

La siguiente etapa deberá diseñar y probar, sin ampliar el MVP:

- registro de entrada;
- registro de salida;
- asociación del movimiento con alumno y usuario responsable;
- consistencia de la secuencia de movimientos;
- historial básico en pantalla;
- coordinación transaccional entre consumo QR y registro del movimiento.

La Etapa B deberá definir qué ocurre si el token se consume pero el movimiento no
puede persistirse. No debe iniciarse hasta aprobar su contrato transaccional,
criterios de aceptación y pruebas de regresión.
