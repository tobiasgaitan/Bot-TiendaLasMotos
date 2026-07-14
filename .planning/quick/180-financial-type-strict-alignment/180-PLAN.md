---
task: 180
name: financial-type-strict-alignment
description: Unify financial routing exclusively under active Firestore entity 'Brilla de Gases', raise explicit exceptions on gRPC or collection NoneType errors in financial_service, and enforce mathematically exact assertions in QA integration tests.
---

# Quick Task 180: Financial Type Strict Alignment

## Objective
Eradicate Crediorbe hardcoding from blind engagement/preventive paths, raise explicit exceptions for database/gRPC/collection errors, and enforce strict, mathematically exact assertions on calculated cuotas in tests.

## Tasks

<task type="auto">
  <name>Align AI Brain and Financial Service Core</name>
  <files>app/services/ai_brain.py, app/services/financial_service.py</files>
  <action>
    - Update `app/services/ai_brain.py` to remove any hardcoded "Crediorbe" fallback in `_calculate_payment_helper` and fallback paths, unifiying the default entity string under "Brilla de Gases".
    - In `app/services/financial_service.py`, refactor the `except` block of `calculate_payment`. If the exception is a Firestore/gRPC failure or collection NoneType error (e.g. `'NoneType' object has no attribute 'collection'`), raise an explicit exception to alert Langfuse rather than returning a fallback calculation with the default 1.95% rate.
  </action>
  <verify>
    .venv/bin/python3 -c "from app.services.financial_service import financial_service; import pytest; ... (test connection failure raises explicitly)"
  </verify>
  <done>
    `app/services/ai_brain.py` defaults to "Brilla de Gases". `financial_service.py` raises explicit exception on NoneType / gRPC errors.
  </done>
</task>

<task type="auto">
  <name>Rewrite Test Assertions and Autopsy Integration Mocks</name>
  <files>tests/test_pcc_ficha_tecnica.py, tests/test_agentic_loop_async.py</files>
  <action>
    - Update `tests/test_pcc_ficha_tecnica.py` to replace partial assertions (like the hardcoded mock cuota $250,000) with mathematically exact assertions matching physical calculations.
    - In `tests/test_agentic_loop_async.py`, remove the flat mock of `cuota_mensual: 350000.0` in `test_meta_payload_leak_prevention_and_bypass`, and replace it with a call utilizing the physical `financial_service` or config_service instance.
  </action>
  <verify>
    .venv/bin/pytest tests/test_pcc_ficha_tecnica.py tests/test_agentic_loop_async.py
  </verify>
  <done>
    Integration tests pass using the physical configuration logic and verify exact cuotas.
  </done>
</task>

<task type="auto">
  <name>Final Validation and Evacuation</name>
  <files>npx agent-cli eval</files>
  <action>
    - Execute `npx agent-cli eval` to certify the Coherence Score of 1.000.
    - Check the exact values: Cuota Venom 14 == $502.072 COP, Cuota Ntorq 125 == $487.395 COP.
  </action>
  <verify>
    npx agent-cli eval
  </verify>
  <done>
    100% test pass rate, exact math matches, zero silent failures.
  </done>
</task>

---
*Created: 2026-07-14*
