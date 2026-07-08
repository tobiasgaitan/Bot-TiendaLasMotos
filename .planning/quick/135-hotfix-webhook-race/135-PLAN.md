---
task: 135
name: hotfix-webhook-race
description: Asimetría en el procesamiento de webhooks locales/beta (acuses síncronos vía await vs mensajes asíncronos vía background_tasks) provoca que los acuses se ejecuten antes de la creación del prospecto en Firestore, disparando falsos positivos de WEBHOOK_RECOVERY.
---

# Quick Task 135: hotfix-webhook-race

## Objective
Resolver la carrera de condiciones y falsos positivos de `WEBHOOK_RECOVERY` delegando el procesamiento de statuses en el webhook de WhatsApp a `background_tasks` en ausencia de Cloud Tasks, e implementando un bypass en `MemoryService.update_whatsapp_status` para ignorar los acuses `sent`/`delivered` si el prospecto no existe físicamente en Firestore.

## Tasks

<task type="auto">
  <name>Delegar procesamiento de statuses a BackgroundTasks</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>Modificar app/routers/whatsapp.py en la Rama 1 (Acuses) para que en ausencia de Cloud Tasks use background_tasks.add_task(_handle_statuses_background, status_data) en lugar de await directo.</action>
  <verify>./.venv/bin/pytest tests/test_webhook_sync_block.py</verify>
  <done>El código usa add_task para los statuses del webhook en ausencia de Cloud Tasks y las pruebas pasan.</done>
</task>

<task type="auto">
  <name>Bypass en MemoryService para acuses en prospecto inexistente</name>
  <files>
    <file>app/services/memory_service.py</file>
  </files>
  <action>Modificar app/services/memory_service.py en update_whatsapp_status para que si el documento no existe (is_new_doc es True) y el status es "sent" o "delivered", se ignore el acuse sin recrear el prospecto de forma destructiva.</action>
  <verify>./.venv/bin/pytest tests/test_reset_concurrency_storm.py</verify>
  <done>El método update_whatsapp_status retorna temprano e ignora acuses sent/delivered si el documento no existe físicamente, manteniendo la suite de pruebas libre de fallos.</done>
</task>

<task type="auto">
  <name>Añadir pruebas unitarias específicas para la delegación asíncrona de statuses</name>
  <files>
    <file>tests/test_webhook_sync_block.py</file>
  </files>
  <action>Escribir un nuevo caso de prueba en tests/test_webhook_sync_block.py para verificar que el webhook_handler delega el procesamiento de statuses a background_tasks cuando Cloud Tasks está desactivado.</action>
  <verify>./.venv/bin/pytest tests/test_webhook_sync_block.py</verify>
  <done>El nuevo test unitario pasa correctamente.</done>
</task>

---
*Created: 2026-07-07*
