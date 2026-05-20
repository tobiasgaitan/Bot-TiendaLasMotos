---
task: 038
name: Spanish Catalog Keys Fix
description: Modificación quirúrgica de app/services/ai_brain.py para cambiar las llaves de extracción de catálogo a las propiedades reales en español de Firestore y corregir la validación anti-null masking.
---

# Quick Task 038: Spanish Catalog Keys Fix

## Objective
Modificar quirúrgicamente la herramienta `search_catalog` en `app/services/ai_brain.py` para mapear las llaves reales en español de Firestore y corregir la validación anti-null masking sin romper la indentación ni la sintaxis del archivo.

## Tasks

<task type="auto">
  <name>Mapeo de Llaves Reales en Español e Integridad de Anti-Null Masking</name>
  <files>
    <file>app/services/ai_brain.py</file>
  </files>
  <action>Mapear preferentemente las llaves 'Nombre del producto TVS', 'Descripción del producto TVS' y 'precio' en la extracción del catálogo de Firestore, y corregir la sintaxis del bloque de validación anti-null masking.</action>
  <verify>.venv/bin/pytest tests/test_brilla_conmutacion.py</verify>
  <done>Las llaves están correctamente mapeadas, los tests pasan y la sintaxis de python es válida.</done>
</task>

---
*Created: 2026-05-20*
