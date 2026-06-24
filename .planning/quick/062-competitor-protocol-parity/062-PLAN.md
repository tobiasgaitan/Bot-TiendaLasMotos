---
task: 062
name: Implementación de pruebas y paridad de Protocolo de Competencia
description: Falta de cobertura y validación automatizada para el Protocolo de Competencia dentro de catalog_service.py.
---

# Quick Task 062: Implementación de pruebas y paridad de Protocolo de Competencia

## Objective
Añadir pruebas unitarias a `tests/test_catalog_scoring.py` para asegurar que el Protocolo de Competencia (pivotaje basado en `searchBy` / marcas rivales como 'NKD') funciona correctamente, y que los resultados del catálogo retornan las llaves del payload visual ('price', 'image_url') sin valores nulos o vacíos silenciosos, y validando la presencia de 'Ficha Tecnica:'.

## Tasks

<task type="auto">
  <name>Inyectar pruebas de paridad en test_catalog_scoring.py</name>
  <files>tests/test_catalog_scoring.py</files>
  <action>Modificar `tests/test_catalog_scoring.py` para inyectar ítems con tags `searchBy` de competencia y agregar métodos de test para validar el pivotaje, el formato del payload visual y la presencia de la cadena "Ficha Tecnica:" sin nulos ni vacíos.</action>
  <verify>.venv/bin/pytest tests/test_catalog_scoring.py</verify>
  <done>Todos los tests pasan con éxito y sin fallos.</done>
</task>

---
*Created: 2026-06-24*
