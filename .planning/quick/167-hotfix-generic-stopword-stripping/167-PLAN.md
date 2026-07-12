---
task: 167
name: Hotfix Generic Stopword Stripping
description: "[BOT-BACKEND-HOTFIX-GENERIC-STOPWORD-STRIPPING-167] Implementar conjunto estático COMMERCIAL_STOPWORDS para filtrar tokens genéricos ('motos', 'moto', 'motocicleta', 'motocicletas') de query_alphabetic_tokens antes del bucle de validación perimetral has_alphabetic_match."
---

# Quick Task 167: Hotfix Generic Stopword Stripping

## Objective
Filtrar tokens comerciales genéricos residuales del array `query_alphabetic_tokens` en `CatalogService.search_items` para que consultas compuestas como 'Motos pisteras' no provoquen falsos negativos en el perímetro alfabético de BOT-BACKEND-CATALOG-THRESHOLD-163.

## Causa Raíz (Verificada Físicamente)
- **Archivo**: `app/services/catalog_service.py`, línea 630
- `query_alphabetic_tokens = [t for t in query_tokens if len(t) >= 2 and not t.isdigit()]`
- Para query `"Motos pisteras"`, los tokens resultantes incluyen `"motos"`. El token `"motos"` entra al bucle perimetral y evalúa contra cada ítem. Como ningún ítem tiene `"motos"` en sus `searchBy` ni en `name_tokens`, fuerza `has_alphabetic_match = False` antes de que tokens intencionales como `"deportiva"` puedan rescatar el match.

## Tasks

<task type="auto">
  <name>Inyectar COMMERCIAL_STOPWORDS en catalog_service.py</name>
  <files>app/services/catalog_service.py</files>
  <action>
    Después de la línea 630 (generación de query_alphabetic_tokens), añadir:
    1. Set estático COMMERCIAL_STOPWORDS = {"motos", "moto", "motocicleta", "motocicletas"}
    2. Filtro: query_alphabetic_tokens = [t for t in query_alphabetic_tokens if t not in COMMERCIAL_STOPWORDS]
    3. Comentario forense referenciando este ticket
  </action>
  <verify>python3 -c "from app.services.catalog_service import CatalogService; s = CatalogService(); print('OK')"</verify>
  <done>El módulo importa sin error y el filtro existe en el código</done>
</task>

<task type="auto">
  <name>Expandir test suite con casos compuestos de stopwords genéricas</name>
  <files>tests/test_agentic_loop_async.py</files>
  <action>
    Añadir función `test_catalog_generic_stopword_stripping()` con aserciones para:
    - "Motos pisteras" → retorna items de categoría 'deportiva'
    - "Motos scooters" → retorna items de categoría 'moped'
    - "motocicleta pistera" → retorna items de categoría 'deportiva'
    Verificar que result no es None y len > 0 con aserciones de contenido
  </action>
  <verify>npx agent-cli eval 2>&1 | tail -5</verify>
  <done>247/247 Tests PASSED, Coherence Score 1.000</done>
</task>

---
*Created: 2026-07-12*
