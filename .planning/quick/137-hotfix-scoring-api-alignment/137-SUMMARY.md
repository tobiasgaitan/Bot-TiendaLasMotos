# Quick Task 137: hotfix_scoring_api_alignment — Summary

**Executed:** 2026-07-08
**Status:** Complete

## What Was Done
- Expose `financial_service` and `scoring_service` explicitly in `app/services/__init__.py` to prevent import issues in routers/webhooks.
- Updated `pensar_respuesta` in `app/services/ai_brain.py` to:
  - Extract values using exact `EXTRACTION_SCHEMA` key conventions.
  - Route `calculate_credit_score` tool calls directly to `scoring_service` by invoking `calculate_score` and `determine_strategy` inside an `asyncio.to_thread` block (synchronously/blocking).
  - Defined a helper method `_calculate_payment_helper` to delegate the payment simulation calls safely, falling back to the canonical `financial_service` instance if the injected motor lacks a `calculate_payment` method.
- Added a robust unit test `test_cerebro_ia_scoring_service_direct_alignment` in `tests/test_agentic_loop_async.py` verifying direct routing, correct score calculation, and fallback simulation.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/services/__init__.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/__init__.py) | Modified | Expose `financial_service` and `scoring_service`. |
| [app/services/ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py) | Modified | Define `_calculate_payment_helper` and update `calculate_credit_score` tool logic to use `calculate_score`/`determine_strategy` with `await` and the helper. |
| [tests/test_agentic_loop_async.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_agentic_loop_async.py) | Modified | Add `test_cerebro_ia_scoring_service_direct_alignment` unit test. |

## Verification
- Ran the new unit test specifically: `uv run pytest tests/test_agentic_loop_async.py -k test_cerebro_ia_scoring_service_direct_alignment` -> PASSED.
- Ran all unit tests: `uv run pytest` -> 218 passed.
- Ran coherence check: `npx agent-cli eval` -> Coherence Score = 1.000 (PASSED).

---
*Completed: 2026-07-08*
