---
task: 184
name: Financial Cascading Exact Parity
description: Re-architect the Brilla de Gases calculations in financial_service.py to match Next.js exactly without static patches.
---

# Quick Task 184: Financial Cascading Exact Parity

## Objective
Re-architect the Brilla de Gases calculation sequence in `app/services/financial_service.py` to match Next.js parity exactly. Implement the rule: if cylinder capacity (moto_cc) <= 125 cc, registration cost is strictly $780.000 COP, otherwise take it from config/matrix. Clean up the test suite to assert exactly $550.469 COP for KYMCO Agility Fusion.

## Tasks

<task type="auto">
  <name>Refactor Brilla de Gases calculation sequence</name>
  <files>[app/services/financial_service.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/financial_service.py)</files>
  <action>Refactor the Brilla de Gases calculations in `calculate_payment` to use strictly $780.000 COP for registration when `moto_cc <= 125`, and apply the exact Next.js sequence: `assetPrice = precio + reg_cost`, `p1_base = assetPrice - inicial + docsTotal`, `vGestion = js_round(p1_base * (brillaManagementRate / 100))`, `p2_intermediate = p1_base + vGestion`, `vCobertura = js_round(p2_intermediate * (coverageRate / 100))`, `cuota_aval_mensual = js_round(vCobertura / 12)`, `P_final = p2_intermediate`, and `cuota_mensual = js_round((P_final * factor) + seguro_vida + cuota_aval_mensual)`.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>Next.js formula sequence implemented cleanly and registration cost rule applied strictly.</done>
</task>

<task type="auto">
  <name>Update tests and verify parity</name>
  <files>[tests/test_pcc_ficha_tecnica.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pcc_ficha_tecnica.py)</files>
  <action>Update `test_brilla_gases_real_firestore_cuotas` in `tests/test_pcc_ficha_tecnica.py` to assert exactly $550.469 COP for KYMCO Agility Fusion (inicial = 1.017.900 COP), and update TVS Sport 100 ELS to $369.501 COP. Update bypass/short-circuit test assertions to $581,506.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>All tests updated and passing cleanly.</done>
</task>

---
*Created: 2026-07-15*
