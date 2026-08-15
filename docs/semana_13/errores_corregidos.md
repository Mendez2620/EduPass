# Errores y riesgos corregidos

| Área | Corrección final |
|---|---|
| Autorización | Roles nominales, sesión recargada e IDOR bloqueado |
| Contraseñas | `secrets`, sólo hash, muestra única, `no-store` y cambio obligatorio |
| Sesiones | Flag recargado y validación de la temporal actual |
| QR | Hash SHA-256, 30 segundos, uso único y sin token textual |
| Movimientos | Tipo determinado por backend y transacción atómica |
| Cámara | ZXing local, controles explícitos y respaldo manual |
| UX | Navegación y vistas responsive verificadas |
| Privacidad | Base temporal, datos ficticios y revisión visual |

Los dominios futuros no se presentaron como implementados.
