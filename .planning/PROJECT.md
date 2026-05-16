# Proyecto: Caché Semántica de Catálogo (BOT-PERF-41)

## Vision
Implementar una capa de Caché Semántica desacoplada en `CatalogService` para optimizar drásticamente el consumo de tokens y reducir la latencia en las consultas repetitivas de inventario y tags de intención.

## Core Value
Garantizar una respuesta inmediata y formateada sin invocar la inferencia del LLM (Gemini) cuando la similitud de cadenas (N-gramas/Levenshtein) de la consulta del usuario supere el 0.85 respecto a una consulta previamente indexada, protegiendo el Price Consistency Check (PCC Pro) al 100%.

## Target Users
* **Usuarios de WhatsApp:** Experimentarán latencia casi nula en consultas frecuentes.
* **Sistema/Negocio:** Reducción drástica de costos por token y latencia cero de red externa.

## Technical Context
* **Backend:** Python 3.13 / FastAPI.
* **Similitud Local:** Algoritmos nativos en Python puro (TF-IDF ligero, Levenshtein, N-gramas). PROHIBIDO llamar a Google GenAI para embeddings.
* **Almacenamiento Local:** Diccionario en memoria RAM hidratado sincrónicamente durante el arranque (`ConfigLoader -> load_all() -> CatalogService.initialize()`). PROHIBIDO archivo JSON en disco.
* **Preservación Visual:** La caché guarda y retorna directamente el bloque Markdown final con precio (`$`) y la imagen canónica (`![]`), no el JSON crudo.

## Requirements

### Active
- [ ] R1: Crear un servicio de vectores (SemanticCacheService) para generar y almacenar embeddings y respuestas.
- [ ] R2: Interceptar `search_items`, `search` y `search_catalog` en `CatalogService`.
- [ ] R3: Calcular similitud de coseno > 0.85 para retornar hits de caché inmediatamente.
- [ ] R4: Preservar el formateo de Price Consistency Check (Regex con $ y Markdown de imagen).

## Key Decisions
| Decision | Source | Rationale | Outcome |
|----------|--------|-----------|---------|
| Similitud Coseno > 0.85 | User | Threshold para considerar un hit sin alucinar | Decided |
| Desacoplamiento | User | No alterar la lógica de búsqueda normal | Decided |
| Preservar PCC | User | Mantener formato de Regex y $ para consistencia | Decided |

---
*Last updated: 2026-05-16*