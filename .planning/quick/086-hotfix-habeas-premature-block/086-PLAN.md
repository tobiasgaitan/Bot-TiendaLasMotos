---
task: 086
name: Remoción quirúrgica del interceptor prematuro de Habeas Data
description: Eliminar el bloque PermissionError (L1276-1283) que colisiona con el HabeasDataBypassInterrupt (L1447) en ai_brain.py
---

# Quick Task 086: Remoción quirúrgica del interceptor prematuro de Habeas Data

## Objective
Eliminar la colisión lógica entre el `raise PermissionError` prematuro (L1276-1283) y el interceptor seguro `HabeasDataBypassInterrupt` (L1447) en `app/services/ai_brain.py`. Linealizar el flujo para que la simulación ciega legítima se ejecute directamente sin el desvío artificial `raise → except → raise`.

## Arqueología Confirmada
- **Commit `a42b57c` (Quick-060)**: Introdujo el bloque `BOT-SEC-42` con `raise PermissionError` como guardia prematura.
- **Commit `3a36c8e` (Quick-081)**: Parcheó el problema con un `except PermissionError` que ejecuta la simulación ciega.
- **Commit `9545720` (Quick-084)**: Introdujo `HabeasDataBypassInterrupt` como mecanismo definitivo de cortocircuito.
- **El `except PermissionError` es ahora código de transición que duplica la lógica del bloque lineal.**

## Diagnóstico
El flujo actual para `habeas_data_accepted=False` es:
1. L1278: `if not is_accepted` → `raise PermissionError` (BLOQUEA)
2. L1405: `except PermissionError` → ejecuta simulación ciega
3. L1447: `raise HabeasDataBypassInterrupt` → burbujea al L619

El flujo correcto debe ser lineal (sin excepción intermedia):
1. L1278: `if not is_accepted` → ejecuta simulación ciega directamente
2. `raise HabeasDataBypassInterrupt` → burbujea al L619

## Tasks

<task type="auto">
  <name>Refactorizar bloque calculate_credit_score</name>
  <files>app/services/ai_brain.py</files>
  <action>
  1. Reemplazar el bloque L1276-1283 (raise PermissionError) por la lógica de la simulación ciega que actualmente vive en el `except PermissionError` (L1405-1447).
  2. Mantener el `if is_accepted` como bifurcación: rama `True` → `evaluate_profile` (flujo completo); rama `False` → simulación ciega + HabeasDataBypassInterrupt.
  3. Eliminar el `except PermissionError as pe:` (L1405-1447) que se convierte en código muerto.
  4. Preservar `except HabeasDataBypassInterrupt: raise` y `except Exception as e: logger.exception(...)`.
  </action>
  <verify>cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos && python -m pytest tests/ -x -q 2>&1 | tail -20</verify>
  <done>El flujo lineal funciona, 168 tests pasan, no hay retornos nulos en PHASE_1.</done>
</task>

<task type="auto">
  <name>Actualizar comentarios de test</name>
  <files>tests/test_pcc_ficha_tecnica.py</files>
  <action>
  Actualizar el comentario de la línea 83 y 395 que menciona `PermissionError` para reflejar el nuevo flujo lineal directo a `HabeasDataBypassInterrupt`.
  </action>
  <verify>cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos && python -m pytest tests/test_pcc_ficha_tecnica.py -x -q 2>&1 | tail -10</verify>
  <done>Comentarios actualizados, tests pasan.</done>
</task>

---
*Created: 2026-07-01*
