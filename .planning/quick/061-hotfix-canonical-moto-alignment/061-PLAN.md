---
task: 061
name: hotfix_canonical_moto_alignment
description: Remoción de las variables redundantes moto_ofrecida y moto_aceptada en el pipeline de extracción de ai_brain.py para unificar el flujo multirreferencia sobre la llave canónica certificada moto_interest.
---

# Quick Task 061: hotfix_canonical_moto_alignment

## Objective
Remover las variables redundantes `moto_ofrecida` y `moto_aceptada` en el pipeline de extracción de `ai_brain.py` y unificar el flujo multirreferencia sobre la llave canónica certificada `moto_interest`. Asegurar que el campo `'required'` dentro del sub-esquema `'extracted'` contenga exactamente `['nombre', 'ciudad', 'moto_interest', 'habeas_data_accepted']`.

## Tasks

<task type="auto">
  <name>Refactorizar EXTRACTION_SCHEMA y Prompt de Extracción</name>
  <files>[app/services/ai_brain.py, tests/test_pii_high_fidelity.py]</files>
  <action>Modificar app/services/ai_brain.py para eliminar 'moto_ofrecida' y 'moto_aceptada' del esquema y las reglas del prompt, añadir 'required' a 'extracted', y actualizar tests/test_pii_high_fidelity.py para adaptarse al nuevo esquema.</action>
  <verify>npx agent-cli eval</verify>
  <done>El Coherence Score se mantiene en 1.000 (135/135 tests passed) sin regresiones.</done>
</task>

---
*Created: 2026-06-24*
