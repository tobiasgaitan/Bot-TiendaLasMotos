---
task: 184
name: Financial Cascading Exact Parity
description: Re-architect and clean up financial calculations for exact Next.js parity on KYMCO Agility Fusion and remove Crediorbe references.
---

# Quick Task 184: Financial Cascading Exact Parity (Rev 2)

## Objective
Re-architect the Brilla de Gases calculations in `app/services/financial_service.py` and `app/services/config_service.py` to achieve exact parity with Next.js calculation rules for cylinder capacities <= 125 cc (registration cost strictly $780.000 COP) and ensure that no double-addition of registration occurs in WhatsApp simulation. Clean up the test assertions and verify all tests pass.

## Tasks

<task type="auto">
  <name>Refactor config_service to apply strict registration cost rule</name>
  <files>
    - [config_service.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/config_service.py)
  </files>
  <action>
    Update `get_registration_cost` in `app/services/config_service.py` to return `780000` directly if `cc` is not None and `math.floor(cc) <= 125`, bypassing any outdated values in Firestore for that range.
  </action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>get_registration_cost returns strictly 780000 for cc <= 125.</done>
</task>

<task type="auto">
  <name>Refactor financial_service calculation pipeline and WhatsApp simulation</name>
  <files>
    - [financial_service.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/financial_service.py)
  </files>
  <action>
    1. In `_generate_full_simulation_response`, subtract `reg_cost` from `precio_moto` to obtain `base_price` (to avoid double-adding registration fee), then pass `base_price` to `calculate_payment`.
    2. In `calculate_payment` phase 3: ensure that `cuota_mensual` is computed using Python's `round((P_final * factor) + seguro_vida + cuota_aval_mensual, 0)`.
    3. Audit file and confirm zero references to 'Crediorbe' or related logic.
  </action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>Simulation does not double-add registration, final calculation rounds correctly, and Crediorbe references are non-existent.</done>
</task>

<task type="auto">
  <name>Update tests and verify parity</name>
  <files>
    - [test_pcc_ficha_tecnica.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pcc_ficha_tecnica.py)
  </files>
  <action>
    1. Remove any static auto-adjust placeholders or hardcoded overrides in `tests/test_pcc_ficha_tecnica.py` if present.
    2. Verify `test_brilla_gases_real_firestore_cuotas` asserts exactly $550.469 COP for KYMCO Agility Fusion (124.6 cc, 1.017.900 COP init, 24m) and the mathematically correct cuota for TVS Sport 100 ELS (369.502 COP).
  </action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>All tests updated and passing cleanly.</done>
</task>

---
*Created: 2026-07-15*
