# Alcance de EduPass 1.0

## 1. Problema central

La escuela necesita registrar entradas y salidas importantes de alumnos con
evidencia consultable, reduciendo registros duplicados, inconsistentes o
realizados por personal no autorizado.

## 2. Objetivo

Entregar un flujo web pequeño y demostrable para una sola escuela: autenticar
al personal, presentar una credencial controlada, validar un QR temporal y de
un solo uso, registrar entradas o salidas del plantel y consultar un historial
básico.

## 3. Usuarios y roles

Los usuarios autenticados de EduPass 1.0 son:

- `administrador`: administra y consulta información autorizada.
- `escaner`: utiliza el flujo de validación y registro del punto de acceso.

El alumno es portador de una credencial digital controlada y no tiene una
cuenta completa. Se seleccionó la opción de dos roles autenticados y una vista
de credencial porque reduce cuentas, sesiones y superficies de autorización,
sin eliminar el flujo principal de demostración.

## 4. Flujo final previsto

1. Un administrador o usuario de escaneo inicia sesión.
2. El sistema valida credenciales, estado y rol.
3. Un alumno activo presenta su credencial controlada.
4. La credencial muestra un token QR que vence a los 30 segundos.
5. El personal captura manualmente el token o, de forma opcional, usa cámara.
6. El sistema comprueba alumno activo, token existente, vigencia y uso único.
7. Se registra una entrada o salida válida, o se informa el rechazo.
8. El administrador consulta el historial básico.
9. SQLite conserva los datos entre ejecuciones.

Este flujo es el objetivo de EduPass 1.0; al cierre de Semana 11 todavía no
están implementados la credencial, el QR, los movimientos ni el historial.

## 5. Alcance incluido

- Aplicación web responsiva para una sola escuela.
- Ejecución local o en red privada de demostración.
- Autenticación de administrador y personal de escaneo.
- Administración de alumnos mediante la arquitectura existente.
- Listado web de alumnos de solo lectura.
- Credencial controlada para alumnos activos.
- QR temporal de 30 segundos y de un solo uso.
- Captura manual obligatoria del token.
- Cámara opcional y deseable.
- Entrada y salida del plantel.
- Rechazo de movimientos inconsistentes.
- Historial básico en pantalla.
- Persistencia local con SQLite.
- Interfaz PySide6 conservada como antecedente funcional.

## 6. Alcance excluido

- Tutores y sus asociaciones.
- Notificaciones push.
- Áreas internas, permisos por área y movimientos internos.
- Dispositivos fijos registrados.
- Aplicación móvil nativa.
- Publicación en Internet y multiinstitución.
- Modo offline.
- Pagos, transporte y calificaciones.
- Reconocimiento facial y geolocalización.
- Exportación de reportes.
- Carga web de fotografías.

## 7. Restricciones y limitaciones

- El valor inicial del QR debe ser 30 segundos y cada token debe usarse una
  sola vez.
- El QR no debe exponer nombre, matrícula, grado, grupo, fotografía ni otros
  datos personales legibles.
- La captura manual no puede eliminarse aunque se agregue cámara.
- No se utilizarán datos personales reales en la demostración.
- HTTP local no equivale a HTTPS; el canal cifrado queda pendiente para un
  despliegue real.
- SQLite es suficiente para el prototipo local, pero no se presenta como una
  solución de producción multiusuario.
- La compatibilidad y el diseño responsivo requieren evidencia final en los
  navegadores disponibles; no existe validación pixel-perfect.

## 8. Tecnología aprobada

- Python y Flask para la capa web.
- Jinja, HTML y CSS responsivo para las vistas.
- Flask-Login para sesiones.
- Flask-WTF para formularios y protección CSRF.
- SQLite para persistencia local.
- `unittest` para pruebas automatizadas.
- PySide6 y Qt Designer únicamente como prototipo anterior conservado.

No se requieren React, Angular, Vue, Node.js como backend, Flutter, Android
Studio, microservicios, Firebase ni Docker.

## 9. Arquitectura reutilizada

La web consume servicios existentes y conserva la separación:

```text
Interfaz web o PySide6
        |
        v
Servicios de dominio
        |
        v
Repositorios
        |
        v
SQL externo parametrizado
        |
        v
SQLite
```

La capa web agrega fábrica Flask, formularios, sesión, autorización, rutas,
plantillas y CSS. No duplica las reglas del servicio de alumnos ni permite que
las vistas consulten SQLite directamente.

## 10. Evolución de interfaz

PySide6 demuestra el registro, consulta, edición, activación y desactivación de
alumnos y se conserva como antecedente del segundo parcial. La interfaz web
responsiva será la interfaz principal final porque puede atender computadora,
tablet y teléfono desde un navegador dentro de la red de demostración.

No se desarrolla una aplicación móvil nativa porque duplicaría interfaz,
distribución, autenticación y pruebas. La cámara permanece deseable debido a
permisos, compatibilidad y variaciones de hardware; la entrada manual ofrece
una ruta verificable y obligatoria.

## 11. Razones de exclusión

Tutores y notificaciones push requieren asociaciones, destinatarios,
infraestructura externa y manejo de entregas. Áreas, permisos y dispositivos
fijos multiplican configuraciones y reglas de movimiento. Ninguno bloquea el
flujo mínimo de entrada y salida del plantel, por lo que quedan fuera de
EduPass 1.0 para proteger la calidad y el calendario.

## 12. Congelamiento previsto

Al terminar Semana 12 debe quedar integrado y probado el flujo principal de
credencial, QR, movimientos e historial. A partir de ese punto no deben
incorporarse funciones grandes: Semana 13 se reserva para correcciones
críticas, pruebas finales, instalación, manuales y preparación de la
presentación de Semana 14.
