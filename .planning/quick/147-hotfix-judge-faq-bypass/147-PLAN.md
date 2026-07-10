---
task: 147
name: Hotfix Judge FAQ Bypass Secondary Trigger
description: Aislar disparador secundario de human_help_requested=True en JudgeService al evaluar FAQs abstractas
---

# Quick Task 147: Hotfix Judge FAQ Bypass Secondary Trigger

## Objective
Eliminar el disparador secundario que causa `human_help_requested=True` en producción ante FAQs abstractas post-reset. El `JudgeService.analyze_response` generaba falsos positivos en C1_VISUAL_LOCK ("soporte"→"Sport") y C9_CITY_MISSING ("requisitos"→crédito) independientemente del bypass activo en `run_checker`.

## Tasks

<task type="auto">
  <name>Fix 1 — Judge Service FAQ Bypass Gate</name>
  <files>app/services/judge_service.py</files>
  <action>Añadir parámetro is_faq_bypass a analyze_response(). Cortocircuitar C1/C9 cuando bypass activo. Hardening de _mentions_bike() con word-boundary regex.</action>
  <verify>pytest tests/test_pcc_ficha_tecnica.py::test_judge_service_faq_bypass -v</verify>
  <done>JudgeService aprueba FAQs con "Sport"/"requisitos" cuando is_faq_bypass=True. C3 sigue activo.</done>
</task>

<task type="auto">
  <name>Fix 2 — Router FAQ Bypass Propagation</name>
  <files>app/routers/whatsapp.py</files>
  <action>Importar AgenticOrchestrator. Evaluar run_checker post-IA antes del Juez. Propagar bypass_strict como is_faq_bypass. logger.exception forense en except genérico.</action>
  <verify>pytest tests/test_pcc_ficha_tecnica.py::test_router_faq_bypass_propagation_to_judge -v</verify>
  <done>Router propaga is_faq_bypass=True al Juez cuando run_checker detecta FAQ pura.</done>
</task>

<task type="auto">
  <name>Fix 3 — Regression Tests Suite</name>
  <files>tests/test_pcc_ficha_tecnica.py</files>
  <action>Añadir test_judge_service_faq_bypass (3 casos) y test_router_faq_bypass_propagation_to_judge (4 pasos).</action>
  <verify>pytest tests/test_pcc_ficha_tecnica.py -k "faq_bypass" -v</verify>
  <done>Todos los nuevos tests verdes. Suite completa sin regresiones.</done>
</task>

---
*Created: 2026-07-10*
