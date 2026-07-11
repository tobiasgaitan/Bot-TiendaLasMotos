# Quick Task 155: bot-vision-parser — Summary

**Executed:** 2026-07-11
**Status:** Complete

## What Was Done
Desacoplamos el enrutamiento de imágenes de catálogo del token rígido `[MOTO_DETECTADA]` en `app/routers/whatsapp.py`.
- Si la respuesta de `VisionService` no contiene tags de documentos financieros (`"CEDULA"` o `"RECIBO"`), la procesa por defecto como una consulta de catálogo de motocicletas.
- Se sanitiza el texto crudo removiendo cualquier prefijo de token residual (`[MOTO_DETECTADA]`, `MOTO_DETECTADA:`, `MOTO_DETECTADA`).
- Si `vision_response` es None o vacía, se lanza un error controlado `ValueError` y se registra un log estructurado (extra) forense con todos los detalles del mensaje/Google API.
- Todo el procesamiento de respuesta de Vision AI se envolvió en un bloque try-except para capturar y reportar fallos catastróficos mediante logs estructurados sin silenciamiento silencioso.
- Se añadieron y modificaron las pruebas en `tests/test_identity_legal_gate.py` para validar la coexistencia del token legacy con el formato limpio, y verificar el comportamiento correcto ante respuestas nulas.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [whatsapp.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/routers/whatsapp.py) | Modified | Implementación de las condiciones de enrutamiento y sanitización, y control de excepciones estructurado. |
| [test_identity_legal_gate.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_identity_legal_gate.py) | Modified | Añadidos tres casos de prueba para el enrutamiento con y sin etiqueta, y con respuestas nulas. |

## Verification
- Se ejecutaron las pruebas locales de gate legal con éxito: `9 passed`.
- Se ejecutó la suite de evaluación completa con `npx @tobiasgaitan/agent-cli eval`.

---
*Completed: 2026-07-11*
