---
task: 181
name: Financial Factor Alignment
description: Refactor Phase 3 of calculate_payment in financial_service.py to conditionalize cuota_aval_mensual and life insurance. If using matrix factor, omit the flat addition of cuota_aval_mensual to avoid double counting. Report why tests/test_pcc_ficha_tecnica.py passed accepting $534,745. Verify cuotas in runtime and success of the test suite.
---

# Quick Task 181: Financial Factor Alignment

## Objective
Refactor Phase 3 of `calculate_payment` in `app/services/financial_service.py` to prevent double-counting of `cuota_aval_mensual` when `uso_matriz` is True, report the autopsy of `tests/test_pcc_ficha_tecnica.py`, update tests, and verify correct WhatsApp-bound calculations for Victory Bet ABS and TVS Sport 100 ELS.

## Tasks

<task type="auto">
  <name>Refactor calculate_payment in app/services/financial_service.py</name>
  <files>
    <file>app/services/financial_service.py</file>
  </files>
  <action>Condition the addition of cuota_aval_mensual in Phase 3. If uso_matriz is True, omit adding cuota_aval_mensual to cuota_mensual.</action>
  <verify>Run local python check to verify target cuotas for Victory Bet ABS ($748.844) and TVS Sport 100 ELS ($364.825).</verify>
  <done>Phase 3 of calculate_payment has been refactored and local calculations match requested values exactly.</done>
</task>

<task type="auto">
  <name>Align test_pcc_ficha_tecnica.py assertions</name>
  <files>
    <file>tests/test_pcc_ficha_tecnica.py</file>
  </files>
  <action>Adjust mock assertions in tests/test_pcc_ficha_tecnica.py to match the updated calculations without double-counting (change $534,745 to $503,623).</action>
  <verify>pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>All tests in tests/test_pcc_ficha_tecnica.py pass in success.</done>
</task>

---
*Created: 2026-07-14*
