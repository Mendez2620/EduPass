# Implementación de credencial y QR

## Núcleo

El núcleo se separa en:

- constantes y excepciones controladas en `src/edupass/shared/`;
- utilidades de token, hash y UTC en el módulo de credencial;
- consultas parametrizadas bajo `src/edupass/persistence/sql/qr_tokens/`;
- `qr_token_repository.py` para transacciones y acceso SQLite;
- `credencial_service.py` para generación, renovación y metadatos;
- `validacion_service.py` para formato, clasificación y consumo.

Los servicios no contienen SQL ni importan Flask o PySide6. El repositorio no
genera tokens ni construye mensajes web.

## Integración web

La integración añade:

- formularios Flask-WTF para generar, renovar y validar;
- rutas administrativas protegidas para la credencial;
- rutas exclusivas del rol escáner para captura manual;
- plantilla de credencial con matrícula enmascarada;
- renderizador QR SVG en memoria;
- JavaScript para renovación automática controlada;
- estilos responsivos integrados al diseño existente.

`qrcode==8.2` es la única dependencia nueva. Pillow no se agregó. El SVG se
convierte en una `data URI`; no se crean archivos SVG o PNG en el repositorio ni
en `data/`.

## Flujo

1. Un administrador autenticado genera la credencial desde el listado.
2. El backend rechaza alumnos inexistentes o inactivos.
3. La respuesta inmediata muestra datos mínimos, matrícula enmascarada, SVG,
   token manual y vigencia.
4. La renovación manual usa POST y funciona sin JavaScript.
5. La renovación automática realiza una sola solicitud por ciclo.
6. El escáner autenticado pega o escribe el token en un formulario.
7. La validación consume el token y aclara que no se registró movimiento.

Todos los POST usan CSRF. Los GET sobre rutas exclusivas de generación o
renovación reciben 405. Las respuestas de credencial usan `Cache-Control:
no-store` y `Referrer-Policy: no-referrer`. El token no se coloca en URL,
sesión, `flash`, logs ni mensajes posteriores al consumo.

## No implementado

No se implementaron cámara, movimientos, historial, cuenta del alumno, portal
público, aplicación móvil, imágenes QR permanentes, notificaciones, tutores,
áreas funcionales ni dispositivos funcionales.
