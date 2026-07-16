# Quick Task 188: Deferred Init — Container Crash Port Binding Fix — Summary

**Executed:** 2026-07-16
**Status:** Complete

## What Was Done
Eliminado el bloque de inicialización síncrona a nivel de módulo (`if not TEST_MODE:`, antiguas L44-84) en `app/main.py` que ejecutaba llamadas de red bloqueantes (Secret Manager, Firestore gRPC, catalog hydration) durante el `import` de Python, impidiendo que Uvicorn abriera el puerto 8080 antes del timeout de la TCP startup probe de Cloud Run.

Toda la inicialización pesada se movió a `_run_deferred_initialization()`, un background task lanzado via `asyncio.create_task()` desde el hook `lifespan()` de FastAPI. Esto permite que:
1. Uvicorn abra el socket en el puerto 8080 **de inmediato**
2. La TCP startup probe de Cloud Run reciba HTTP 200 instantáneamente
3. El catálogo se hidrate en segundo plano sin bloquear el hilo principal
4. El webhook handler rechace peticiones con HTTP 503 hasta que `catalog_ready=True`

El endpoint `/health` ahora reporta status degradado `"starting"` mientras la hidratación está en progreso, y `"healthy"` cuando completa.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| app/main.py | Modified | Eliminado bloque bloqueante module-level, creada `_run_deferred_initialization()` como background task, health endpoint con status degradado |
| tests/test_startup_lock.py | Modified | Nuevo test `test_deferred_init_port_available_before_hydration` que verifica yield inmediato del lifespan (<0.5s) |
| tests/test_health_check.py | Modified | Alineación de aserciones con nuevo contrato de status degradado |

## Verification
- ✅ Syntax validation: `python3 -c "import ast; ast.parse(...)"`
- ✅ Startup lock tests: 6/6 passed (including new port-binding regression test)
- ✅ Full test suite: **264 passed, 0 failures, 2 skipped**
- ✅ Core regression test confirms lifespan yields in <0.5s even with 2s simulated slow init

---
*Completed: 2026-07-16*
