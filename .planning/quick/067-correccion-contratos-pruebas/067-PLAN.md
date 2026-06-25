---
task: 067
name: correccion_contratos_pruebas_firestore
description: Corregir discrepancias de nomenclatura de Firestore, forma_pago, variables estrictas de EXTRACTION_SCHEMA y alertar guardrail PCC Pro en tests.
---

# Quick Task 067: correccion_contratos_pruebas_firestore

## Objective
Corregir discrepancias de nomenclatura de Firestore y variables inventadas en la suite de pruebas unitarias alineándolas a la nomenclatura estricta del EXTRACTION_SCHEMA, y asegurar que la mutación de llaves del catálogo active la alerta de PCC Pro.

## Tasks

<task type="auto">
  <name>Actualizar forma_pago y llaves de prueba en test_agentic_loop_async.py</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>Cambiar 'forma_pago': 'credito' por 'Crédito - 0 inicial' y alinear los parámetros de evaluate_profile a 'ocupacion' y 'datacredito'.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>Las pruebas de test_agentic_loop_async.py pasan exitosamente con los valores canónicos.</done>
</task>

<task type="auto">
  <name>Alinear parámetros de evaluate_profile en financial_service.py</name>
  <files>app/services/financial_service.py</files>
  <action>Modificar evaluate_profile para extraer 'ocupacion' y 'datacredito' priorizándolos sobre los parámetros antiguos.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>El método evaluate_profile soporta 'ocupacion' y 'datacredito' y pasa las pruebas.</done>
</task>

<task type="auto">
  <name>Asegurar que la mutación de una llave requerida active la alerta del guardrail PCC Pro en test_pcc_ficha_tecnica.py</name>
  <files>tests/test_pcc_ficha_tecnica.py</files>
  <action>Modificar los escenarios de prueba mutada para verificar que run_checker retorne success=False con broken_guardrail='PRICE_CONSISTENCY_CHECK'.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>Las aserciones verifican correctamente que run_checker detecta fallos de validación por mutación de llaves.</done>
</task>

---
*Created: 2026-06-25*
