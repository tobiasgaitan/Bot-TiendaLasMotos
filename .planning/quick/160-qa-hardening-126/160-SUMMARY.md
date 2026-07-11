# Quick Task 160: QA Hardening — BOT-QA-HARDENING-126 — Summary

**Executed:** 2026-07-11
**Status:** Complete ✅
**Eval Score:** 1.000 (241/241 passed)

## What Was Done

Eliminación de 3 falsos positivos críticos en la suite de pruebas que enmascaran fallos de runtime real:

### Tarea 1 — KeyError duro en `search_catalog` al detectar `summary=None` explícito
- **Archivo modificado:** `app/services/catalog_service.py`
- Se reemplazó el `.get('summary')` silencioso por un guard explícito que distingue entre:
  - Llave **ausente** en el dict → omitir sección Ficha Tecnica silenciosamente (OK)
  - Llave **presente** pero con valor `None` → lanzar `KeyError` duro con mensaje de trazabilidad forense
- **Archivo test modificado:** `tests/test_pcc_ficha_tecnica.py`
- Se añadió Escenario 2b al test `test_pcc_ficha_tecnica_no_silent_null` que:
  - Inyecta `summary=None` en el mock item (mutación explícita)
  - Parchea `search_items` para forzar el ítem corrupto al loop de formateo
  - Verifica que se lanza `KeyError` con `"CATALOG INTEGRITY VIOLATION"` para diagnóstico forense

### Tarea 2 — Transformador dinámico de URL Meta en `test_habeas_data_gate_before_credit_score`
- **Archivo modificado:** `tests/test_pcc_ficha_tecnica.py`
- Se actualizó el Caso 2 (con consentimiento) para usar URLs complejas de Firebase Storage con query params:
  `?alt=media&token=abc123-xyz456&size=800&watermark=tlm`
- Se inyectó la función `_validate_meta_url_integrity()` que:
  - Verifica que la URL no fue truncada antes del pipeline (pre-flight check)
  - Verifica que los query params críticos (`?alt=media`, `&token=`) sobreviven intactos
  - Verifica longitud exacta de la URL para detectar truncado silencioso
- Diagnóstico forense reveló que el proxy Meta mutila URLs con `?` y `&` generando HTTP 400 silencioso

### Tarea 3 — Rechazo estricto de `'Sin descripción'` bajo Visual-Lock íntegro
- **Archivo modificado:** `app/services/agentic_loop_service.py`
- Se añadió la detección del marcador `'Sin descripción'` como fallo de Visual-Lock en `run_checker`:
  - Solo activo cuando `has_moto_interest=True` (intención comercial activa)
  - Sin `moto_interest`, el fallback es aceptable (consultas genéricas sin riesgo de alucinación)
  - `logs_trace` identifica `"SIN_DESCRIPCION_FALLBACK"` para diagnóstico forense
- **Archivo modificado:** `tests/test_pcc_ficha_tecnica.py`
- Se expandió `test_resilience_missing_summary_passes_filter` en dos sub-escenarios:
  - **Sub-A:** Sin `moto_interest` → `"Sin descripción"` es aceptable ✅
  - **Sub-B:** Con `moto_interest` activo → rechaza `"Sin descripción"` como Visual-Lock incompleto ✅

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| `app/services/catalog_service.py` | Modified | KeyError duro al detectar `summary=None` explícito en `search_catalog` |
| `app/services/agentic_loop_service.py` | Modified | Visual-Lock guard para marcador `'Sin descripción'` con `moto_interest` activo |
| `tests/test_pcc_ficha_tecnica.py` | Modified | 3 tests endurecidos con escenarios reales de mutación, URLs complejas y Visual-Lock |

## Verification

```
━━━ EVAL REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tests passed : 241
  Tests failed : 0
  Total        : 241
  Score        : 1.000 (threshold: 0.9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ SCORE 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```

## Commits Atómicos
- `ecd5b11`: Safety checkpoint before QA hardening
- `53c20b1`: feat(quick-160-t1): KeyError duro en search_catalog
- `521045d`: feat(quick-160-t2): transformador dinámico URL Meta
- `fceb71e`: feat(quick-160-t3): rechazo estricto 'Sin descripción' Visual-Lock

---
*Completed: 2026-07-11*
