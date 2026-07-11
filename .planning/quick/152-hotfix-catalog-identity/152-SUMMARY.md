# Quick Task 152: Hotfix Catalog Identity Calibration — Summary

**Executed:** 2026-07-10
**Status:** Complete ✅
**Ticket:** BOT-PERF-IDENTITY-CALIBRATION-122

## Diagnóstico Real (Diferente al Ticket)

El ticket reportaba que `name_match` no estaba declarada en el scope del bucle.
**Verificación física (L494):** `name_match = False` SÍ está declarada. No hay `NameError`.

**Bug real identificado (de lógica, no de scope):** El `ratio` del Paso 3 (Fuzzy Name Match,
L553-555) era completamente independiente del flag `name_match`. Una query como `"rider"` → `"Raider"`
producía `ratio ≈ 0.91 (≥ 0.85)`, lo que agregaba `ratio * 60` puntos pero dejaba `name_match = False`,
bloqueando el boost de **+20,000** del Tier 1 de `_apply_scoring_adaptor`.

## What Was Done

1. **Fix quirúrgico en `search_items`**: Añadido bloque de "Fuzzy Identity Escalation" justo
   después del cálculo de `ratio`. Si `ratio >= 0.85 and not name_match`, se promueve
   `name_match = True` automáticamente — sin tocar `spelling_map` ni aliases manuales.

2. **Tests rígidos en `test_catalog_fuzzy.py`**: Dos nuevas aserciones:
   - `test_fuzzy_identity_escalation_rider`: Valida que `"rider"` retorna TVS Raider 125 primero.
   - `test_fuzzy_identity_escalation_raidr`: Cobertura fonética adicional para `"raidr"`.

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `app/services/catalog_service.py` | Modified | +14 líneas: bloque FUZZY IDENTITY ESCALATION en search_items (L557-570) |
| `tests/test_catalog_fuzzy.py` | Modified | +36 líneas: 2 nuevos test cases con aserciones rígidas |

## Verification

```
pytest tests/test_catalog_fuzzy.py -v
3 passed in 0.20s ✅

npx agent-cli eval
232 passed, 2 skipped — Score: 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```

## Commit

`807c15d` — `feat(quick-152): fuzzy identity escalation — promote name_match when ratio>=0.85 to activate +20k boost [BOT-PERF-IDENTITY-CALIBRATION-122]`

---
*Completed: 2026-07-10*
