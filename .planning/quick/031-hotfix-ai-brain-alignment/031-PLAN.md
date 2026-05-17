---
task: 031
name: hotfix-ai-brain-alignment
description: Corrección de regresión en app/services/ai_brain.py alineando la herramienta search_catalog con el contrato estructurado search_items de CatalogService.
---

# Quick Task 031: hotfix-ai-brain-alignment

## Objective
Corregir la regresión en app/services/ai_brain.py reemplazando el método obsoleto `search_catalog` con `search_items` de CatalogService, inicializando todas las variables locales para evitar `UnboundLocalError`, implementando re-raise síncrono para errores (Anti-Null Masking), y agregando casos de prueba que validen el formato de Ficha Técnica y el control de excepciones.

## Tasks

<task type="auto">
  <name>Refactorizar el bloque de la herramienta search_catalog en ai_brain.py</name>
  <files>app/services/ai_brain.py</files>
  <action>Modificar el bloque `elif f_name == "search_catalog":` en [ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py) para inicializar explícitamente variables, llamar a `search_items`, formatear dinámicamente el resultado a Markdown con la etiqueta `Ficha Tecnica:`, validar que las llaves requeridas no sean nulas ni vacías, e implementar el re-raise de excepciones en el bloque except.</action>
  <verify>.venv/bin/pytest tests/test_perf_45.py</verify>
  <done>El código de ai_brain.py está refactorizado según los guardrails y el archivo pasa las pruebas existentes.</done>
</task>

<task type="auto">
  <name>Agregar pruebas unitarias de aserción de contenido y fallos en test_perf_45.py</name>
  <files>tests/test_perf_45.py</files>
  <action>Añadir nuevos casos de prueba en [test_perf_45.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/tests/test_perf_45.py) que validen que la ejecución del catálogo produce la cadena "Ficha Tecnica:" y que un fallo en el catálogo o la ausencia de llaves críticas lanza un ValueError/Exception explícito sin enmascaramiento nulo.</action>
  <verify>.venv/bin/pytest tests/test_perf_45.py</verify>
  <done>Los nuevos tests de aserción y control de fallos pasan exitosamente.</done>
</task>
