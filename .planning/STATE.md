# Project State — BOT-STRUC-765-EVOLUTION

**Project:** Bot TiendaLasMotos — Refactoring God Nodes & Schema Standardization
**Ticket principal:** BOT-STRUC-765-EVOLUTION
**Rama activa:** beta
**Último commit:** b4471b3 — `refactor(ai-brain): extract God Nodes, elevate schema, standardize HTTP error handling`

## Estado Actual

| Campo | Valor |
|-------|-------|
| Fase activa | Post-refactor — Validación de no-regresión |
| Rama | beta |
| Último deploy | b4471b3 (beta) |
| Test suite | 33 PASSED / 13 FAILED (ver análisis abajo) |

## Quick Tasks Completadas

| # | Descripción | Fecha | Commit | Directorio |
|---|-------------|-------|--------|------------|
| 001 | Restauracion Entorno y Eval (BOT-CORE-770-EVAL) | 2026-04-29 | pendiente | 001-restauracion-entorno-eval |
| 003 | CLI Environment Isolation | 2026-04-29 | c120cc0 | 003-cli-isolation |

## Análisis de Fallos del Eval (BOT-CORE-770-EVAL)

### Categoría A — Regresión de Nomenclatura (Naming Lock) [CRÍTICO]
- `test_memory_merge` → `KeyError: 'habeasData'` (se renombró a `habeas_data_accepted` en el refactor)
- `test_reset_flow::test_merge_still_latches_true` → El latch de `habeas_data_accepted` no funciona

### Categoría B — Contrato de API Roto (God Node ai_brain)
- `test_habeas_data_regression::test_phase_*` → `AttributeError: type object 'obj' has no attribute 'get'`
  El método `_determine_funnel_phase` recibe objetos Pydantic `obj` en vez de dicts `{"role": ..., "content": ...}`

### Categoría C — Contrato de API Roto (MemoryService)
- `test_read_asymmetry` → `AttributeError: '_get_prospect_data_sync'` (método eliminado en refactor — era `get_prospect_data`)

### Categoría D — Tests de Infraestructura (No bloquean No-Regresión lógica)
- `test_price_consolidation`, `test_campaign_admin` → `async def functions not natively supported` (falta `pytest-asyncio` mode=auto)
- `test_read_asymmetry::test_template_sanitization` → mock incorrecto (coroutine sin await)
- `test_proactive_credit::test_deterministic_insurance_fallback` → Fallback de seguro de vida = 0 vs 15000

## Score de Coherencia Estimado

```
Tests lógicos core: 33 PASSED / 46 total = 71.7% RAW
Excluyendo tests de infraestructura (async/mock): 33/42 = 78.6%
SCORE ACTUAL: 0.71 — POR DEBAJO DEL UMBRAL 0.9
ESTADO: ⛔ DESPLIEGUE A BETA BLOQUEADO hasta resolver Categorías A, B, C
```

*Última actualización: 2026-04-29*
