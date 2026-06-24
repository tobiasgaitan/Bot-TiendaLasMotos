# Quick Task 059: Unificar llaves de catálogo a 'summary' y corregir condicional silencioso — Summary

**Executed:** 2026-06-23
**Status:** Complete

## What Was Done
1. Corregimos el condicional silencioso en `tests/test_pcc_ficha_tecnica.py` reemplazando el bloque condicional por una aserción directa de que `"Ficha Tecnica:"` no debe estar presente cuando las llaves del catálogo mutan o no existen.
2. Unificamos la obtención de la ficha técnica/resumen del catálogo a `'summary'` en `app/services/ai_brain.py`, removiendo el fallback a la llave legacy en español `'Descripción del producto TVS'`. También estandarizamos el uso de `'name'` y `'price'`/`'formatted_price'`.
3. Actualizamos los mocks y aserciones en las pruebas `tests/test_bot_bug_040.py` y `tests/test_brilla_conmutacion.py` para usar únicamente las llaves unificadas.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py) | Modified | Unificación de la extracción de llaves del catálogo a `name`, `summary` y `price` / `formatted_price`. |
| [test_pcc_ficha_tecnica.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pcc_ficha_tecnica.py) | Modified | Reemplazo del condicional silencioso por aserción directa en escenario de llaves mutadas. |
| [test_bot_bug_040.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_bot_bug_040.py) | Modified | Unificación de mocks y lógica de bucle interno a llaves estandarizadas. |
| [test_brilla_conmutacion.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_brilla_conmutacion.py) | Modified | Actualización del test de interceptación para utilizar llaves unificadas en el catálogo. |

## Verification
Ejecutamos la suite completa de pruebas locales mediante pytest, resultando en 134 pruebas exitosas:
```bash
.venv/bin/pytest tests/test_pcc_ficha_tecnica.py tests/test_bot_bug_040.py tests/test_brilla_conmutacion.py
```
Salida exitosa:
- `tests/test_pcc_ficha_tecnica.py` -> 1 passed
- `tests/test_bot_bug_040.py` -> 6 passed
- `tests/test_brilla_conmutacion.py` -> 5 passed

---
*Completed: 2026-06-23*
