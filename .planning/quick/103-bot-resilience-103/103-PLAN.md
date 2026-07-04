---
task: 103
name: bot-resilience-103
description: Fallo de validación en Drift Interceptor debido a baja similitud léxica en regionalismos y categorías.
---

# Quick Task 103: bot-resilience-103

## Objective
Implementar un bypass estructural en el Drift Interceptor de `app/services/ai_brain.py` para evitar falsos positivos cuando la búsqueda del usuario (regionalismo o modelo parcial) corresponda con la moto de interés actual registrada en el prospecto, garantizando el cumplimiento de la política Zero-Silent-Failures en la captura de excepciones.

## Proposed Changes

### app/services/ai_brain.py
- Diseñar e integrar la función auxiliar `_is_synonym_or_model_match(query: str, moto_interest: str, aliases: dict) -> bool`.
- Modificar el Drift Interceptor en `pensar_respuesta` para aplicar esta validación y omitir el bloqueo (`skip_catalog = False`) si se detecta correspondencia exacta, por sub-cadena limpia de modelos, o por alias de categorías (regionalismos).
- Registrar de forma explícita mediante `logger.warning` o `logger.exception` cualquier excepción atrapada durante la obtención de los aliases del catálogo, prohibiendo el uso de bloques `except Exception: pass`.

### tests/test_interceptor_blindaje.py
- Agregar casos de prueba unitarios:
  1. `test_interceptor_bypass_synonyms`: Probar que si `moto_interest` is "scooter" y la query es "señoritera" (mapeado en `category_aliases`), el catálogo NO sea bloqueado.
  2. `test_interceptor_bypass_partial_model`: Probar que si `moto_interest` is "TVS Apache 160" y la query es "Apache" (coincidencia parcial de sub-cadena), el catálogo NO sea bloqueado.

## Verification Plan
- Ejecutar la suite completa de pruebas locales mediante:
  `./.venv/bin/pytest tests/test_interceptor_blindaje.py`
  y la suite global:
  `./.venv/bin/pytest`
- Asegurar que el Coherence Score se mantenga en 1.00.
