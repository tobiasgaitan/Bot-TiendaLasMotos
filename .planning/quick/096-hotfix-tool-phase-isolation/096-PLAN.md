---
task: 096
name: hotfix-tool-phase-isolation
description: Aislar calculate_credit_score de PHASE_1_PROFILING para prevenir ejecución prematura del motor de crédito
---

# Quick Task 096: hotfix-tool-phase-isolation

## Objective
Remover `PHASE_1_PROFILING` del gate de inyección de `calculate_credit_score` en `_create_tools()` para que la herramienta de simulación financiera SOLO esté disponible en `PHASE_2_HABEAS_DATA` y `PHASE_3_CREDIT_PROFILING`.

## Tasks

<task type="auto">
  <name>Aislar credit_function del Phase 1</name>
  <files>app/services/ai_brain.py</files>
  <action>Remover "PHASE_1_PROFILING" del condicional de la línea 801. La herramienta credit_function solo se inyecta en PHASE_2_HABEAS_DATA y PHASE_3_CREDIT_PROFILING.</action>
  <verify>python3 -m pytest tests/ -x -q 2>&1 | tail -5</verify>
  <done>La condición dice `if phase in ["PHASE_2_HABEAS_DATA", "PHASE_3_CREDIT_PROFILING"]`</done>
</task>

<task type="auto">
  <name>Corregir test test_proactive_tools_without_habeas</name>
  <files>tests/test_proactive_credit.py</files>
  <action>El test actualmente espera credit en PHASE_1. Debe invertirse: assertNotIn para Phase 1, y agregar un nuevo test Phase 2 que sí lo contenga.</action>
  <verify>python3 -m pytest tests/test_proactive_credit.py -v 2>&1 | tail -10</verify>
  <done>Tests pasan confirmando aislamiento de herramientas por fase</done>
</task>

<task type="auto">
  <name>Verificar suite completa</name>
  <files>tests/</files>
  <action>Ejecutar pytest completo para verificar coherencia al 100%</action>
  <verify>python3 -m pytest tests/ -x -q 2>&1 | tail -5</verify>
  <done>Todos los tests PASSED con 0 failures</done>
</task>

---
*Created: 2026-07-02T17:37-05:00*
