---
task: 059
name: Unificar llaves de catálogo a 'summary' y corregir condicional silencioso
description: Corregir condicional silencioso en test_pcc_ficha_tecnica.py y unificar llaves de catálogo a 'summary'
---

# Quick Task 059: Unificar llaves de catálogo a 'summary' y corregir condicional silencioso

## Objective
Unificar las llaves del catálogo a 'summary' en la lógica del bot y pruebas, y remover el condicional silencioso en el archivo de prueba de la ficha técnica.

## Tasks

<task type="auto">
  <name>Unificar llaves de catálogo y corregir condicional silencioso</name>
  <files>[tests/test_pcc_ficha_tecnica.py, app/services/ai_brain.py, tests/test_bot_bug_040.py, tests/test_brilla_conmutacion.py]</files>
  <action>Modificar los archivos de pruebas y de ai_brain.py para usar únicamente la llave 'summary' y eliminar la validación condicional silenciosa en tests/test_pcc_ficha_tecnica.py.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py tests/test_bot_bug_040.py tests/test_brilla_conmutacion.py</verify>
  <done>Todos los tests pasan con éxito.</done>
</task>

---
*Created: 2026-06-23*
