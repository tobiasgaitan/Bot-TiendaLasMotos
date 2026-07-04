---
task: 104
name: bot-resilience-104
description: Erradicar congelamiento/timeout en producción eliminando la importación dinámica circular de config_service en ai_brain.py y exponiendo get_catalog_aliases() directamente en CatalogService.
---

# Quick Task 104: bot-resilience-104

## Objective
El objetivo de esta tarea es eliminar la importación dinámica circular de `config_service` en `ai_brain.py` expuesta a fallos concurrentes de Import Lock en Cloud Run, implementando el método `get_catalog_aliases()` directamente en `CatalogService` (el cual devuelve los alias pre-cargados en memoria) y adaptando `ai_brain.py` para consumirlo de forma segura e independiente.

## Tasks

<task type="auto">
  <name>Implementar get_catalog_aliases en CatalogService</name>
  <files>[app/services/catalog_service.py]</files>
  <action>Agregar el método `get_catalog_aliases(self) -> Dict[str, List[str]]` a `CatalogService` en `app/services/catalog_service.py` para devolver los alias aplanados, limpios y validados de `self._category_aliases`.</action>
  <verify>Ejecutar `python3 -c "from app.services.catalog_service import catalog_service; print('Desacoplamiento exitoso:', catalog_service)"`</verify>
  <done>El método devuelve un diccionario de listas de strings limpio de valores nulos o vacíos, y el módulo se puede importar y usar sin dependencias externas bloqueantes.</done>
</task>

<task type="auto">
  <name>Refactorizar ai_brain.py para usar CatalogService y eliminar importación de config_service</name>
  <files>[app/services/ai_brain.py]</files>
  <action>Modificar el Drift Interceptor (línea 1245) y la inyección de sinónimos del prompt (línea 945) en `app/services/ai_brain.py` para usar `self._catalog_service.get_catalog_aliases()`. Prohibir estrictamente el uso de `from app.services.config_service import config_service` en estas funciones, implementando logs explícitos ante fallas de obtención conforme a Zero-Silent-Failures.</action>
  <verify>Ejecutar `./.venv/bin/pytest tests/test_interceptor_blindaje.py` y `./.venv/bin/pytest`</verify>
  <done>Las pruebas locales unitarias e integrales pasan al 100%, y el Coherence Score se mantiene en 1.000.</done>
</task>

---
*Created: 2026-07-04*
