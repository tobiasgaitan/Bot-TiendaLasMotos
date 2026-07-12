---
task: 164
name: Corrección de firmas Langfuse v4
description: Alinear de forma quirúrgica el módulo de observabilidad y las inyecciones de trazas dentro de app/routers/whatsapp.py para adaptarlos a las especificaciones y firmas nativas del SDK de Langfuse v4
---

# Quick Task 164: Corrección de firmas Langfuse v4

## Objective
Alinear de forma quirúrgica el módulo de observabilidad y las inyecciones de trazas dentro de app/routers/whatsapp.py para adaptarlos a las especificaciones y firmas nativas del SDK de Langfuse v4, erradicando los imports de langfuse.decorators y usando el adaptador unificado de observabilidad.

## Tasks

<task type="auto">
  <name>Limpieza de imports obsoletos de langfuse.decorators en whatsapp.py</name>
  <files>app/routers/whatsapp.py</files>
  <action>Eliminar todas las referencias a 'from langfuse.decorators import langfuse_context' en app/routers/whatsapp.py, reemplazándolas por el uso directo del objeto langfuse_context importado a nivel de módulo desde app.utils.observability.</action>
  <verify>.venv/bin/python3 -c "import app.routers.whatsapp; print('Importación del enrutador de WhatsApp exitosa sin excepciones de Langfuse')"</verify>
  <done>El enrutador se importa sin ModuleNotFoundError y no contiene referencias a langfuse.decorators.</done>
</task>

<task type="auto">
  <name>Verificar tests unitarios y de integración</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>Ejecutar pytest en la suite tests/test_agentic_loop_async.py, tests/test_trace_propagation.py y tests/test_observability_gate.py para validar la correcta propagación de trazas.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py tests/test_trace_propagation.py tests/test_observability_gate.py</verify>
  <done>Los tests pasan exitosamente sin errores.</done>
</task>

---
*Created: 2026-07-12*
