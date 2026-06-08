---
task: 041
name: Unificar Persistencia Prospectos
description: Refactorizar la capa de persistencia para eliminar la colección 'mensajeria' y unificar bajo 'prospectos/{phone}/historial'
---

# Quick Task 041: Unificar Persistencia Prospectos

## Objective
Eliminar la bifurcación de colecciones Firestore (mensajeria vs prospectos) unificando todo el historial de chat bajo `prospectos/{phone}/historial`.

## Tasks

<task type="auto">
  <name>Refactorizar memory_service.py</name>
  <files>app/services/memory_service.py</files>
  <action>Cambiar 5 métodos que apuntan a mensajeria/whatsapp/sesiones/{phone}/historial → prospectos/{phone}/historial</action>
  <verify>python -m pytest tests/test_memory_stream_coverage.py tests/test_reset_flow.py tests/test_read_asymmetry.py -v</verify>
  <done>0 referencias a .collection("mensajeria") en memory_service.py</done>
</task>

<task type="auto">
  <name>Refactorizar survey_service.py y whatsapp.py</name>
  <files>app/services/survey_service.py, app/routers/whatsapp.py</files>
  <action>Redirigir sesiones de survey y _get_session a prospectos con merge=True</action>
  <verify>grep -c 'collection("mensajeria")' app/services/survey_service.py app/routers/whatsapp.py</verify>
  <done>0 coincidencias</done>
</task>

<task type="auto">
  <name>Crear test_persistence_unification.py</name>
  <files>tests/test_persistence_unification.py</files>
  <action>Implementar suite de aserción de contenido mandatorio (Key Alignment, Ficha Tecnica, No-Mensajeria, Ruta Canónica)</action>
  <verify>python -m pytest tests/test_persistence_unification.py -v</verify>
  <done>Todos los tests pasan</done>
</task>

---
*Created: 2026-06-07*
