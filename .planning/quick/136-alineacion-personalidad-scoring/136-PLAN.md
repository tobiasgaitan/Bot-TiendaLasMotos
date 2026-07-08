---
task: 136
name: alineacion_personalidad_scoring
description: Desalineación entre el prompt transaccional de Firestore y el archivo local app/core/personality.json. El JSON local carece de las 4 reglas duras de evaluación por score crediticio.
---

# Quick Task 136: alineacion_personalidad_scoring

## Objective
Surgically modify `app/core/personality.json` and `app/core/prompts.py` to integrate the 4 credit scoring copywriting actions under `<MATRIZ_DE_PERFILAMIENTO_ESTRICTA>`, replacing the simplified `CIERRE` line, maintaining sync with Firestore configuration.

## Tasks

<task type="auto">
  <name>Surgically update personality.json and prompts.py</name>
  <files>[app/core/personality.json, app/core/prompts.py]</files>
  <action>Replace the single CIERRE line in the `<MATRIZ_DE_PERFILAMIENTO_ESTRICTA>` block with the 4 credit scoring evaluation copywriting rules matching Firestore.</action>
  <verify>uv run pytest</verify>
  <done>The files are surgically updated and the test suite passes successfully.</done>
</task>

---
*Created: 2026-07-08*
