# Plan 04-03b: Migración TestClient a Lifespan Real y Certificación — Summary

**Executed:** 2026-07-22
**Status:** Complete
**Prerequisite:** Wave 04-03a cerrada con Coherence 1.000 ✓

## What Was Built
- **Fixture `real_lifespan_client`** (`tests/conftest.py`): TestClient dentro del contexto de lifespan REAL de producción (lifespan → `asyncio.create_task(_run_deferred_initialization)` → commit barrier). Mockea SOLO el I/O externo en la frontera (LazyProxies de app.main: credenciales, firestore, config_service, ConfigLoader, FinanceConfigLoader, storage_service, init_memory_service, catalog_service-proxy de main); el router sigue viendo el singleton real con 60 ítems dinámicos (04-02) y `min_catalog_items=60` (umbral de producción). Incluye: sleep real de 2s (BOT-190, fidelidad total), espera activa con TimeoutError explícito a los 15s (zero-silent-failures: jamás cliente zombi), y teardown higiénico de `app.state` (snapshot/restore).
- **Inventario forense corregido:** el conteo "14 archivos" incluía 7 `.pyc` stale de `__pycache__`. Inventario real: **7 archivos .py** (4 TestClient + 3 httpx).

## Migración por archivo (certificación individual)
| Archivo | Uso previo | Resolución | Cert |
|---------|-----------|------------|------|
| test_health_check.py | 2× `TestClient(app)` sin lifespan | Migrado a fixture (2 tests parten de estado post-hidratación real) | 2/2 ✓ |
| test_robots.py | 1× `TestClient(app)` sin lifespan | Migrado a fixture | 1/1 ✓ |
| test_api_bounds.py | `client = TestClient(app)` module-level | Migrado a fixture (3 signature tests); eliminado wiring monkeypatch de 04-03a (el fixture satisface el guard como en producción) | 5/5 ✓ |
| test_startup_lock.py | 5× TestClient | **EXENCIÓN documentada** (REAL-LIFESPAN-EXEMPTION): es la suite del propio lifespan — sus usos ejercitan directamente el camino real (port binding, commit barrier, hidratación) | 11/11 ✓ |
| test_agentic_loop_async.py | patch `httpx.AsyncClient.post` | **No aplica**: httpx como librería saliente (Meta API), no transporte ASGI | verde ✓ |
| test_multimodal_similitude.py | patch `httpx.AsyncClient.post` | No aplica (ídem) | verde ✓ |
| test_notification_service.py | mock httpx.AsyncClient | No aplica (ídem) | verde ✓ |

## Verification Results (salidas reales)
- [x] Certificación individual migrados: health_check 2/2, robots 1/1, api_bounds 5/5 — **8/8 PASSED** (12.75s)
- [x] Suite completa: **374 passed, 2 skipped, 2 subtests passed (73.7s)** — +14s por los sleeps reales de 2s del deferred init (coste de fidelidad, documentado)
- [x] `npx agent-cli eval` → **Coherence Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅**
- [x] Cero regresiones /health + hidratación: startup_lock 11/11, health_check 2/2
- [x] `rg 'TestClient' tests/`: residuo solo en conftest.py (implementación del fixture + docstrings) y test_startup_lock.py (exención documentada en cabecera)
- [x] Inmutabilidad: `ai_brain.py` / `juan_pablo_personality` intactos

## Notable Decisions
- El fixture mantiene el `asyncio.sleep(2)` real del deferred init (BOT-190) en lugar de parchearlo: fidelidad total al camino de producción a cambio de +2s por instanciación (6 usos ≈ +12s suite).
- `min_catalog_items=60` en el fixture (no 0): el guard se ejerce con el umbral real de Cloud Run — los tests HTTP validan el comportamiento productivo, no una goma de paso.
- La exención de test_startup_lock se documenta en cabecera del archivo y aquí: convertir esos tests al fixture destruiría su propósito (control fino del init diferido).

## Issues Encountered
- Ninguno bloqueante. El conteo inflado "14 archivos" (pycache stale) fue corregido y documentado.

---
*Executed: 2026-07-22 | Wave 04-03b CLOSED — clientes HTTP sobre lifespan real, Coherence 1.000*
