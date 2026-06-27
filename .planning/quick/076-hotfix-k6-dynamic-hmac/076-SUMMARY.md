# Quick Task 076: hotfix-k6-dynamic-hmac — Summary

**Executed:** 2026-06-27
**Status:** Complete

## What Was Done
Reemplazada la firma HMAC estática hardcodeada (`mocked_k6_load_test_signature_pass_bypass`) en `tests/performance/test_k6.js` por un cálculo dinámico usando el módulo nativo `k6/crypto`. Cada iteración del test ahora computa `crypto.hmac('sha256', secret, payload, 'hex')` sobre el body JSON serializado, garantizando que la firma enviada en `X-Hub-Signature-256` coincida con la que el servidor espera validar via `hmac.compare_digest()`.

## Causa Raíz
El payload de k6 contiene `Math.random()` para generar teléfonos y message IDs únicos, pero la firma era estática. El router de WhatsApp (`whatsapp.py` L159-167) calcula el HMAC esperado sobre el body crudo recibido y lo compara. Como el body cambia en cada iteración pero la firma no, el resultado siempre era un HTTP 401 (Signature mismatch).

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| `tests/performance/test_k6.js` | Modified | Import `k6/crypto`, captura `WHATSAPP_APP_SECRET` con fallback, calcula HMAC dinámico, elimina hardcode |

## Verification
- `grep -n "crypto.hmac"` → Encontrado en línea 41 ✓
- `grep -n "mocked_k6_load_test_signature_pass_bypass"` → No encontrado (exit 1) ✓
- QA Gate local: 167/167 tests passed, Score 1.000 ✓
- Push exitoso a `origin/fix/pipeline-qa-gate-073` → commit `2fc3e2d` ✓

---
*Completed: 2026-06-27*
