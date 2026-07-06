# Quick Task 094: hotfix-async-firestore-stream — Summary

**Executed:** 2026-07-02
**Status:** Complete

## What Was Done
Aislé las operaciones de I/O síncronas de Firestore (`.stream()`) del event loop principal de FastAPI para eliminar el bloqueo de 10 minutos bajo carga real de producción Meta.

### Causa Raíz Verificada
`CatalogService.load_catalog()` ejecuta `firestore.Client.stream()` (I/O bloqueante) dentro de handlers `async def` del webhook de WhatsApp. Bajo carga concurrente de Meta, esto congela el event loop de asyncio y todos los demás webhooks quedan encolados.

### Corrección Quirúrgica
- Renombrado `_ensure_services()` → `_ensure_services_sync()` (conserva toda la lógica intacta)
- Creado nuevo wrapper `async def _ensure_services()` que delega al `ThreadPoolExecutor` via `asyncio.to_thread()`
- Convertidos los 6 callsites en handlers async a `await _ensure_services()`
- Aislado `catalog_service_local.refresh()` en `asyncio.to_thread()` para el comando `/refresh_catalog`
- El `lifespan` en `main.py` NO fue modificado (ejecuta antes de aceptar requests)

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| `app/routers/whatsapp.py` | Modified | Async isolation of sync Firestore I/O via `asyncio.to_thread()` |

## Verification
- **162/162 tests PASSED** (0 failures, 0 errors)
- Verificación ejecutada con: `uv run python -m pytest tests/ -x -q`
- Commit: `da56b17`

---
*Completed: 2026-07-02T15:47:00-05:00*
