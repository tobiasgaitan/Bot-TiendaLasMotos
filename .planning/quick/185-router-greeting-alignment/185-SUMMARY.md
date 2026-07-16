# Quick Task 185: Router Greeting Alignment Hotfix — Summary

**Executed:** 2026-07-16
**Status:** Complete

## What Was Done
- Se implementó en `app/services/ai_brain.py` la lógica de **Runtime Prompt Assembly** mediante el método helper `_assemble_skip_greeting_prompt`.
- Cuando la bandera `skip_greeting` es `True`, se reescribe de forma dinámica la instrucción del sistema (`base_instruction`) cargada en tiempo de ejecución:
  - Se sustituye y suprime la instrucción del PASO 1 (Enganche) para prohibir de forma determinista el saludo ("¡Hola!"), bienvenida o presentación de Juan Pablo.
  - Se inyecta una regla inquebrantable que obliga al LLM a iniciar la respuesta directamente con la presentación de la motocicleta (información, imagen y precio).
- Se agregaron casos de prueba automatizados en `tests/test_agentic_loop_async.py` que comprueban la reescritura correcta de los prompts y validan que segundas consultas de catálogo consecutivas con `skip_greeting=True` no contengan saludos.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/services/ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py) | Modified | Se añadió la reescritura de prompts dinámica para saludos condicionales en `pensar_respuesta`. |
| [tests/test_agentic_loop_async.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_agentic_loop_async.py) | Modified | Se añadieron tests de regresión para búsquedas de catálogo consecutivas y comprobación de reescritura de prompts. |

## Verification
Se ejecutaron los tests locales del bot y la suite de evaluación completa:
- `.venv/bin/pytest tests/test_agentic_loop_async.py` -> 27 passed.
- `.venv/bin/pytest tests/test_pcc_ficha_tecnica.py` -> 12 passed.
- `npx agent-cli eval` -> 261 passed, Coherence Score = 1.000.

---
*Completed: 2026-07-16*
