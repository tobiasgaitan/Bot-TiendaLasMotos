---
task: 022
name: Langfuse Observability Integration (BOT-TRACE-201)
description: Integración de Langfuse para observabilidad total del ciclo de vida del prospecto.
---

# Quick Task 022: Langfuse Observability Integration

## Objective
Integrar el SDK de Langfuse para capturar trazas de `pensar_respuesta` y `_generate_with_retry_async`,
mapeando `prospect_id` (phone) como `userId` y capturando latencia de `search_catalog` y tokens.

## Tasks

<task type="auto">
  <name>Task A: Agregar langfuse a requirements.txt</name>
  <files>requirements.txt</files>
  <action>Append `langfuse>=2.0.0` to requirements.txt</action>
  <verify>grep -n "langfuse" requirements.txt</verify>
  <done>langfuse aparece en requirements.txt con versión</done>
</task>

<task type="auto">
  <name>Task B: Configurar cliente Langfuse en config.py</name>
  <files>app/core/config.py</files>
  <action>Agregar variables LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST a Settings</action>
  <verify>python3 -c "from app.core.config import settings; print(hasattr(settings, 'langfuse_public_key'))"</verify>
  <done>Settings expone las tres variables de Langfuse sin romper validación</done>
</task>

<task type="auto">
  <name>Task C: Instrumentar ai_brain.py con @observe()</name>
  <files>app/services/ai_brain.py</files>
  <action>
    1. Import langfuse con guard `try/except` (LANGFUSE_AVAILABLE flag).
    2. Decorar `pensar_respuesta` con `@observe()`.
    3. Dentro de `_generate_with_retry_async`, al inicio inyectar `propagate_attributes(user_id, session_id, tags=[funnel_phase])`.
    4. En el bloque `search_catalog` (L953-957), enriquecer con `langfuse.update_current_observation(metadata={"latency_s": latency})`.
    5. En el bloque de telemetría final (L908-914), reportar tokens via `langfuse.update_current_generation(usage_details)`.
  </action>
  <verify>python3 -c "import ast; ast.parse(open('app/services/ai_brain.py').read()); print('AST OK')"</verify>
  <done>AST parsea sin errores. Langfuse se importa con guard. `@observe()` presente en `pensar_respuesta`.</done>
</task>

---
*Created: 2026-05-11*
