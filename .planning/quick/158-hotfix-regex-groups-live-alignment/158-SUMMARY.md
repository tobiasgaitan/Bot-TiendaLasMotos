# Quick Task 158: Hotfix Regex Groups Live Alignment — Summary

**Executed:** 2026-07-11
**Status:** Complete

## What Was Done
- Replaced the unified `image_pattern` regex in [whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py) with independent, robust patterns (`markdown_pattern` and `legacy_pattern`). This prevents `re.findall` from returning tuples of empty strings from multiple alternative capture groups and fixes subsequent string interpolation and parsing.
- Refactored `markdown_pattern` to use `[\s\S]*?` and `\s*` to correctly match and strip Markdown images with control characters, spaces, or newlines injected inside brackets or between brackets and parentheses.
- Updated the regression test `test_whatsapp_image_url_with_complex_query_params_regression` in [test_agentic_loop_async.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_agentic_loop_async.py) to patch `httpx.AsyncClient.post` and assert the exact JSON payload format sent to Meta.
- Added rigid assertions to verify that the message type changes to `"image"`, the URL extracts cleanly with its extensive query params, and the cleaned caption contains no remaining brackets (`[` or `]`) or raw Firebase Storage URLs.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/routers/whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py) | Modified | Replaced unified image pattern regex with independent Markdown/legacy patterns. |
| [tests/test_agentic_loop_async.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_agentic_loop_async.py) | Modified | Refactored mock logic to intercept `httpx.AsyncClient.post` and asserted clean caption/type payload parameters. |

## Verification
Executed the test suite regression test successfully:
```bash
.venv/bin/pytest tests/test_agentic_loop_async.py -vv -s
```
Output:
- All 21 tests passed (including `test_whatsapp_image_url_with_complex_query_params_regression`).

---
*Completed: 2026-07-11*
