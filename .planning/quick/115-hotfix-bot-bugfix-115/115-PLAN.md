---
task: 115
name: hotfix-bot-bugfix-115
description: Restaura la bifurcación lógica de Cold Start en el callsite del Drift Interceptor dentro de app/services/ai_brain.py y asegura el bypass correcto en sesiones sin moto de interés previa.
---

# Quick Task 115: hotfix-bot-bugfix-115

## Objective
Restaurar la bifurcación lógica de Cold Start en el callsite del Drift Interceptor dentro de `app/services/ai_brain.py` para prospectos con interés vacío (`moto_interest` vacío o `None`), asegurando que las búsquedas no sean bloqueadas incorrectamente y que los alias válidos de categorías (ej. 'señoritera') sean procesados correctamente por el bypass del interceptor.

## Tasks

<task type="auto">
  <name>Refactorizar Drift Interceptor en ai_brain.py</name>
  <files>app/services/ai_brain.py</files>
  <action>Reemplazar la validación del Drift Interceptor en `app/services/ai_brain.py` para entrar al bloque si `moto_interest_prev` no es `None` y aplicar la bifurcación para Cold Start (cuando `moto_interest_prev` es vacío o nulo) iterando sobre el diccionario de alias normalizados y aplicando normalización estricta (.lower().strip()).</action>
  <verify>./.venv/bin/pytest tests/test_drift_alias_bypass.py</verify>
  <done>La suite de pruebas pasa exitosamente y no hay bloqueos en búsquedas válidas.</done>
</task>

<task type="auto">
  <name>Actualizar Suite de Pruebas test_drift_alias_bypass.py</name>
  <files>tests/test_drift_alias_bypass.py</files>
  <action>Integrar las pruebas unitarias `test_drift_alias_bypass_cold_start` y `test_drift_normal_search_cold_start` que simulen explícitamente el escenario de Cold Start (moto_interest='') y aserten el bypass correcto.</action>
  <verify>./.venv/bin/pytest tests/test_drift_alias_bypass.py</verify>
  <done>Las aserciones de Cold Start pasan limpiamente.</done>
</task>

---
*Created: 2026-07-05*
