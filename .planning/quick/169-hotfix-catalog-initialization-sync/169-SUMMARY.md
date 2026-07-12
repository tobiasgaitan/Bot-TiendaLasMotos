# Quick Task 169: Hotfix Catalog Initialization Sync — Summary

**Executed:** 2026-07-12
**Status:** Complete ✅

## What Was Done

### Causa Raíz Confirmada
La condición de carrera estaba en `CatalogService.load_catalog()` (línea 84 original): `ConfigLoader()` era invocado **sin argumento `db`**. El patrón Singleton de `ConfigLoader` requiere `db` en la primera instanciación. Si el singleton aún no estaba hidratado en el momento de la llamada, el `ValueError` era silenciado por el `except Exception:`, resultando en `category_aliases = {}` e invalidando todas las consultas de alias (regresión del ticket 163).

### Cambios Quirúrgicos

1. **`CatalogService.__init__()`**: Agregado atributo `_config_loader = None`
2. **`CatalogService.initialize(db, config_loader=None)`**: Acepta `ConfigLoader` como dependencia inyectada. Almacena en `self._config_loader`.
3. **`CatalogService.load_catalog()`**: Refactorizado para usar `self._config_loader` en vez de instanciar `ConfigLoader()`. Path degradado: accede al singleton existente via `_CL._instance` (sin crear uno nuevo).
4. **Guardrail `RuntimeError`**: Dispara `[CATALOG-INIT-FAILURE]` si `config_loader` fue inyectado, `raw_aliases` es un `dict` real, y `category_aliases` resulta vacío (Firestore field missing/empty).
5. **Re-raise externo**: `except RuntimeError: raise` en el bloque externo de `load_catalog()` para que el guardrail no sea absorbido silenciosamente.
6. **`app/main.py`**: Ambos paths (module-level línea 65 y lifespan línea 152) ahora pasan `config_loader` post-hidratación a `catalog_service.initialize()`.
7. **Test suite**: 5 tests de caracterización en `tests/test_catalog_initialization_sync.py`.

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `app/services/catalog_service.py` | Modified | DI refactor + RuntimeError guardrail |
| `app/main.py` | Modified | Inyección de config_loader en ambos paths |
| `tests/test_catalog_initialization_sync.py` | Created | 5 characterization tests |

## Verification

```
253 passed, 2 skipped, 2 subtests passed
Coherence Score: 1.000 (threshold: 0.9) ✓ DEPLOY AUTHORIZED ✅
```

---
*Completed: 2026-07-12 | Commit: 41bbaa4*
