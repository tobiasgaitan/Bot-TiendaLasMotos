---
task: 045
name: BOT-BUG-045 KeyError Fix
description: Aislar y reparar el KeyError en test_price_consolidation.py y alcanzar un eval de 0 fallos
---

# Quick Task 045: BOT-BUG-045 KeyError Fix

## Objective
Solucionar la regresión comercial detectada por 'eval' en `test_price_consolidation.py` que arroja un `KeyError`, restaurar la alineación de llaves, y lograr 0 fallos en los tests.

## Tasks

<task type="auto">
  <name>Aislar Error</name>
  <files>tests/test_price_consolidation.py</files>
  <action>Ejecutar pytest para identificar la traza del error.</action>
  <verify>./.venv/bin/pytest tests/test_price_consolidation.py -v --tb=short</verify>
  <done>Se identifica la llave faltante y el archivo origen.</done>
</task>

<task type="auto">
  <name>Reparar Origen de Datos</name>
  <files></files>
  <action>Modificar el archivo donde la llave es requerida/construida para evitar el KeyError.</action>
  <verify>./.venv/bin/pytest tests/test_price_consolidation.py -v --tb=short</verify>
  <done>El test de consolidación pasa exitosamente.</done>
</task>

<task type="auto">
  <name>Re-evaluación</name>
  <files></files>
  <action>Ejecutar npx agent-cli eval para certificar 0 fallos.</action>
  <verify>npx agent-cli eval</verify>
  <done>El reporte del eval indica 0 tests failed.</done>
</task>

---
*Created: 2026-06-08*
