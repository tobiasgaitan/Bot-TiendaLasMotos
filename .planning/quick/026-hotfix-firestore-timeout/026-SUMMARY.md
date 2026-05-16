# Quick Task 026: Hotfix Firestore Timeout — Summary

**Executed:** 2026-05-15
**Status:** Complete

## What Was Done
Se ha resuelto el problema de timeout en escrituras asíncronas de Firestore durante ráfagas de webhooks de estado. Se instanció `self._status_semaphore = asyncio.Semaphore(5)` en el constructor de `MemoryService` y se envolvió el cuerpo del método `update_whatsapp_status` en un bloque `async with self._status_semaphore:` para limitar la concurrencia. También se ajustó la aserción de `test_judge_one_question_rule` para que coincida con la nueva validación `C5_TWO_QUESTION_RULE`.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| app/services/memory_service.py | Modified | Se añadió el semáforo y se aplicó al interceptor `update_whatsapp_status` |
| tests/test_judge_service.py | Modified | Se corrigió el error C5_ONE_QUESTION_RULE por C5_TWO_QUESTION_RULE en el unit test |

## Verification
Se ejecutó satisfactoriamente `uv run pytest`, logrando que todos los contratos y pruebas (incluyendo `test_memory_merge`, `test_reset_flow` y `test_read_asymmetry`) pasen exitosamente con 74 pasados y 2 omitidos, garantizando una compilación limpia y ausencia de regresiones.

---
*Completed: 2026-05-15*
