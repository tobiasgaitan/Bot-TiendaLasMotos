---
task: 134
name: hotfix-reaction-debounce
description: Corregir vaciado de variable por agregación de buffer en reacciones e inyectar test unitario de cobertura para payloads tipo reaction de Meta
---

# Quick Task 134: hotfix-reaction-debounce

## Objective
Corregir la regresión donde la agregación de buffer en reacciones vacía la variable `message_body` para reacciones de WhatsApp, e inyectar una prueba unitaria robusta para asegurar la cobertura de payloads de tipo `reaction`.

## Tasks

<task type="auto">
  <name>Modificar bloque condicional de reacción en whatsapp.py</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>Capturar el valor original de message_body antes del sleep de debounce en reacciones y restaurarlo si el buffer consolidado retorna vacío.</action>
  <verify>pytest tests/test_agentic_loop_async.py</verify>
  <done>El buffer no anula el valor 'Sí' (o [REACTION]) tras el sleep en las reacciones.</done>
</task>

<task type="auto">
  <name>Inyectar test unitario para reaccionales de WhatsApp</name>
  <files>
    <file>tests/test_agentic_loop_async.py</file>
  </files>
  <action>Añadir test_whatsapp_reaction_payload_processing en tests/test_agentic_loop_async.py con mocks para simular payload de reaction y validar procesamiento.</action>
  <verify>pytest -v tests/test_agentic_loop_async.py -k test_whatsapp_reaction_payload_processing</verify>
  <done>El nuevo test unitario pasa con éxito.</done>
</task>

---
*Created: 2026-07-07*
