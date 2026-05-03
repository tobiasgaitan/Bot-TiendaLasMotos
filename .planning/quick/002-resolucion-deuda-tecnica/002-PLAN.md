---
task: 002
name: Resolución Deuda Técnica Tests Restantes
description: Resolución de Deuda Técnica en suite de pruebas (4 tests fallidos). Causas diagnosticadas: Evolución de Pydantic Schema no reflejada en tests, invocación dura de infraestructura en entorno aislado, desincronización de fallback financiero y aserción rígida de prompts.
---

# Quick Task 002: Resolución Deuda Técnica Tests Restantes

## Objective
Reparar 4 tests caídos en la suite debido a deuda técnica (cambios de esquema, fallbacks financieros, y aserciones de prompts CRM Anchor) para que el pipeline de CI/CD pase limpiamente.

## Tasks

<task type="auto">
  <name>Parchear test_campaign_admin.py</name>
  <files>tests/test_campaign_admin.py</files>
  <action>Inyectar `language="es"` en la inicialización de `CampaignRequest`.</action>
  <verify>source .venv/bin/activate && pytest tests/test_campaign_admin.py -v</verify>
  <done>El test debe pasar sin errores de Pydantic ValidationError.</done>
</task>

<task type="auto">
  <name>Refactorizar test_price_consolidation.py</name>
  <files>tests/test_price_consolidation.py</files>
  <action>Reemplazar `firestore.Client()` con `MagicMock()`.</action>
  <verify>source .venv/bin/activate && pytest tests/test_price_consolidation.py -v</verify>
  <done>El test no debe intentar conectar con Firestore real y debe pasar.</done>
</task>

<task type="auto">
  <name>Alinear test_proactive_credit.py</name>
  <files>tests/test_proactive_credit.py</files>
  <action>Actualizar los mocks de `mock_config` para que devuelvan diccionarios vacíos en lugar de Mocks puros al llamar a `get_financial_entity_config` y usar `entidad="Banco"` para evadir la regla hardcodeada de Crediorbe (0.0 de seguro_vida) y evaluar el fallback de 15000.</action>
  <verify>source .venv/bin/activate && pytest tests/test_proactive_credit.py -v</verify>
  <done>El cálculo debe retornar correctamente el fallback esperado en lugar de fallar.</done>
</task>

<task type="auto">
  <name>Actualizar aserción en test_ai_adapter.py</name>
  <files>tests/test_ai_adapter.py</files>
  <action>Modificar la cadena esperada para el CRM Anchor reflejando la versión v7.7.0 en la línea 49.</action>
  <verify>source .venv/bin/activate && pytest tests/test_ai_adapter.py -v</verify>
  <done>El test debe pasar.</done>
</task>

---
*Created: 2026-04-29*
