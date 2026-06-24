---
task: 060
name: hotfix_gate_legal
description: Falso positivo en test_fallback_price_parsing. Falta aserción que garantice el bloqueo del motor financiero calculate_credit_score si el flag habeas_data_accepted está ausente o en False.
---

# Quick Task 060: hotfix_gate_legal

## Objective
Garantizar el bloqueo del motor financiero `calculate_credit_score` si el flag `habeas_data_accepted` está ausente o en False. Inyectar una prueba de caracterización en `tests/test_pcc_ficha_tecnica.py` que valide esta intercepción y desvío al flujo de legalización antes de tocar el simulador.

## Tasks

<task type="auto">
  <name>Implementar bloqueo de calculate_credit_score por Habeas Data</name>
  <files>[app/services/ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py)</files>
  <action>Validar que 'habeas_data_accepted' sea True en prospect_data antes de invocar el motor financiero. Si no lo es, lanzar PermissionError.</action>
  <verify>.venv/bin/pytest tests/test_perf_45.py</verify>
  <done>La validación se ejecuta y los tests existentes no se rompen (tras ajustar sus prospect_data).</done>
</task>

<task type="auto">
  <name>Actualizar prospect_data en tests existentes</name>
  <files>[tests/test_perf_45.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_perf_45.py), [tests/test_brilla_conmutacion.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_brilla_conmutacion.py), [tests/test_proactive_credit.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_proactive_credit.py), [tests/test_agentic_loop_async.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_agentic_loop_async.py), [tests/test_habeas_data_regression.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_habeas_data_regression.py), [tests/test_identity_legal_gate.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_identity_legal_gate.py), [tests/test_competitor_protocol.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_competitor_protocol.py)</files>
  <action>Asegurar que los tests que esperan que calculate_credit_score simule una cuota exitosa incluyan 'habeas_data_accepted': True en su prospect_data.</action>
  <verify>.venv/bin/pytest tests/</verify>
  <done>Todos los tests existentes pasan correctamente con el bloqueo activo.</done>
</task>

<task type="auto">
  <name>Inyectar prueba de caracterización en test_pcc_ficha_tecnica.py</name>
  <files>[tests/test_pcc_ficha_tecnica.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pcc_ficha_tecnica.py)</files>
  <action>Añadir test_habeas_data_gate_before_credit_score que verifique que con habeas_data_accepted = False/ausente, calculate_credit_score lance PermissionError/se bloquee antes de tocar evaluate_profile/calculate_payment, y que contenga la aserción de contenido requerida.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>La prueba de caracterización valida el bloqueo y pasa exitosamente.</done>
</task>

---
*Created: 2026-06-23*
