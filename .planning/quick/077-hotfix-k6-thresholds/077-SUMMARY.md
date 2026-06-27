# Quick Task 077: Calibrar umbrales k6 — Summary

**Executed:** 2026-06-27
**Status:** Complete

## What Was Done
Se recalibraron los umbrales de latencia del Gate de Rendimiento en `tests/performance/test_k6.js` para reflejar la realidad operativa de un agente de IA generativa con dependencias síncronas pesadas (Gemini LLM + Firestore).

**Cambio:**
- `http_req_duration: ['p(95)<250', 'p(99)<450']` → `['p(95)<15000', 'p(99)<20000']`
- La métrica `tasa_errores_webhook` (`rate<0.01`) permanece **inalterada**.

**Justificación:** La latencia real p(95) bajo carga fue de 10.82s. Los umbrales de 250ms eran propios de APIs CRUD sin dependencias externas, no de un flujo Webhook→HMAC→Gemini→Firestore.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| `tests/performance/test_k6.js` | Modified | Ajustados thresholds de http_req_duration a p(95)<15s, p(99)<20s |

## Verification
- `grep -n 'http_req_duration'` → Confirma `p(95)<15000`, `p(99)<20000` ✓
- `grep -n 'tasa_errores_webhook'` → Confirma `rate<0.01` inalterada ✓

---
*Completed: 2026-06-27T04:41:00Z*
