# Quick Task 041: Unificar Persistencia Prospectos — Summary

**Executed:** 2026-06-07
**Status:** Complete

## What Was Done

Refactorización de la capa de persistencia para unificar todos los flujos de chat/sesión bajo la colección canónica `prospectos`. La colección `mensajeria` fue eliminada como destino de escritura en todos los módulos de producción.

### Arqueología Forense (Valla de Chesterton)
- **Commit original** (`e5b5286`): 0 referencias a `mensajeria`, 9 a `prospectos`
- **Bifurcación** (`b813be47`): Introducida sin documentación en v9.6.0
- **Propósito original**: Aislar historial volátil del documento CRM
- **Solución**: Preservar el aislamiento como subcolección `prospectos/{phone}/historial`

### Cambios Ejecutados
La ruta de persistencia cambió de 5 segmentos a 3 segmentos:
- **Antes**: `mensajeria/whatsapp/sesiones/{phone}/historial`
- **Después**: `prospectos/{phone}/historial`

## Files Modified
| File | Action | Description |
|------|--------|-------------|
| `app/services/memory_service.py` | Modified | 5 métodos redirigidos a prospectos/{phone}/historial |
| `app/services/survey_service.py` | Modified | 3 métodos redirigidos a prospectos collection |
| `app/routers/whatsapp.py` | Modified | _get_session redirigido a prospectos |
| `tests/test_persistence_unification.py` | Created | 8 tests: Key Alignment, Ficha Tecnica, static grep, canonical route |
| `tests/test_reset_flow.py` | Modified | Mocks actualizados para nueva ruta |
| `tests/test_read_asymmetry.py` | Modified | Mocks actualizados para nueva ruta |
| `tests/test_memory_stream_coverage.py` | Modified | Mock chain depth reducida de 5 a 3 segmentos |

## Verification
- **Pytest**: 104/104 tests passed (0 regressions)
- **Static Analysis**: `grep -rn 'collection("mensajeria")' app/ --include="*.py"` → 0 coincidencias
- **Commit**: `a140e02`

---
*Completed: 2026-06-07*
