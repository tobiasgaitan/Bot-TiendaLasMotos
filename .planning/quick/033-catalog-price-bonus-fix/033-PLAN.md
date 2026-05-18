---
task: 033
name: Catalog Price Bonus Fix
description: Fallo crítico de colisión de nomenclatura (precio vs price) en CatalogService que contamina el capital base del simulador financiero, aplicando bonos de contado a simulaciones de crédito. Adicionalmente, omisión de serialización de las variables bonusAmount y bonusEndDate hacia la ventana de contexto del LLM.
---

# Quick Task 033: Catalog Price Bonus Fix

## Objective
Resolver la colisión de nomenclatura (precio vs price) y serializar/validar 'bonusAmount' y 'bonusEndDate' hacia el LLM con una validación rigurosa de fecha y mutación de string, garantizando un test unitario robusto y libre de fallos silenciosos.

## Tasks

<task type="auto">
  <name>Surgical Hotfix in CatalogService</name>
  <files>
    - app/services/catalog_service.py
  </files>
  <action>
    1. En 'CatalogService.load_catalog()', modificar la extracción forzando la llave canónica base: 'price_val = data.get("price") or 0'.
    2. Extraer 'bonusAmount' y 'bonusEndDate' del dict Firestore e inyectarlos en 'mapped_item'.
    3. En la función de serialización 'search_items' (truncated_item), implementar validación de fecha evaluando 'bonusEndDate' contra 'datetime.now()'.
    4. En 'search_catalog', si el bono es mayor a 0 y está vigente, mutar el string de 'search_results' para incluir explícitamente: '[BONO EXCLUSIVO DE CONTADO: $X válido hasta Y]'.
  </action>
  <verify>.venv/bin/pytest tests/test_catalog_price_bonus.py</verify>
  <done>CatalogService handles price base cleanly, extracts/validates bonus details, formats them accurately in Markdown output, and passes all tests.</done>
</task>

---
*Created: 2026-05-18*
