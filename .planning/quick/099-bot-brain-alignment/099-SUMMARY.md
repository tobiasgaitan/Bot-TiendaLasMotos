# Quick Task 099: Bot Brain Alignment — Summary

**Executed:** 2026-07-03
**Status:** Complete

## What Was Done

### 1. Synonym Injection (Tubería Semántica)
- Added `get_catalog_aliases()` to `config_service.py` that flattens Firestore's indexed-dict format (`{"0": "Señoritera"}`) into proper lists.
- Injected `<diccionario_sinonimos_regionales>` XML block into `ai_brain.py` full_prompt to give the LLM awareness of regional colloquialisms.

### 2. Prompt-Tool Desync Purge
- In `_generate_with_retry_async()`, added detection of whether `calculate_credit_score` is in the current toolset.
- If absent (PHASE_1), `REGLA DE CREDITO CIEGO` is dynamically purged via `re.sub()` and replaced with an explicit "tool not available" instruction.

### 3. Hard-Cap on Tool Calls per Turn
- Added `MAX_TOOL_CALLS_PER_TURN = 2` constant in the tool execution loop.
- If the LLM dispatches more than 2 function_calls in a single turn, excess calls are truncated with forensic logging.

### 4. Cloud Tasks TTL
- Added `dispatch_deadline=duration_pb2.Duration(seconds=120)` to the task payload in `_enqueue_cloud_task()`.
- Documented resilience contract: task-processor SHOULD return HTTP 200 on inference failures.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| app/services/config_service.py | Modified | Added `get_catalog_aliases()` method |
| app/services/ai_brain.py | Modified | Synonym XML injection, credit-blind purge, hard-cap |
| app/routers/whatsapp.py | Modified | `dispatch_deadline=120s` on Cloud Tasks |

## Verification
- 168/169 tests PASSED. 
- 1 pre-existing failure (`test_eventloop_latency.py::test_webhook_response_within_meta_window`) confirmed as pre-existing regression unrelated to this change (missing `/tmp/fake-key.json` GCP mock).
- Coherence Score: Maintained at baseline (168 PASSED, 0 new regressions).

---
*Completed: 2026-07-03*
