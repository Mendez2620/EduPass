# Reporte del incremento técnico de Semana 11

## 1. Objetivo

Agregar autenticación modular y una capa web mínima, segura y comprobable,
reutilizando alumnos y persistencia sin iniciar QR, movimientos o historial.

## 2. Estado previo

Antes del incremento existían SQLite, `DatabaseManager`, el módulo funcional de
alumnos, SQL externo, pruebas automatizadas y la interfaz PySide6. La suite
tenía 75 pruebas. No existían autenticación funcional ni capa web.

## 3. Decisiones técnicas

- Mantener la arquitectura por capas y la disposición `src/`.
- Implementar primero autenticación y luego la interfaz web.
- Autorizar únicamente los roles `administrador` y `escaner`.
- Mantener al alumno sin cuenta completa.
- Usar Flask, Jinja, CSS propio, Flask-Login y Flask-WTF.
- Exigir `EDUPASS_SECRET_KEY` fuera de pruebas.
- Usar conexiones SQLite por operación, sin conexión global.
- Conservar PySide6 sin reescribirlo.

## 4. Backend de autenticación

El primer commit agregó repositorios y SQL externo para roles y usuarios,
servicios de creación y autenticación, hash seguro de contraseñas, validación
de roles, recuperación segura de sesión y un script interactivo para crear
usuarios de demostración. Las respuestas del servicio excluyen
`password_hash`.

## 5. Capa web

El segundo commit agregó:

- fábrica `create_app(test_config=None)`;
- configuración por variables de entorno;
- Flask-Login y Flask-WTF;
- formularios de login y logout;
- cierre de sesión únicamente por `POST`;
- decorador reutilizable de rol;
- errores 403 y 404;
- panel de administrador;
- listado administrativo de alumnos de solo lectura;
- panel de escáner que declara el alcance pendiente;
- CSS responsivo propio;
- punto de entrada `python -m edupass.web`.

## 6. Integración con alumnos

La ruta administrativa llama a
`alumnos_service.listar_alumnos(DATABASE_PATH)`. No importa el repositorio ni
ejecuta SQL. La plantilla recibe únicamente ID, nombre, matrícula, grado,
grupo y estado; no recibe fotografía ni ruta local.

## 7. Archivos principales

| Grupo | Archivos principales |
|---|---|
| Autenticación | `usuarios_service.py`, `roles_service.py` |
| Persistencia auth | `usuario_repository.py`, `rol_repository.py`, SQL de usuarios y roles |
| Preparación de demo | `scripts/create_demo_user.py` |
| Fábrica y entrada web | `src/edupass/web/__init__.py`, `__main__.py` |
| Seguridad web | `extensions.py`, `security.py`, `forms.py` |
| Rutas | `auth_routes.py`, `admin_routes.py`, `scanner_routes.py` |
| Presentación | plantillas Jinja y `static/css/app.css` |
| Configuración | `.env.example`, `.gitignore`, `requirements.txt` |
| Pruebas | pruebas de auth, repositorios, servicios, script y web |

## 8. Rutas implementadas

| Método | Ruta | Acceso | Función |
|---|---|---|---|
| GET | `/` | Público controlado | Redirige a login o panel por rol. |
| GET/POST | `/login` | No autenticado | Inicia sesión con correo y contraseña. |
| POST | `/logout` | Autenticado + CSRF | Cierra y limpia la sesión. |
| GET | `/admin` | Administrador | Muestra el panel administrativo. |
| GET | `/admin/alumnos` | Administrador | Lista alumnos en modo de solo lectura. |
| GET | `/scanner` | Escáner | Muestra el panel base del siguiente incremento. |

También existen manejadores HTML para respuestas 403 y 404.

## 9. Roles y seguridad básica

- Los IDs de rol no están fijados en las rutas.
- `SessionUser` conserva solo los datos necesarios de sesión.
- El usuario se recarga mediante el servicio y una cuenta inactiva no se
  conserva como sesión válida.
- `role_required` exige autenticación y valida el rol nominal.
- Las contraseñas se verifican mediante hash y no se guardan en sesión.
- CSRF protege formularios y logout.
- La sesión es permanente con duración configurable, 30 minutos por defecto.
- Las cookies usan `HttpOnly` y `SameSite=Lax`.
- `Secure=False` es una limitación explícita de la demostración HTTP local.
- No se versiona `.env` ni una clave secreta real.

## 10. Configuración

`.env.example` documenta, sin valores sensibles:

- `EDUPASS_SECRET_KEY`
- `EDUPASS_DATABASE_PATH`
- `EDUPASS_SESSION_MINUTES`
- `EDUPASS_HOST`
- `EDUPASS_PORT`

La aplicación falla con un mensaje controlado cuando falta la clave secreta
fuera de pruebas. El host predeterminado es `127.0.0.1`, el puerto es `5000` y
el modo de depuración y el recargador permanecen desactivados.

## 11. Pruebas

La autenticación elevó la suite de 75 a 137 pruebas. La capa web agregó 35,
para un total de 172:

| Grupo | Pruebas |
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

Las pruebas usan bases SQLite temporales. No se ejecutó una herramienta de
cobertura, por lo que no se declara un porcentaje.

## 12. Validación manual

Durante la auditoría de publicación se utilizó una base temporal fuera del
repositorio y usuarios ficticios creados mediante los servicios. Se verificó
arranque sin traceback, login de administrador y escáner, separación de roles,
listado administrativo, logout y cierre controlado del servidor. La base
temporal fue eliminada. Esta validación no acredita aún compatibilidad final en
todos los navegadores ni calidad pixel-perfect.

## 13. Problemas y correcciones

La capa web se ajustó a los contratos reales de servicios en vez de duplicar
persistencia. Se trataron de forma controlada la ausencia de `SECRET_KEY`, los
valores inválidos de sesión o puerto, los roles no autorizados, el acceso
cruzado y los errores del listado. Una ejecución interrumpida se retomó después
de auditar los archivos existentes, evitando repetir o restaurar cambios.

No fue necesaria una corrección de la lógica principal después de la auditoría
final: la suite publicada terminó en `OK`. El mensaje de advertencia controlado
del listado ante un error simulado de repositorio es evidencia del caso de
error, no un fallo de prueba.

## 14. Commits y publicación

1. `2e1c520e7cd51e57937d16b1321410c9ca8584ac` -
   `feat: implementar autenticacion modular`
2. `3520ddd797685773e3148932eb6b4bb1a70f2a3c` -
   `feat: agregar base web y listado administrativo`

Ambos commits técnicos fueron auditados y publicados en `origin/master`. No se
incluyeron metadatos personales, documentación de presentación, bases SQLite,
secretos ni credenciales.

## 15. Resultado y requerimientos atendidos

RF-16 y RF-19 quedaron implementados para los dos roles aprobados. RF-01 se
reutiliza mediante el listado web, pero la web no registra alumnos. RF-02
permanece implementado en servicio y repositorio. RF-17 cuenta con preparación
parcial mediante servicio y script interactivo.

No se atendieron todavía los RF funcionales de credencial, QR, validación,
movimientos o historial. RF-33 solo dispone de soporte estructural. Tutores,
push, áreas y dispositivos permanecen fuera de EduPass 1.0.

## 16. Limitaciones y conclusión

La web es un prototipo local, no una publicación en Internet. HTTP local no
cumple HTTPS y SQLite no se plantea para producción multiusuario. El responsive
requiere evidencia final en navegadores y dispositivos disponibles.

El incremento deja una base autenticada, modular y probada sobre la cual puede
integrarse en Semana 12 el flujo principal, sin declarar como terminadas
funciones que aún no existen.
