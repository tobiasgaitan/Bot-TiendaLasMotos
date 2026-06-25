---
task: 68
name: hotfix-webhook-sync-block
description: Falta de registro en Langfuse, resúmenes de Firebase vacíos y omisión de creación de leads en CRM debido al uso de tareas fire-and-forget en la ruta crítica del webhook, interrumpiendo el flujo antes del commit de persistencia síncrona.
---

# Quick Task 068: hotfix-webhook-sync-block

## Objective
Reemplazar todo uso de background tasks de FastAPI o asyncio.create_task en el procesamiento conversacional del webhook por llamadas síncronas bloqueantes mediante 'await' en `app/routers/whatsapp.py`. El orquestador conversacional debe esperar la confirmación de base de datos y el tracing de Langfuse antes de liberar el hilo y responder HTTP 200 a Meta.

## Tasks

<task type="auto">
  <name>Modificar webhook_handler en whatsapp.py</name>
  <files>[app/routers/whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py)</files>
  <action>Reemplazar `background_tasks.add_task(_handle_statuses_background, status_data)` y `background_tasks.add_task(_handle_message_background, msg_data, background_tasks)` por llamadas síncronas con `await`.</action>
  <verify>uv run pytest tests/test_reset_concurrency_storm.py</verify>
  <done>Las llamadas en `app/routers/whatsapp.py` se ejecutan síncronamente usando `await`.</done>
</task>

<task type="auto">
  <name>Crear test unitario de aserción de contenido y concurrencia</name>
  <files>[tests/test_webhook_sync_block.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_webhook_sync_block.py)</files>
  <action>Crear un test unitario de aserción de contenido que verifique la presencia explícita de la cadena transformada 'PENDING' u 'ACTIVE' en un flujo simulado con delays de red y prohíba que una mutación de llaves resulte en un string vacío o valores devueltos como None silenciosos.</action>
  <verify>uv run pytest tests/test_webhook_sync_block.py</verify>
  <done>El nuevo test unitario pasa correctamente.</done>
</task>

---
*Created: 2026-06-25*
