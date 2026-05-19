---
task: 035
name: Purga de Llaves Legacy y Firma de calculate_credit_score
description: Purgar fallbacks legacy ('name', 'city', 'payment_method') en ai_brain.py y alinear calculate_credit_score con 'entidad' y 'reportes'
---

# Quick Task 035: Purga de Llaves Legacy y Firma de calculate_credit_score

## Objective
Purgar de forma física y estricta los fallbacks a llaves obsoletas/legacy (`name`, `city`, `payment_method`) en `ai_brain.py` para cumplir con el esquema canónico unificado. Alinear la firma de la herramienta `calculate_credit_score` añadiendo los parámetros `entidad` y `reportes` requeridos por el prompt del sistema y pasándolos adecuadamente al motor financiero.

## Tasks

<task type="auto">
  <name>Purgar fallbacks legacy de llaves ('name', 'city', 'payment_method') en ai_brain.py</name>
  <files>app/services/ai_brain.py</files>
  <action>Modificar `app/services/ai_brain.py` para eliminar las llaves legacy en la lógica de funnel y de prompt, asegurando consistencia absoluta con el esquema canónico unificado.</action>
  <verify>uv run pytest tests/test_ai_adapter.py</verify>
  <done>Todos los fallbacks obsoletos en ai_brain.py han sido eliminados físicamente.</done>
</task>

<task type="auto">
  <name>Alinear la firma de calculate_credit_score con entidad y reportes</name>
  <files>app/services/ai_brain.py</files>
  <action>Modificar la declaración de `credit_function` en `app/services/ai_brain.py` para incluir los parámetros `entidad` y `reportes`, y pasárselos a `self.motor_financiero.evaluate_profile` durante la ejecución de la herramienta.</action>
  <verify>uv run pytest tests/test_proactive_credit.py</verify>
  <done>La declaración y ejecución de calculate_credit_score incluyen 'entidad' y 'reportes'.</done>
</task>

<task type="auto">
  <name>Validación y Auditoría Final</name>
  <files>app/services/ai_brain.py</files>
  <action>Ejecutar npx agent-cli eval para garantizar que el score de coherencia es 1.000 y pasar todas las pruebas del sistema.</action>
  <verify>npx agent-cli eval</verify>
  <done>El pipeline de pruebas pasa completamente con un Coherence Score de 1.000.</done>
</task>

---
*Created: 2026-05-18*
