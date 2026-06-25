# Quick Task 067: correccion_contratos_pruebas_firestore — Summary

**Executed:** 2026-06-25
**Status:** Complete

## What Was Done
1. **Canonical 'forma_pago' Alignment:** Updated `tests/test_agentic_loop_async.py` (line 89) to change `'forma_pago': 'credito'` to the canonical database value `'Crédito - 0 inicial'`.
2. **Strict Keys Parametrization in Financial Service:** Modified `app/services/financial_service.py` to extract `'ocupacion'` and `'datacredito'` prioritizing the strict Firestore keys from `EXTRACTION_SCHEMA` over legacy keys.
3. **Aligned Tests to Strict Keys:** Updated all invocations of `evaluate_profile` in `tests/test_agentic_loop_async.py` to pass the strict parameter keys `'ocupacion'` and `'datacredito'`.
4. **PCC Pro Guardrail Alert Enforcement:** Updated `tests/test_pcc_ficha_tecnica.py` in both Escenario 2 and Escenario B to assert that missing or mutated catalog keys (such as `summary` or `price`) trigger the `PRICE_CONSISTENCY_CHECK` guardrail failure in `AgenticOrchestrator().run_checker`.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/services/financial_service.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/financial_service.py) | Modified | Prioritized strict keys `ocupacion` and `datacredito` in profile evaluation. |
| [tests/test_agentic_loop_async.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_agentic_loop_async.py) | Modified | Changed 'forma_pago' mock value to 'Crédito - 0 inicial' and aligned parameters to strict keys. |
| [tests/test_pcc_ficha_tecnica.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pcc_ficha_tecnica.py) | Modified | Asserted that key mutation activates the PCC Pro guardrail validation failure. |

## Verification
- Verified by running the target test files: `pytest tests/test_agentic_loop_async.py tests/test_pcc_ficha_tecnica.py` (passed).
- Verified by running the entire pytest suite: `pytest` (156 passed, 2 skipped).
- Verified using `npx agent-cli eval` returning a perfect Coherence Score of **1.000** (threshold: 0.9).

---
*Completed: 2026-06-25*
