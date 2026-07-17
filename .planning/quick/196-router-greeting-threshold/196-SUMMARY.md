# Quick Task 196: Router Greeting Threshold Hotfix — Summary

**Executed:** 2026-07-17
**Status:** Complete

## What Was Done
1. **Refactored `_evaluate_skip_greeting` in `app/routers/whatsapp.py`**:
   - Completely removed `is_metadata_only` and any dependency on `ai_summary`.
   - Set `newly_created` check exclusively using Firestore physical document existence (`exists = bool(prospect_data and prospect_data.get("exists", False))`).
   - Sliced `legitimate_user_messages[:-1]` to cleanly extract `past_user_messages` when the current message of the turn has already been appended (`current_message_saved=True`), avoiding any self-greeting loops on out-of-catalog errors.
   - Evaluated the 12-hour window (`diff_seconds < 43200`) strictly on the timestamp of the last message in `past_user_messages`.
2. **Aligned AI Brain in `app/services/ai_brain.py`**:
   - Evaluated `has_no_legitimate_history` based exclusively on prior text user messages in `history` (removing `has_ai_summary` check).
   - Removed all assignments and modifications mutating `skip_greeting`, strictly respecting and inheriting the parameter calculated by the router.
3. **Added Test Coverage**:
   - Added unit test `test_consecutive_out_of_catalog_query_suppresses_greeting` in `tests/test_identity_legal_gate.py` to ensure greeting suppression is respected under consecutive out-of-catalog searches.
   - Updated `test_perimeter_short_tokens_and_greeting_bypass` in `tests/test_agentic_loop_async.py` to reflect the new strict routing-inheritance model.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/routers/whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py) | Modified | Removed `is_metadata_only`, calculated `newly_created` correctly, sliced out current message from past history. |
| [app/services/ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py) | Modified | Removed `skip_greeting` mutations, aligned `has_no_legitimate_history` to `history`. |
| [tests/test_identity_legal_gate.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_identity_legal_gate.py) | Modified | Added `test_consecutive_out_of_catalog_query_suppresses_greeting`. |
| [tests/test_agentic_loop_async.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_agentic_loop_async.py) | Modified | Updated `test_perimeter_short_tokens_and_greeting_bypass` to align with the new strict routing-inheritance model. |

## Verification
- Ran the modified identity gate tests:
  - `.venv/bin/pytest tests/test_identity_legal_gate.py` passed cleanly (13/13).
- Ran the full test suite and eval gate:
  - `npx agent-cli eval` completed successfully:
    - 271 passed, 0 failed.
    - **Coherence Score: 1.000** (authorized for deployment).

---
*Completed: 2026-07-17*
