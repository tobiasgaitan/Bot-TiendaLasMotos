---
task: 161
name: Langfuse Adapter Creation
description: Create and verify the isolated local Adapter Pattern in app/utils/observability.py.
---

# Quick Task 161: Langfuse Adapter Creation (Tarea 1)

## Objetivo
Crear y verificar de forma aislada el adaptador local `app/utils/observability.py` que envuelve el SDK real de Langfuse v4 y expone `observe` y `langfuse_context` adaptados al nuevo contrato de OpenTelemetry, sin alterar otros archivos del codebase ni site-packages.

## Tareas

<task type="auto">
  <name>Tarea 1: Crear adaptador de observabilidad app/utils/observability.py</name>
  <files>app/utils/observability.py</files>
  <action>
    Crear el archivo app/utils/observability.py con la siguiente lógica:
    1. Importar opentelemetry.trace y LangfuseOtelSpanAttributes.
    2. Importar observe desde langfuse y definir un fallback no-op si langfuse no está instalado.
    3. Crear la clase adaptador _LangfuseContextAdapter que exponga:
       - update_current_trace: recibe user_id, session_id, tags y metadata, y los asocia como atributos en el span activo de OpenTelemetry usando las constantes oficiales de LangfuseOtelSpanAttributes (user.id, session.id, trace.tags, trace.metadata).
       - update_current_observation: recibe metadata y kwargs, y los asocia como atributos en el span activo.
       - update_current_generation: recibe metadata y kwargs, y los asocia como atributos en el span activo.
    4. Instanciar langfuse_context = _LangfuseContextAdapter() y exportar observe y langfuse_context.
  </action>
  <verify>.venv/bin/python3 -c "from app.utils.observability import observe, langfuse_context; print(observe, langfuse_context)"</verify>
  <done>El adaptador local es creado y se puede importar de manera limpia</done>
</task>

<task type="auto">
  <name>Tarea 2: Alinear importaciones de observabilidad en routers y servicios core</name>
  <files>app/routers/whatsapp.py, app/services/ai_brain.py, app/services/memory_service.py</files>
  <action>
    1. En app/routers/whatsapp.py, reemplazar el try-except legado de langfuse.decorators con:
       from app.utils.observability import observe, langfuse_context
    2. En app/services/ai_brain.py, reemplazar la importación directa, la definición de _LangfuseContextShim y el mock del modulo en sys.modules con:
       from app.utils.observability import observe, langfuse_context
    3. En app/services/memory_service.py, línea 533, reemplazar "from langfuse.decorators import langfuse_context" con:
       from app.utils.observability import langfuse_context
  </action>
  <verify>.venv/bin/pytest tests/test_trace_propagation.py</verify>
  <done>Las importaciones core apuntan al adaptador local y pasan las pruebas de propagación estructural</done>
</task>

