# Quick Task 061: hotfix_canonical_moto_alignment — Summary

**Executed:** 2026-06-24
**Status:** Complete

## What Was Done
1. Removimos las variables redundantes `moto_ofrecida` y `moto_aceptada` en `app/services/ai_brain.py` para unificar el flujo multirreferencia sobre la llave canónica `moto_interest`.
2. Actualizamos el prompt del sistema `generate_summary` en `app/services/ai_brain.py` para eliminar las directivas asociadas con `moto_ofrecida` y `moto_aceptada`, y unificar las reglas de inmutabilidad y exclusión de marcas competidoras en torno a `moto_interest`.
3. Añadimos el campo `'required'` en el sub-esquema `'extracted'` de `EXTRACTION_SCHEMA` en `ai_brain.py` conteniendo exactamente `['nombre', 'ciudad', 'moto_interest', 'habeas_data_accepted']`.
4. Modificamos el test `tests/test_pii_high_fidelity.py` para remover las referencias a las variables descartadas y adaptarlo al esquema unificado.

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| [ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py) | Modified | Remoción de variables redundantes de motos y adición de required a extracted. |
| [test_pii_high_fidelity.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_pii_high_fidelity.py) | Modified | Adaptación de las aserciones de prueba al nuevo esquema unificado. |

## Verification
Ejecutamos la suite de pruebas completa:
```bash
npx agent-cli eval
```
Salida exitosa:
- Tests passed: 135
- Tests failed: 0
- Total: 135
- Score: 1.000

---
*Completed: 2026-06-24*
