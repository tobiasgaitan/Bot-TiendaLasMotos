# Quick Task 194: Token Strip Hotfix — Summary

**Executed:** 2026-07-16
**Status:** Complete

## What Was Done
- Se modificó la inicialización de la clase `Settings` en `app/core/config.py` para aplicar un saneamiento agresivo mediante `.strip()` sobre las credenciales críticas de la API (`whatsapp_token`, `phone_number_id`, `webhook_verify_token`, `whatsapp_app_secret` y `admin_api_key`) si están definidas. Esto remueve de manera automática cualquier espacio en blanco, retorno de carro (`\r`) o salto de línea (`\n`) que se inyecte por error al pasar tokens por gcloud/terminal en caliente.
- Se agregó el caso de prueba unitaria `test_settings_token_stripping` en `tests/test_startup_lock.py` que inyecta credenciales simuladas con espacios al inicio y saltos de línea al final ('\n EAAT... \r'), y asegura que sean saneadas correctamente sin levantar errores de validación.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [app/core/config.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/core/config.py) | Modified | Se saneó con `.strip()` las variables críticas. |
| [tests/test_startup_lock.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_startup_lock.py) | Modified | Se añadió el test unitario `test_settings_token_stripping`. |

## Verification
- Se ejecutó `pytest tests/test_startup_lock.py` de forma exitosa (10/10 tests pasados).
- Se ejecutó `npx agent-cli eval` y la suite completa de pruebas retornó 270/270 (270 passed, including the new unit test).

---
*Completed: 2026-07-16*
