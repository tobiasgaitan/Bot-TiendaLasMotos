---
task: 123
name: Align _LangfuseContextShim interface
description: Interface misalignment en _LangfuseContextShim de app/services/ai_brain.py provoca advertencias por falta del atributo update_current_generation y fuga silenciosa de métricas de coste en entornos con telemetría offline.
---

# Quick Task 123: Align _LangfuseContextShim interface

## Objective
Align `_LangfuseContextShim` in `app/services/ai_brain.py` and `app/routers/whatsapp.py` to support `update_current_generation(self, **kwargs)` gracefully to prevent telemetry errors when Langfuse is offline or disabled.

## Tasks

<task type="auto">
  <name>Align _LangfuseContextShim interface</name>
  <files>app/services/ai_brain.py, app/routers/whatsapp.py</files>
  <action>Add `def update_current_generation(self, **kwargs): pass` to class `_LangfuseContextShim` in both files.</action>
  <verify>.venv/bin/pytest && npx agent-cli eval</verify>
  <done>The test suite passes and the coherence score is 1.000.</done>
</task>

---
*Created: 2026-07-06*
