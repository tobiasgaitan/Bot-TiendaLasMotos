# Quick Task 167: Hotfix Generic Stopword Stripping — Summary

**Executed:** 2026-07-12
**Status:** Complete ✅

## What Was Done

### Causa Raíz Verificada Físicamente
El token `"motos"` (y variantes) es generado por `_tokenize()` en la fase de preprocesamiento de `CatalogService.search_items` y luego incluido en `query_alphabetic_tokens` (línea 630). Al entrar al bucle de validación perimetral `has_alphabetic_match` (BOT-BACKEND-CATALOG-THRESHOLD-163), ningún ítem del catálogo lo tiene en sus `searchBy` tags ni en `name_tokens`, forzando `has_alphabetic_match = False` antes de que tokens intencionales como `"pisteras"` o `"deportiva"` (inyectados vía alias mapping) puedan rescatar el match. Resultado: retorno de `[]` vacío para consultas compuestas como `"Motos pisteras"`.

### Corrección Quirúrgica (catalog_service.py)
Inyección de un set estático `_COMMERCIAL_STOPWORDS = {"motos", "moto", "motocicleta", "motocicletas"}` con filtro inmediato **post-extracción de `query_alphabetic_tokens`** y **pre-bucle perimetral**. No altera:
- La lista `query_tokens` (base de scoring)
- Los ngrams calibrados
- El mapa de alias de categorías
- Las restricciones de BOT-BACKEND-CATALOG-THRESHOLD-163 para tokens específicos

### Autopsia de Tests (test_agentic_loop_async.py)
Nueva función `test_catalog_generic_stopword_stripping()` con **3 casos de caracterización**:
1. `"Motos pisteras"` → debe retornar `TVS Raider 125` (categoría `deportiva`)
2. `"Motos scooters"` → debe retornar `TVS Ntorq 125` (categoría `moped`)
3. `"motocicleta pistera"` → debe retornar `TVS Raider 125` (categoría `deportiva`)

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| `app/services/catalog_service.py` | Modified | Filtro `_COMMERCIAL_STOPWORDS` en línea 631-640 |
| `tests/test_agentic_loop_async.py` | Modified | `test_catalog_generic_stopword_stripping()` — 3 casos |

## Verification
```
━━━ EVAL REPORT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Tests passed : 248
  Tests failed : 0
  Total        : 248
  Score        : 1.000 (threshold: 0.9)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ SCORE 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅
```

**Commit:** `a4b5eb9` — `feat(quick-167): hotfix commercial stopword stripping in search_items perimeter`

---
*Completed: 2026-07-12*
