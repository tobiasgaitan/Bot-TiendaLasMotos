---
task: 050
name: hotfix-ai-brain-null
description: AttributeError en app/services/ai_brain.py línea 816 debido a desreferenciación insegura de prospect_data como None Type durante pruebas aisladas o Cold Starts.
---

# Quick Task 050: hotfix-ai-brain-null

## Objective
Fix AttributeError on line 816 in app/services/ai_brain.py due to unsafe dereferencing of prospect_data when it is None. Add a unit test to assert the behavior and verify it runs cleanly without prospect_data arguments in the local inference script.

## Tasks

<task type="auto">
  <name>Modificar app/services/ai_brain.py</name>
  <files>[app/services/ai_brain.py]</files>
  <action>Modificar la línea 816 de app/services/ai_brain.py para usar data = prospect_data or {} de modo que prospect_data no se desreferencie como None.</action>
  <verify>uv run pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>Se asigna data = prospect_data or {} y se usan sus llaves de manera segura.</done>
</task>

<task type="auto">
  <name>Crear test unitario para prospect_data None y verificar Ficha Tecnica</name>
  <files>[tests/test_bot_bug_109.py]</files>
  <action>Crear el test unitario tests/test_bot_bug_109.py que verifique que pensar_respuesta funciona correctamente cuando prospect_data es None, e incluya aserciones para evitar la mutación de llaves silenciosa o strings vacíos.</action>
  <verify>uv run pytest tests/test_bot_bug_109.py</verify>
  <done>El test pasa de forma exitosa y valida la corrección.</done>
</task>

<task type="auto">
  <name>Modificar y ejecutar simulador_ia.py sin prospect_data</name>
  <files>[simulador_ia.py]</files>
  <action>Modificar simulador_ia.py para llamar a pensar_respuesta sin pasar prospect_data (dejando que tome el valor por defecto None) y ejecutarlo de manera limpia.</action>
  <verify>uv run python simulador_ia.py</verify>
  <done>La ejecución de simulador_ia.py es exitosa y no lanza ningún AttributeError.</done>
</task>
