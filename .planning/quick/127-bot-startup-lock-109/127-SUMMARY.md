# Quick Task 127: bot-startup-lock-109 — Summary

**Executed:** 2026-07-06
**Status:** Complete

## What Was Done
- **Propiedad min_catalog_items en Settings:** Se agregó `self.min_catalog_items` cargado desde `MIN_CATALOG_ITEMS` (por defecto `60` en producción, y `0` en pytest).
- **Secuenciación Lineal y Bloqueante en Lifespan:** Se eliminó `ThreadPoolExecutor` del arranque inicial. La inicialización ahora se realiza lineal y bloqueantemente (`config_service.initialize()`, `config_loader.load_all()`, `catalog_service.initialize()`, `FinanceConfigLoader()`).
- **Timeout con Fail-Fast:** Se envolvió la inicialización síncrona en `asyncio.wait_for(asyncio.to_thread(...), settings.db_timeout)` para forzar un fail-fast estricto de 5 segundos. En caso de timeout o error, se inyecta un log forense detallado y se lanza un `RuntimeError` para tumbar el contenedor.
- **Validación de Tamaño de Catálogo:** Inmediatamente tras la carga, se verifica que la cantidad de ítems sea mayor o igual al umbral mínimo, lanzando un `RuntimeError` en producción si no es así.
- **Protección de Webhooks y Worker:** Se agregaron guardas en `webhook_handler` y `task_processor` de `app/routers/whatsapp.py` que retornan HTTP 503 Service Unavailable si el catálogo no se encuentra completamente cargado en memoria.
- **Pruebas Unitarias de Arranque y Guarda:** Se creó `tests/test_startup_lock.py` cubriendo todos los escenarios (reemplazo por 503, timeout del lifespan, fallas de tamaño de catálogo).
- **Evitar Regresión en Pytest:** Se configuró el entorno de pruebas para defaulting de `MIN_CATALOG_ITEMS` a 0 bajo pytest, asegurando que las 202 pruebas previas sigan pasando.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/core/config.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/core/config.py) | Modified | Added `min_catalog_items` setting and auto-default to 0 in pytest. |
| [app/main.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/main.py) | Modified | Implemented sequential, blocking startup within timeout and catalog item validation. |
| [app/routers/whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py) | Modified | Added 503 rejection guards to webhook_handler and task_processor. |
| [tests/conftest.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/conftest.py) | Modified | Updated mock_env_vars fixture with TEST_MODE="true" and MIN_CATALOG_ITEMS="0". |
| [tests/test_startup_lock.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_startup_lock.py) | New | Created unit tests verifying webhook HTTP 503 rejection and lifespan startup failures. |

## Verification
- Ejecutado `npx @tobiasgaitan/agent-cli eval` y certificado que 206/206 pruebas pasaron con un Score de Coherencia de 1.000.
- Verificada la estructura del proyecto mediante `npx agent-cli scaffold --check` resultando en PASS.

---
*Completed: 2026-07-06*
