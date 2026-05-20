---
task: 037
name: Brilla Entity Switch and Crediorbe Intercept
description: Conmutación proactiva de simulación de crédito ciego hacia Brilla, extensión de EXTRACTION_SCHEMA para captura de cédula e intercepción de links digitales de Crediorbe.
---

# Quick Task 037: Brilla Entity Switch and Crediorbe Intercept

## Objective
Conmutar la simulación de crédito ciego por defecto a Brilla de Gases, permitir extraer cedula_usuario en el esquema de la IA, e interceptar Crediorbe en la resolución de herramientas bloqueando el link digital y orientando al usuario a sedes físicas.

## Tasks

<task type="auto">
  <name>Modificar prompts.py</name>
  <files>
    <file>app/core/prompts.py</file>
  </files>
  <action>Cambiar la regla del Crédito Ciego de 'crediorbe' a 'Brilla de Gases' y actualizar la instrucción de Habeas Data (Paso 2).</action>
  <verify>.venv/bin/pytest tests/test_brilla_conmutacion.py</verify>
  <done>Las referencias a Crediorbe en Crédito Ciego y Habeas Data se han cambiado a Brilla de Gases.</done>
</task>

<task type="auto">
  <name>Modificar financial_service.py</name>
  <files>
    <file>app/services/financial_service.py</file>
  </files>
  <action>Cambiar entidad_default de Crediorbe a Brilla de Gases en _generate_full_simulation_response.</action>
  <verify>.venv/bin/pytest tests/test_brilla_conmutacion.py</verify>
  <done>La entidad por defecto en simulación de crédito es Brilla de Gases.</done>
</task>

<task type="auto">
  <name>Modificar ai_brain.py</name>
  <files>
    <file>app/services/ai_brain.py</file>
  </files>
  <action>Extender el objeto properties de extracted para añadir cedula_usuario con bias negativo. Interceptar calculate_credit_score para Crediorbe bloqueando res['link_url'] e inyectando instrucciones comerciales específicas.</action>
  <verify>.venv/bin/pytest tests/test_brilla_conmutacion.py</verify>
  <done>El esquema incluye cedula_usuario y las llamadas a Crediorbe están interceptadas.</done>
</task>

<task type="auto">
  <name>Crear y ejecutar test_brilla_conmutacion.py</name>
  <files>
    <file>tests/test_brilla_conmutacion.py</file>
  </files>
  <action>Implementar la prueba pytest assertando las nuevas funcionalidades.</action>
  <verify>.venv/bin/pytest tests/test_brilla_conmutacion.py</verify>
  <done>La prueba de no-regresión pasa correctamente.</done>
</task>

---
*Created: 2026-05-20*
