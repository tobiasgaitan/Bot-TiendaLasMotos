# Quick Task 171: Hotfix Webhook Idempotency Lock — Summary

**Executed:** 2026-07-12
**Status:** Complete

## What Was Done
Implemented a synchronous idempotency guardrail in the WhatsApp webhook router boundary (`app/routers/whatsapp.py`) to prevent duplicate payloads from webhook retry storms from being enqueued asynchronously. 

1. **MessageBuffer Refactoring**: Added `self._added_wamids` to decouple registration tracking from text buffering. This prevents the actual background task (`add_message`) from throwing false duplicate warnings for tasks that were successfully registered in the router beforehand.
2. **Synchronous Webhook Boundary Check**: Updated `webhook_handler` in `app/routers/whatsapp.py` to call `await message_buffer.register_wamid(...)` blocking/synchronously using the lock mechanism. Any concurrent duplicate request with the same WAMID is immediately short-circuited and ignored with `{"status": "ignored", "procesado": False}` before enqueuing to background or Cloud tasks.
3. **Updated Existing Tests**: Updated `tests/test_webhook_sync_block.py` where the message buffer mock was not prepared for an async `register_wamid` call.
4. **Created Concurrency Characterization Tests**: Created `tests/test_router_concurrency.py` containing `test_concurrent_webhook_idempotency` to simulate concurrent requests with identical WAMIDs and assert only one executes while the duplicate is immediately rejected.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/services/message_buffer.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/message_buffer.py) | Modified | Added `_added_wamids` set tracking and adjusted `add_message` check. |
| [app/routers/whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py) | Modified | Called `register_wamid` synchronously at the router boundary. |
| [tests/test_webhook_sync_block.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_webhook_sync_block.py) | Modified | Adjusted mocked `MessageBuffer` to support async `register_wamid`. |
| [tests/test_router_concurrency.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_router_concurrency.py) | Created | Characterization test to evaluate WAMID idempotency under concurrency. |

## Verification
- Running `pytest tests/test_router_concurrency.py` passed successfully.
- Running the full pytest test suite (254 tests) passed successfully.

```bash
======================== 254 passed, 2 skipped in 8.55s ========================
```

---
*Completed: 2026-07-12*
