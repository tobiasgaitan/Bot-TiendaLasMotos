---
task: 177
name: Orchestrator Alignment
description: Refactorizar de forma quirúrgica el módulo app/services/ai_brain.py para dinamizar las variables de asignación financiera, removiendo Crediorbe de la simulación preventiva y sustituyendo por Brilla de Gases.
---

# Quick Task 177: Orchestrator Alignment

## Objective
Refactorizar `app/services/ai_brain.py` para sustituir de forma mandatoria la entidad "Crediorbe" por "Brilla de Gases" en las invocaciones de la simulación preventiva ciega (ausencia de Habeas Data), asegurando consistencia con las tasas y seguros del simulador oficial.

## Tasks

<task type="auto">
  <name>Surgically replace Crediorbe with Brilla de Gases in ai_brain.py simulation helper calls</name>
  <files>app/services/ai_brain.py</files>
  <action>Reemplazar 'entidad="Crediorbe"' por 'entidad="Brilla de Gases"' en las líneas de simulación ciega preventiva dentro de app/services/ai_brain.py (en las llamadas de calculate_payment_helper alrededor de las líneas 1664 y 1714).</action>
  <verify>.venv/bin/pytest</verify>
  <done>Las llamadas de simulación preventiva ciega utilizan "Brilla de Gases" en lugar de "Crediorbe".</done>
</task>
