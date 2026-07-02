---
task: 094
name: hotfix-async-firestore-stream
description: Desbloquear el event loop de FastAPI aislando las llamadas síncronas de Firestore .stream() en CatalogService fuera del hilo principal del webhook
---

# Quick Task 094: hotfix-async-firestore-stream

## Objective
Eliminar el bloqueo del event loop de FastAPI causado por `firestore.Client.stream()` (I/O síncrono) ejecutándose en handlers `async` del webhook de WhatsApp. La solución aísla las operaciones síncronas pesadas en un thread separado usando `asyncio.to_thread()`.

## Diagnóstico Verificado Físicamente

| Vector | Archivo | Línea | Impacto |
|--------|---------|-------|---------|
| `items_ref.stream()` en `load_catalog()` | `catalog_service.py:76` | Cold-start (`lifespan`) | ✅ Aceptable |
| `CatalogService().initialize(db)` | `whatsapp.py:120-121` | Lazy init en webhook async | 🔴 BLOQUEO |
| `catalog_service_local.refresh()` | `whatsapp.py:636` | Comando `/refresh_catalog` | 🔴 BLOQUEO |

## Decisión de Arquitectura
- **NO** reescribimos `load_catalog()` a async (cambio invasivo, requiere `AsyncClient` y alteración de todo el flujo de iteración).
- **SÍ** envolvemos las llamadas síncronas en `asyncio.to_thread()` en los dos callsites del webhook, delegando la ejecución al `ThreadPoolExecutor` por defecto de asyncio.
- El `lifespan` en `main.py` permanece intacto (es síncrono de naturaleza y se ejecuta antes de aceptar requests).

## Tasks

<task type="auto">
  <name>Convertir _ensure_services a async y aislar I/O síncrono</name>
  <files>app/routers/whatsapp.py</files>
  <action>
    1. Renombrar `_ensure_services()` a `_ensure_services_sync()` (mantiene toda la lógica actual intacta).
    2. Crear nueva `async def _ensure_services()` que ejecuta `await asyncio.to_thread(_ensure_services_sync)`.
    3. Actualizar `catalog_service_local.refresh()` en línea 636 para ejecutar `await asyncio.to_thread(catalog_service_local.refresh)`.
    4. Asegurar que todos los callsites de `_ensure_services()` ya estén en contexto `async` (verificado: todos están dentro de handlers async).
  </action>
  <verify>cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos && python -m pytest tests/ -x -q 2>&1 | tail -20</verify>
  <done>_ensure_services() es async, delega el I/O síncrono a un thread, y todas las pruebas pasan al 100%.</done>
</task>

---
*Created: 2026-07-02T15:43:00-05:00*
