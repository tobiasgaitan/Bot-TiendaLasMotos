---
task: 159
name: Hotfix Unified Egress Message Delivery
description: Falso positivo por Mocking Blindness en tests históricos. El bloque que procesa mensajes entrantes de tipo imagen ejecuta 'pensar_respuesta' de CerebroIA pero despacha el resultado invocando de forma directa a '_send_whatsapp_message' en texto plano, evadiendo el pipeline de parsing de patrones Markdown e inyectando código crudo en producción.
---

# Quick Task 159: Hotfix Unified Egress Message Delivery

## Objective
Extract the image detection, extraction, and cleaning logic into a unified, reusable asynchronous function `_process_and_send_egress_message` inside `app/routers/whatsapp.py`. Replace direct plain-text message sending in the image webhook block and the text webhook block with calls to this function, ensuring correct Markdown image parsing, Strategy A (caption) sending, and historical message logging.

## Tasks

<task type="auto">
  <name>Extract and unify markdown image egress processing</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>
    Define the `_process_and_send_egress_message` helper in `app/routers/whatsapp.py` to encapsulate regex matching/extraction, Strategia A caption/overflow sending, and history logging. Replace plain-text message calls at L842 (image block response) and L1556 (text block response) to route through `_process_and_send_egress_message`.
  </action>
  <verify>pytest tests/test_agentic_loop_async.py</verify>
  <done>
    Both image-incoming webhook response and regular text response correctly parse markdown images, format captions, and log model answers.
  </done>
</task>

<task type="auto">
  <name>Redesign test suite to simulate image inputs and assert metadata output</name>
  <files>
    <file>tests/test_agentic_loop_async.py</file>
  </files>
  <action>
    Add a new test or adapt the async agentic loop test suite to send an incoming image webhook, mock CerebroIA to return a markdown image response, and verify Meta's outbound message payload is correctly mutated to type 'image' with correct link/caption parameters.
  </action>
  <verify>pytest tests/test_agentic_loop_async.py</verify>
  <done>
    Test suite includes strict assertions verifying Meta's payload has type 'image' and contains correct links/captions, passing local pytest execution.
  </done>
</task>

---
*Created: 2026-07-11*
