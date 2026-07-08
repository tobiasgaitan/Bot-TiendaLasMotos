---
task: 137
name: hotfix_scoring_api_alignment
description: Fallo de importación (ImportError) en la ruta crítica del webhook provocado por invocación huérfana de 'evaluate_profile' sobre app/services/scoring_service.py.
---

# Quick Task 137: hotfix_scoring_api_alignment

## Objective
Resolver el fallo de importación y la invocación huérfana del motor financiero, permitiendo la conmutación dinámica y síncrona/bloqueante usando await hacia `calculate_score` y `determine_strategy` en `ai_brain.py` respetando las llaves del `EXTRACTION_SCHEMA` de Firestore, y exponiendo adecuadamente los servicios en `app/services/__init__.py`.

## Tasks

<task type="auto">
  <name>Exponer servicios en el init de services</name>
  <files>
    <file>app/services/__init__.py</file>
  </files>
  <action>Exponer financial_service y scoring_service en app/services/__init__.py para evitar fallos de importación.</action>
  <verify>uv run pytest tests/test_agentic_loop_async.py</verify>
  <done>Los servicios se exportan correctamente y las pruebas pasan.</done>
</task>

<task type="auto">
  <name>Actualizar llamada en ai_brain.py para usar calculate_score/determine_strategy con await</name>
  <files>
    <file>app/services/ai_brain.py</file>
  </files>
  <action>Modificar ai_brain.py para conmutar entre la llamada legacy (evaluate_profile) y el nuevo mapeo síncrono/bloqueante con await (asyncio.to_thread) hacia calculate_score y determine_strategy, alineando con las llaves de EXTRACTION_SCHEMA de Firestore.</action>
  <verify>uv run pytest tests/test_agentic_loop_async.py tests/test_brilla_conmutacion.py</verify>
  <done>Las pruebas pasan correctamente y el comportamiento es 100% retrocompatible y robusto.</done>
</task>

---
*Created: 2026-07-08*
