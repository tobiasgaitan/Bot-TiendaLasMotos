# Quick Task 146: Hotfix FAQ-Catalog Collision — Summary

**Executed:** 2026-07-09
**Status:** Complete ✅

## What Was Done

### Diagnóstico Forense
El bucle de auto-reparación post-generación (`BOT-QA-LOOP-107`) en `ai_brain.py` evaluaba `is_catalog_query` basándose **únicamente** en las keywords de la consulta del usuario (L659: `"ficha"`, `"tecnica"`, etc.) y el guardia del `if` (L661) activaba el bloque completo si `mentions_moto OR is_moto_query` era True por la presencia global de `"moto"`. Aunque `run_checker` determinaba `bypass_strict=True` (FAQ sin `moto_interest` en CRM), el dict de retorno solo exponía `{"success": True, "report": {}}` — sin señal explícita del bypass. El llamador en `ai_brain.py` no podía distinguir entre un pass genuino de catálogo y un bypass semántico.

### Corrección Quirúrgica (2 archivos, 13 líneas netas)

**1. `app/services/agentic_loop_service.py` (contrato del checker):**
- Expuesto `bypass_strict: True` en el dict de retorno exitoso cuando se aplica el bypass semántico.

**2. `app/services/ai_brain.py` (máquina de estados):**
- En el bloque `else` post-validación exitosa: se lee `validation.get("bypass_strict")`.
- Si el bypass fue aplicado, se fuerza `is_catalog_query = False` sincrónicamente.
- Se emite log forense `INFO` con `[PCC BYPASS]` incluyendo `user_id` y `query` para trazabilidad en GCP Cloud Logging.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| `app/services/agentic_loop_service.py` | Modified | Expone `bypass_strict=True` en el retorno exitoso del bypass |
| `app/services/ai_brain.py` | Modified | Lee `bypass_strict`, fuerza `is_catalog_query=False` y emite log forense |

## Verification

```
CLI Verification (3 edge cases):
  Caso 1 FAQ pura:             success=True  bypass_strict=True   ✅
  Caso 2 FAQ+moto sin interés: success=True  bypass_strict=True   ✅
  Caso 3 Catálogo real:        success=False bypass_strict=False  ✅

Test Suite: 216 passed, 1 pre-existing failure (test_eventloop_latency - requires GCP credentials)
```

---
*Completed: 2026-07-09*
