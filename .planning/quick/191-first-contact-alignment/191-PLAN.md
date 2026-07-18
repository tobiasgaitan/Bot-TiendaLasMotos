---
task: 191
name: First Contact Alignment
description: Refactorizar el cerebro para forzar el saludo e identidad de Juan Pablo en el primer contacto / reset, y robustecer el guardrail del catálogo en el webhook handler y task processor para evitar falsos negativos en cold-start.
---

# Quick Task 191: First Contact Alignment

## Objective
Garantizar la identidad y presentación comercial del bot en su primer mensaje e impedir falsos negativos de inventario debido a consultas de catálogo prematuras durante el arranque/hidratación de la aplicación.

## Tasks

<task type="auto">
  <name>Refactorizar skip_greeting en ai_brain.py</name>
  <files>app/services/ai_brain.py</files>
  <action>Introducir la detección de primer contacto/reset en _generate_with_retry_async y evitar que la pre-búsqueda caliente o ejecución de la herramienta search_catalog seteen skip_greeting = True.</action>
  <verify>uv run pytest tests/test_identity_legal_gate.py</verify>
  <done>La variable skip_greeting no se modifica a True en el primer contacto.</done>
</task>

<task type="auto">
  <name>Robustecer guardrail de catálogo en whatsapp.py</name>
  <files>app/routers/whatsapp.py</files>
  <action>Refactorizar webhook_handler y task_processor para rechazar con HTTP 503 si catalog_ready no es True o si la longitud de catalog_service.get_all_items() es inferior a min_catalog_items.</action>
  <verify>uv run pytest tests/test_startup_lock.py</verify>
  <done>Ambos endpoints devuelven HTTP 503 si el catálogo no está completamente hydrated/ready.</done>
</task>

<task type="auto">
  <name>Inyectar caso de prueba de integración</name>
  <files>tests/test_identity_legal_gate.py</files>
  <action>Inyectar test_first_interaction_always_greets que valide el saludo de Juan Pablo en la primera interacción y pase todas las aserciones de paridad.</action>
  <verify>uv run pytest tests/test_identity_legal_gate.py</verify>
  <done>El nuevo test de integración pasa exitosamente.</done>
</task>

<task type="auto">
  <name>Certificación final agent-cli</name>
  <files>app/services/ai_brain.py, app/routers/whatsapp.py, tests/test_identity_legal_gate.py, tests/test_startup_lock.py</files>
  <action>Ejecutar npx agent-cli eval para certificar el Score de 1.000.</action>
  <verify>npx agent-cli eval</verify>
  <done>El Coherence Score es 1.000 y el 100% de los tests pasan.</done>
</task>

---
*Created: 2026-07-16*
