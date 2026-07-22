# Plan 04-03a: Erradicación TOTAL del Bypass is_test_mode en Producción — Summary

**Executed:** 2026-07-22
**Status:** Complete
**Prerequisite:** Wave 04-02 cerrada con Coherence 1.000 ✓

## What Was Built
Erradicación de TODOS los seams de modo de pruebas del código de producción y del arnés global. El STARTUP-GUARD es ahora estricto e incondicional; los tests lo satisfacen explícitamente (fixtures 04-02 + wiring `catalog_ready=True`).

### Producción (4 archivos)
- **`app/routers/whatsapp.py`** — eliminados los 2 bloques bypass (`webhook_handler`, `task_processor`): `is_test_mode`, sniffing de tipos Mock y `should_bypass` sustituidos por parseo estricto `int(settings.min_catalog_items)` con `logger.exception` ante fallo (fallback 60). Guard idéntico e incondicional en ambos endpoints.
- **`app/main.py`** — eliminada la variable de módulo de modo de pruebas y toda la rama inline del lifespan (~80 líneas: init con mocks + fallback `DummyConfigLoader`/`DummyFinanceConfigLoader` + `dummy_completed_task`). Un solo camino: `asyncio.create_task(_run_deferred_initialization(app))`. `import os` huérfano eliminado.
- **`app/services/catalog_service.py`** — STARTUP-GUARD-PAD: eliminada la detección de pytest; el objetivo del padding ahora es `int(settings.min_catalog_items)` (con `logger.exception`, fallback 60) y se desactiva explícitamente con target 0. Producción intacta (60). Añadido `from app.core.config import settings`.
- **`app/core/config.py`** — default uniforme `"40"` para `MIN_CATALOG_ITEMS` en todo contexto; eliminada la detección de pytest (`import sys` huérfano removido).

### Arnés y CI
- **`tests/conftest.py`** — fuera las inyecciones globales de modo de pruebas y `MIN_CATALOG_ITEMS=0`.
- **`.github/workflows/qa-pipeline.yml`** — fuera `TEST_MODE`/`MIN_CATALOG_ITEMS` del job (comentario actualizado).

### Migración de tests (11 archivos)
- `test_startup_lock.py`: eliminados 4× `patch.object(main_module, "TEST_MODE", ...)` + 4× wrappers `patch.dict` del entorno de pruebas (con dedent) + imports locales huérfanos.
- Wiring `mock_request.app.state.catalog_ready = True` en: `test_webhook_sync_block` (×4), `test_characterization_etapa1` (helper + ×2), `test_router_concurrency` (×2), `test_audio_regression`, `test_eventloop_latency`, `test_webhook_burst_load` (+`mock_settings.min_catalog_items = 0` donde faltaba: ×7 sitios).
- `test_api_bounds.py::test_webhook_signature_valid`: `monkeypatch` sobre `app.state.catalog_ready` + `settings.min_catalog_items` (preserva simetría HMAC del app_secret real).
- `test_catalog_double_buffer.py` / `test_catalog_price_bonus.py`: patch explícito `settings.min_catalog_items=0` en setUp (padding off — los asserts exigen conteos exactos).
- `test_min_catalog_items_env.py`: test del default reescrito (40 uniforme, sin ramas pytest) + restaurado `from unittest.mock import patch` (baja accidental detectada por la suite).
- **Hallazgo forense clave:** `MagicMock(spec=Request)` hereda `__len__` de la interfaz Mapping de `HTTPConnection` (retorna 0) → `bool(request)==False` → short-circuit del guard. Resuelto eliminando `spec=Request` en `test_eventloop_latency` y `test_webhook_burst_load` (documentado con WHY).

## Verification Results (salidas reales)
- [x] `rg 'is_test_mode|TEST_MODE|pytest.{0,20}sys\.modules' app/ tests/conftest.py tests/test_config_startup.py .github/` → **0 hits** (acceptance #2)
- [x] Suite completa: **374 passed, 2 skipped, 2 subtests passed (59.85s)** — baseline idéntica, cero regresiones
- [x] **0 RuntimeWarnings** (`grep -c RuntimeWarning` → 0)
- [x] `npx agent-cli eval` → **Coherence Score 1.000 ≥ 0.9 — DEPLOY AUTHORIZED ✅**
- [x] /health + hidratación: `test_startup_lock` 11/11, `test_health_check` verde (cero regresión, acceptance #4)
- [x] Inmutabilidad: `git diff` vacío en `ai_brain.py` y `prompts.py` (juan_pablo_personality)
- [x] Zero-silent-failures: los 3 nuevos try/except de parseo (whatsapp ×2, catalog_service ×1) inyectan `logger.exception`

## Notable Decisions
- El guard conserva `if request and hasattr(...)` (producción: Request real tiene scope no-vacío → truthy). La fragilidad era del mock espeado, no del código → se corrigió en tests, no en producción.
- `int(MagicMock())` retorna 1 (no excepción): los tests que patchean settings con MagicMock deben fijar `min_catalog_items` explícitamente — aplicado en ×7 sitios.
- Padding con `target_min=0` = off explícito: es el mecanismo aprobado para tests de conteo exacto (sustituye al seam de pytest).

## Issues Encountered
- Baja accidental de `from unittest.mock import patch` en `test_min_catalog_items_env.py` al editar imports → detectada por la suite (NameError ×3) y restaurada.
- 2 tests con `spec=Request` fallaban con `catalog_ready=False` pese al wiring → root cause `__len__` heredado (ver arriba); documentado en los tests.

## Deferral a 04-03b
- Tests TestClient (health_check, robots, api_bounds, notification_service, agentic_loop_async, multimodal_similitude) pasan SIN migración (controlan `app.state` explícitamente o no disparan lifespan). 04-03b consolida el fixture `real_lifespan_client` y certifica los 14 archivos individualmente.

---
*Executed: 2026-07-22 | Wave 04-03a CLOSED — seam erradicado, Coherence 1.000*
