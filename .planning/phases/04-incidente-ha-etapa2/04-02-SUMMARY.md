# Plan 04-02: Fábrica de Mocking Dinámico en Memoria — Summary

**Executed:** 2026-07-22
**Status:** Complete
**Prerequisite:** `npx agent-cli scaffold --check` → **PASS ✅** (estructura conforme)

## What Was Built
- **`tests/factories.py`** (nuevo): generador determinista (seed=2026) de catálogos en memoria — `make_catalog(n=60)` con precios dinámicos (COP 3M–12M, múltiplos de 10k, rng-seeded), `make_catalog_item`, `make_domain_item(**overrides)`, `make_prospect`, `format_cop`, `install_dynamic_catalog`/`restore_catalog` (inyección en el singleton real con restauración explícita) y `TEST_SMLV = 1_705_905` como fuente única de verdad del arnés. Fallos explícitos (ValueError/TypeError/AttributeError) ante parámetros inválidos — zero-silent-failures.
- **`tests/conftest.py`**: fixtures `dynamic_catalog` (60 ítems inyectados con teardown) y `catalog_guard_ready` (catálogo + `app.state.catalog_ready=True` + `min_catalog_items=60` vía monkeypatch) — la forma aprobada de satisfacer el guard estricto tras 04-03a.
- **Migración de los 5 tests del guard** (7+2 sitios):
  - `test_startup_lock.py`: 2× `[MagicMock()] * 60` → `make_catalog(60)`
  - `test_characterization_etapa1.py`: 3× `[MagicMock()] * 10` → `make_catalog(10)`
  - `test_router_concurrency.py`: 1× `[MagicMock()] * 10` → `make_catalog(10)`
  - `test_audio_regression.py`: `[{"name": "Victory"}] * 100` → `make_catalog(100)`; `[{"name": "TVS Sport 100"}] * 50` → `make_catalog(50)`; ítem Raider hand-crafted → `make_domain_item(**overrides)`; 3 respuestas cerebro con precio literal (`$6.000.000`, `$3.200.000`) → `format_cop(item['price'])` (consistencia PCC dinámica)
  - `test_config_startup.py`: sin cambios requeridos en esta wave (su `MIN_CATALOG_ITEMS: "0"` se elimina en 04-03a T5 junto al default pytest de config.py — deferral planeado)

## Files Created/Modified
| File | Action | Description |
|------|--------|-------------|
| tests/factories.py | Created | Generador determinista + TEST_SMLV + install/restore |
| tests/conftest.py | Modified | +2 fixtures (dynamic_catalog, catalog_guard_ready) |
| tests/test_startup_lock.py | Modified | 2 mocks ad-hoc → factories |
| tests/test_characterization_etapa1.py | Modified | 3 mocks ad-hoc → factories |
| tests/test_router_concurrency.py | Modified | 1 mock ad-hoc → factories |
| tests/test_audio_regression.py | Modified | 4 mocks ad-hoc + 3 precios literales → factories |

## Verification Results (salidas reales)
- [x] `npx agent-cli scaffold --check` → `Scaffold integrity: PASS ✅`
- [x] Contrato factories (determinismo, unicidad, rango de precios, install/restore, fallos explícitos) → `FACTORIES OK`
- [x] 5 archivos del guard migrados: **28 passed** (10.36s)
- [x] Escaneo de residuos (precios/SMLV/urls hardcodeadas en los 5 archivos) → **0 hits**
- [x] Suite completa: **374 passed, 2 skipped, 2 subtests passed (55.85s)** — idéntico a baseline pre-wave (374/2), cero regresiones, cero RuntimeWarning transversal nuevo
- [x] `npx agent-cli eval` → **Coherence Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅**

## Notable Decisions
- `test_min_catalog_items_env.py` NO se tocó: su assert del default pytest (0) sigue vigente hasta que config.py pierda la detección pytest en 04-03a T4 (deferral coherente con el plan).
- El wiring `catalog_ready=True` en los tests characterization/router (requests MagicMock) se difiere a 04-03a: hoy el bypass lo hace innecesario; allí será obligatorio. Los fixtures ya lo soportan.
- `ai_brain.py` y `juan_pablo_personality`: intactos (constraint de inmutabilidad — `git diff` vacío).

## Issues Encountered
- 2 residuos de literales en un tercer test de `test_audio_regression.py` no cubierto por el barrido inicial (L79 `$6.000.000`, L237 `[{"name":...}] * 50` + `$3.200.000`) → migrados en el mismo pase; re-escaneo 0 hits.

---
*Executed: 2026-07-22 | Wave 04-02 CLOSED — arnés dinámico operativo, Coherence 1.000*
