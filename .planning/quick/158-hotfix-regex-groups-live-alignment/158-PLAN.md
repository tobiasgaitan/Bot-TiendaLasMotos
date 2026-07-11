---
task: 158
name: Hotfix Regex Groups Live Alignment
description: Falso positivo en la suite de pruebas debido a Mocking Blindness. El uso de re.findall con múltiples grupos alternativos dentro de un contenedor no capturable genera tuplas con strings vacíos y falla al procesar caracteres de control o saltos de línea inyectados por el LLM en vivo.
---

# Quick Task 158: Hotfix Regex Groups Live Alignment

## Objective
Fix regex capturing/parsing in whatsapp.py for markdown and legacy image URL extraction to avoid empty group tuples, support live LLM formatting (with control characters and newlines), and add strict assertions to test_agentic_loop_async.py to verify Meta payload format.

## Tasks

<task type="auto">
  <name>Align regex parsing in whatsapp.py</name>
  <files>
    - app/routers/whatsapp.py
  </files>
  <action>Replace pattern in L1515 with separate robust regex expressions for Markdown and legacy formats to extract URLs cleanly without generating empty group tuples, handling newlines/control characters.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py -k "test_whatsapp_image_url" -vv -s</verify>
  <done>Regex successfully parses URL and cleans response text without raising exceptions or leaving Markdown tags.</done>
</task>

<task type="auto">
  <name>Implement rigid assertion in test suite</name>
  <files>
    - tests/test_agentic_loop_async.py
  </files>
  <action>Add a rigid assertion on the simulated Meta outgoing payload to ensure type is strictly 'image' and caption does not contain brackets/raw URLs.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py -k "test_whatsapp_image_url" -vv -s</verify>
  <done>Tests pass and assert correct Meta payload formatting.</done>
</task>

---
*Created: 2026-07-11*
