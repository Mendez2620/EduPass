# Bitácora técnica resumida de Codex - Semana 11

Esta bitácora registra actividades y decisiones verificables. No reconstruye
los prompts ni las respuestas como transcripciones literales.

| Número | Actividad | Objetivo | Restricciones principales | Resultado | Archivos afectados | Pruebas | Commit | Decisión posterior |
|---:|---|---|---|---|---|---|---|---|
| 1 | Diagnóstico inicial del repositorio | Confirmar rama, SHA, estado y suite existente | No modificar ni agregar la carpeta de presentación | Se identificó el corte funcional y el árbol real | Ninguno | 75 en OK | No aplica | Analizar alcance antes de programar. |
| 2 | Auditoría de cambios pendientes | Distinguir cambios técnicos y material no rastreado | No restaurar ni borrar trabajo existente | Solo la carpeta protegida permaneció fuera de Git | Ninguno | Suite de referencia | No aplica | Mantener staging selectivo. |
| 3 | Separación y commit del listado de alumnos | Cerrar el incremento previo de alumnos | No mezclar documentación ni funciones nuevas | Listado general integrado y publicado por separado | Alumnos, SQL y pruebas del corte previo | 75 en OK | `6b12ea8` | Reutilizar `listar_alumnos()` en web. |
| 4 | Publicación de avances anteriores | Sincronizar el prototipo de alumnos | Auditar antes de publicar | PySide6 y listado quedaron en `origin/master` | Solo archivos autorizados de avances previos | 75 en OK | `83081a6`, `6b12ea8` | Conservar PySide6 como antecedente. |
| 5 | Delimitación de EduPass 1.0 | Reducir el alcance a un flujo demostrable | Una escuela, web local, sin tutores/push/áreas/dispositivos | Se aprobaron dos roles autenticados y credencial controlada | Ninguno | No aplica | No aplica | Priorizar autenticación y base web. |
| 6 | Plan técnico del incremento | Definir capas, contratos, seguridad y pruebas | No duplicar alumnos ni modificar esquema | Se separaron backend auth y capa web | Ninguno | Estrategia de 62 pruebas nuevas | No aplica | Implementar autenticación primero. |
| 7 | Backend de autenticación | Crear usuarios demo, autenticar y validar roles | Sin interfaz web, QR, movimientos ni secretos | Servicios, repositorios, SQL y script interactivo completados | Auth, persistencia, compartidos, pruebas y requisitos | Suite creció de 75 a 137 | `2e1c520` | Reutilizar contratos desde Flask. |
| 8 | Capa web | Crear fábrica, login, roles, paneles y listado | Sin CRUD web, PySide6, QR, movimientos ni historial | Web mínima responsiva y configurable completada | `src/edupass/web/`, pruebas, configuración y README raíz | 35 nuevas; total 172 | `3520ddd` | Auditar y publicar ambos commits. |
| 9 | Auditoría y publicación | Verificar alcance, secretos, pruebas y remoto | Sin commits nuevos, force push, pull, merge o rebase | Dos commits técnicos publicados; local y remoto sincronizados | Ninguno durante auditoría | 172 en OK; validación manual temporal | No aplica | Preparar cierre documental. |
| 10 | Documentación de cierre | Consolidar alcance, trazabilidad, evidencia y plan | Solo siete Markdown; no iniciar Semana 12 | Cierre formal preparado en `docs/semana_11/` | Siete documentos de Semana 11 | Suite inicial y final de 172 | Commit documental local | Mantener remoto sin cambios hasta autorización futura. |

## Prompts y respuestas completos

“Los prompts y las respuestas completas se conservan en el historial original
de trabajo y se incorporarán sin resumir en el documento académico acumulativo.
Este archivo no sustituye esa transcripción.”
