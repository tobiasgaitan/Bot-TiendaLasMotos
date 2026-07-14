---
task: 182
name: Financial Matrix Equalization
description: Refactor Fase 3 of financial_service.py to nullify flat seguro_vida for Brilla de Gases when uso_matriz is True.
---

# Quick Task 182: Financial Matrix Equalization

## Objective
Refactor the Phase 3 calculation in `app/services/financial_service.py` to omit the flat addition of `seguro_vida` for "Brilla de Gases" when `uso_matriz` is True, achieving exact parity with the frontend calculator.

## Tasks

<task type="auto">
  <name>Refactor financial_service.py</name>
  <files>app/services/financial_service.py</files>
  <action>Refactor the Phase 3 calculation to nullify flat seguro_vida for Brilla de Gases when using matrix factors (uso_matriz == True).</action>
  <verify>.venv/bin/python3 verify_independent_runtime.py</verify>
  <done>Victory Bet ABS cuota in WhatsApp is $689,901 COP net of seguro_vida (or what the live runtime yields net of seguro_vida).</done>
</task>

<task type="auto">
  <name>Align Test Assertions and Verify Suite</name>
  <files>tests/test_pcc_ficha_tecnica.py,tests/test_agentic_loop_async.py</files>
  <action>Update test assertions in the test suite to expect the new cuotas without flat seguro_vida for Brilla de Gases.</action>
  <verify>.venv/bin/pytest</verify>
  <done>All 257 tests pass successfully.</done>
</task>

---
*Created: 2026-07-14*
