---
task: 043
name: BOT-BUG-044-REV2 Judge Sync and Fallback Log
description: Modificar judge_service para permitir simulación ciega sin habeas data, registrar rejection_reason nativo en whatsapp.py, y test de integridad
---

# Quick Task 043: BOT-BUG-044-REV2 Judge Sync and Fallback Log

## Objective
Corregir la desincronización de Habeas Data en el `judge_service` que bloquea la Simulación Ciega Anticipada de cuotas y exponer el motivo de rechazo en el fallback de `whatsapp.py`, además de agregar aserciones de consistencia para prevenir fallos silenciosos.

## Tasks

<task type="auto">
  <name>Modificar judge_service.py</name>
  <files>app/services/judge_service.py</files>
  <action>Actualizar _is_profiling_attempt con los patrones estrictos de ai_brain.py para no bloquear cuotas ciegas.</action>
  <verify>pytest tests/test_bot_bug_044_rev2.py -v</verify>
  <done>Las cuotas simuladas no triggerean C3_HABEAS_DATA_VIOLATION.</done>
</task>

<task type="auto">
  <name>Modificar whatsapp.py</name>
  <files>app/routers/whatsapp.py</files>
  <action>Añadir rejection_reason en el logger.error de JUDGE_FALLBACK.</action>
  <verify>grep -q "Rejection Reason: {rejection_reason}" app/routers/whatsapp.py && echo "Pasa"</verify>
  <done>El log expone nativamente el motivo del rechazo.</done>
</task>

<task type="auto">
  <name>Añadir Test de Verificación</name>
  <files>tests/test_bot_bug_044_rev2.py</files>
  <action>Crear test unitario que aserte que la mutación de strings o valores de llaves no generan strings vacíos ni Nones.</action>
  <verify>pytest tests/test_bot_bug_044_rev2.py</verify>
  <done>El test pasa correctamente y valida Zero-Silent-Failures.</done>
</task>

---
*Created: 2026-06-08*
