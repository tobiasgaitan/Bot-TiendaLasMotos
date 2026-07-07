---
task: 133
name: Hotfix Catalog Identity
description: Corregir la desalineación de la Capa de Identidad en search_items para otorgar máxima prioridad (+20,000) cuando un token de búsqueda limpia coincida exactamente con los elementos del arreglo searchBy (tags de catálogo) provistos por Firestore.
---

# Quick Task 133: Hotfix Catalog Identity

## Objective
Asegurar que si cualquier token de query_tokens se encuentra presente de forma exacta dentro del arreglo item.get('searchBy', []), la variable name_match se fuerce a True, otorgando máxima prioridad (+20,000) en el catalog scoring.

## Tasks

<task type="auto">
  <name>Modificar la Capa de Identidad en catalog_service.py</name>
  <files>app/services/catalog_service.py</files>
  <action>Modificar la sección de 'IDENTITY DETECTION' en app/services/catalog_service.py para evaluar si algún token de la consulta coincide de forma exacta con los tags de catálogo de Firestore (searchBy), forzando name_match a True.</action>
  <verify>.venv/bin/pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>El test de Ficha Técnica pasa con éxito y el score de coherencia general se mantiene en 1.000.</done>
</task>

---
*Created: 2026-07-06*
