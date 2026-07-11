---
task: 152
name: Hotfix Catalog Identity Calibration
description: BOT-PERF-IDENTITY-CALIBRATION-122 — Boost de identidad (+20,000) no se activa ante variaciones tipográficas/fonéticas con ratio >= 0.85
---

# Quick Task 152: Hotfix Catalog Identity Calibration

## Objective
Retroalimentar `name_match = True` dinámicamente cuando el ratio de similitud global del nombre (`difflib.SequenceMatcher`) supere 0.85, garantizando que el boost de identidad (+20,000) en `_apply_scoring_adaptor` sea activado para variaciones como "rider" → "Raider" sin inyectar alias manuales al `spelling_map`.

## Diagnóstico Real (Autopsia Física)

- `name_match` SÍ está declarada en el scope (L494) — no hay `NameError`.
- El bug es de LÓGICA: el `ratio` calculado en el Paso 3 (L553) es completamente independiente del flag `name_match`.
- Consecuencia: ratio >= 0.85 solo suma puntos de fuzzy (ratio*60) pero NO activa el boost +20,000 del Tier 1 del adaptador.
- El fix correcto es añadir un cuarto camino de detección ANTES de la llamada al adaptador que convierta ratio >= 0.85 en `name_match = True`.

## Tasks

<task type="auto">
  <name>Añadir Fuzzy Identity Escalation en search_items</name>
  <files>app/services/catalog_service.py</files>
  <action>
    Después de calcular `ratio = difflib.SequenceMatcher(None, clean_query, name_clean).ratio()` (L553),
    añadir bloque condicional: `if ratio >= 0.85 and not name_match: name_match = True`.
    Esto retroalimenta el flag ANTES de `_apply_scoring_adaptor` activando el boost Tier 1 (+20,000).
  </action>
  <verify>python3 -c "from app.services.catalog_service import CatalogService; cs = CatalogService(); print('OK — CatalogService importa correctamente')"</verify>
  <done>El flag name_match se eleva a True cuando ratio >= 0.85, activando el boost +20,000 en el adaptador.</done>
</task>

<task type="auto">
  <name>Añadir caso de prueba 'rider' en test suite</name>
  <files>tests/test_catalog_identity.py</files>
  <action>
    Crear o actualizar test con aserción rígida: search_items("rider") debe retornar la moto "Raider"
    como primer resultado con score implícito en el nombre del item retornado.
  </action>
  <verify>npx agent-cli eval</verify>
  <done>229/229 pruebas exitosas incluyendo el nuevo caso "rider" → "Raider".</done>
</task>

---
*Created: 2026-07-10*
