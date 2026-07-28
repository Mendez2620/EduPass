# Contrato técnico del QR temporal

## Persistencia

Se reutiliza la tabla existente `qr_tokens`, sin migración de esquema. Sus datos
operativos son `qr_id`, `alumno_id`, `token_hash`, `generado_en`, `expira_en`,
`usado_en` y `estado`. La relación con `alumnos` permite comprobar que el alumno
existe y continúa activo.

El token original nunca se persiste. Se genera con
`secrets.token_urlsafe(32)`, tiene 43 caracteres Base64URL sin relleno y se
almacena únicamente su SHA-256 hexadecimal. No se usa salt porque el token tiene
alta entropía criptográfica y no proviene de un dominio pequeño susceptible de
diccionario. El hash no permite reconstruir ni volver a mostrar el token.

El QR no codifica nombre, matrícula, grado, grupo, fotografía, correo, usuario,
rol ni identificadores personales. Codifica solamente el token opaco.

## Tiempo y vigencia

Las fechas son `datetime` conscientes de zona y se normalizan a UTC. El formato
persistido es:

```text
YYYY-MM-DDTHH:MM:SS.ffffffZ
```

La vigencia es de 30 segundos. Un token es temporalmente válido solo cuando
`ahora < expira_en`; en el instante exacto de vencimiento ya es inválido. Los
servicios aceptan un reloj inyectable para probar los límites sin `sleep()`.

## Estados

Estados persistidos:

- `activo`
- `utilizado`
- `invalidado`

`vencido` es un estado calculado a partir de `expira_en`; no se persiste.
`inexistente` y `alumno inactivo` también son resultados de clasificación.

## Reemplazo y consumo

La generación o renovación invalida los tokens activos previos del alumno e
inserta el nuevo token dentro de una sola transacción. No se eliminan filas.

El consumo abre una transacción corta con `BEGIN IMMEDIATE`, clasifica el
registro y ejecuta un `UPDATE` condicional que exige hash coincidente, estado
activo, `usado_en IS NULL` y `expira_en > ahora`. Solo `rowcount == 1` representa
éxito. En cualquier error se realiza rollback y la conexión se cierra.

Esta estrategia impide dos consumos exitosos del mismo token dentro de las
garantías del prototipo SQLite. No convierte SQLite en una solución de
producción para alta concurrencia.

## Respuestas y privacidad

La generación devuelve el token original solo en la respuesta inmediata que lo
necesita para mostrar el QR. Las consultas posteriores devuelven únicamente
metadatos. Los servicios y repositorios no registran tokens completos, hashes,
SQL, rutas locales ni datos personales en mensajes públicos.

La limitación del modelo hash-only es deliberada: después de perder la respuesta
inmediata no es posible recuperar el token; se debe generar uno nuevo, lo que
invalida el anterior.
