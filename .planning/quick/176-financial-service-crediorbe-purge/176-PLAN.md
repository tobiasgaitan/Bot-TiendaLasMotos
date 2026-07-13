---
task: 176
name: Purga de Crediorbe y configuración dinámica
description: Refactorizar app/services/financial_service.py para remover condicionales rígidos de crediorbe, cambiar la entidad por omisión a Brilla de Gases, y ajustar la simulación genérica.
---

# Quick Task 176: Purga de Crediorbe y configuración dinámica

## Objective
Remover de raíz todas las condicionales y parches rígidos vinculados a la entidad 'crediorbe' en `app/services/financial_service.py` y dinamizar el motor basándolo al 100% en configuraciones de Firestore.

## Tasks

<task type="auto">
  <name>Auditar tests para documentar por qué no detectaron la desviación</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>Correr pytest en tests/test_agentic_loop_async.py y analizar las aserciones de cuota rígidas.</action>
  <verify>pytest tests/test_agentic_loop_async.py</verify>
  <done>Explicación documentada en la respuesta al usuario.</done>
</task>

<task type="auto">
  <name>Refactorizar financial_service.py</name>
  <files>app/services/financial_service.py</files>
  <action>Purgar referencias rígidas a 'crediorbe', cambiar el valor default del parámetro 'entidad' en `calculate_payment` a 'Brilla de Gases', y actualizar respuestas genéricas y de fallback para Brilla.</action>
  <verify>python3 -c "from app.services.financial_service import financial_service; print(financial_service.calcular_cuota(11100000.0, 1500000.0, 24))"</verify>
  <done>financial_service.py sin referencias hardcodeadas de crediorbe y con firma actualizada.</done>
</task>

<task type="auto">
  <name>Ejecutar pruebas unitarias y verificar score de coherencia</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>Ejecutar npx agent-cli eval para comprobar el 100% de éxito y score de coherencia 1.000.</action>
  <verify>npx agent-cli eval</verify>
  <done>Suite de pruebas exitosa y Coherence Score = 1.000.</done>
</task>

---
*Created: 2026-07-13*
