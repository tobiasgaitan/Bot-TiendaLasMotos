# Quick Task 147: Hotfix Judge FAQ Bypass Secondary Trigger — Summary

**Executed:** 2026-07-10
**Status:** Complete
**Commit:** 36bcabc

## What Was Done

Aislado y eliminado el **disparador secundario** que causaba `human_help_requested=True` ante FAQs abstractas en producción (GCP Live), a pesar de que el bypass de `run_checker` en `ai_brain.py` estaba activo.

**Causa raíz física confirmada**: `JudgeService.analyze_response` operaba completamente ciego al contexto de FAQ, generando dos falsos positivos:
- **C1_VISUAL_LOCK**: `_mentions_bike()` usaba substring `"Sport"` que colisionaba con "soporte" en respuestas de FAQ.
- **C9_CITY_MISSING**: `_detect_credit_advance()` detectaba "requisitos" como avance de crédito.

El `except Exception` genérico en el router (L1168) también silenciaba errores de red del SDK de Gemini del JudgeService sin stack trace forense.

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `app/services/judge_service.py` | Modified | Añadido `is_faq_bypass: bool = False` a `analyze_response()`. Gate de cortocircuito antes de C1/C9. Hardening de `_mentions_bike()` con word-boundary regex. |
| `app/routers/whatsapp.py` | Modified | Import de `AgenticOrchestrator`. Evaluación de `run_checker` post-IA para extraer `bypass_strict`. Propagación como `is_faq_bypass` al Juez. `logger.exception` forense en except genérico. |
| `tests/test_pcc_ficha_tecnica.py` | Modified | +2 tests de regresión: `test_judge_service_faq_bypass` (3 casos, incluyendo C3 sigue activo) y `test_router_faq_bypass_propagation_to_judge` (4 pasos de integración end-to-end). |

## Verification

```
tests/test_pcc_ficha_tecnica.py::test_run_checker_faq_bypass         PASSED
tests/test_pcc_ficha_tecnica.py::test_judge_service_faq_bypass       PASSED
tests/test_pcc_ficha_tecnica.py::test_router_faq_bypass_propagation_to_judge PASSED
============================== 10 passed in 0.55s ==============================
```

**Cero regresiones. Suite completa: 10/10 PASSED.**

---
*Completed: 2026-07-10*
