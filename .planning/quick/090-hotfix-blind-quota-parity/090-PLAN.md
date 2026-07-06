---
task: 090
name: hotfix-blind-quota-parity
description: Falso positivo en test unitario y fallo de formato en Meta debido a código duro en la rama ciega de ai_brain.py.
---

# Quick Task 090: hotfix-blind-quota-parity

## Objective
Corregir quirúrgicamente la rama sin consentimiento en calculate_credit_score de ai_brain.py y alinear las aserciones correspondientes en tests/test_agentic_loop_async.py.

## Tasks

<task type="auto">
  <name>Rediseñar rama sin consentimiento en calculate_credit_score</name>
  <files>app/services/ai_brain.py</files>
  <action>Corregir llamada al simulador financiero con inicial=m_price * 0.10 y formatear credit_res con la cadena exacta de copywriting del Paso 3.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>La llamada calcula cuotas con el 10% de inicial y devuelve la cadena esperada.</done>
</task>

<task type="auto">
  <name>Alinear aserciones en test_agentic_loop_async.py</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>Corregir las aserciones para verificar el patrón exacto del 10% de inicial y prohibir la cadena 'sin cuota inicial'.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>Todas las pruebas unitarias pasan exitosamente.</done>
</task>

---
*Created: 2026-07-02*
