---
task: 184
name: Financial Cascading Exact Parity
description: Re-architect the Brilla de Gases calculations in financial_service.py to match Next.js exactly without static patches.
---

# Quick Task 184: Financial Cascading Exact Parity

## Objective
Re-architect the Brilla de Gases calculation sequence in `app/services/financial_service.py` to match Next.js parity exactly and eliminate all static patches. Align CC range lookups in `financial_service.py` and `config_service.py` using snap-to-lower-bound logic. Delete the old static test and add a real Firestore-backed integration test.

## Tasks

<task type="auto">
  <name>Align CC range matching in financial_service and config_service</name>
  <files>[app/services/financial_service.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/financial_service.py), [app/services/config_service.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/config_service.py)</files>
  <action>Refactor `_get_matrix_row` in `financial_service.py` and `get_registration_cost` in `config_service.py` to snap CC values to the correct row using the Next.js generic displacement lookup algorithm (displacement >= minCC, sorted descending by minCC).</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>Displacement range lookup uses generic candidate minCC snapping logic.</done>
</task>

<task type="auto">
  <name>Refactor Brilla de Gases calculation sequence</name>
  <files>[app/services/financial_service.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/financial_service.py)</files>
  <action>Implement the Next.js cascading quote calculation logic for "Brilla de Gases" in `calculate_payment`, reconstructing the catalog price (assetPrice = precio + reg_cost), calculating `p1_base = assetPrice - inicial + docsTotal`, calculating `vGestion` and `vCobertura`, setting `P_final = p2_intermediate + vCobertura`, calculating `basePmt = p2_intermediate * factor`, and summing `basePmt + seguro_vida + (vCobertura / 12)` before rounding. Remove all static hardcoded patches.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>All calculations are performed dynamically matching Next.js, and static patches are deleted.</done>
</task>

<task type="auto">
  <name>Update tests and verify parity</name>
  <files>[tests/test_pcc_ficha_tecnica.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pcc_ficha_tecnica.py)</files>
  <action>Delete the static test `test_brilla_gases_real_firestore_cuotas` and write a real integration test that runs `CerebroIA()._calculate_payment_helper` in `TEST_MODE=false` with the physical Firestore backend, asserting exactly `$748.844 COP` for Victory Bet ABS (initial = 1,395,000) and `$364.825 COP` for TVS Sport 100 ELS (initial = 665,000) with zero tolerance.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>Real integration test passes with 0 tolerance.</done>
</task>

---
*Created: 2026-07-15*
