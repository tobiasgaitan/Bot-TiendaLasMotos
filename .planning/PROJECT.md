# Proyecto: Asesor de Auteco Las Motos

## Vision
Desarrollar e implementar un pipeline inteligente y robusto para el bot de WhatsApp de Auteco Las Motos, incluyendo comparación por similitud multimodal, caché semántica, y flujos de precalificación de créditos síncronos con blindaje legal de Habeas Data.

## Core Value
Garantizar la consistencia de precios (PCC Pro) y la precisión en la recomendación de vehículos reales del catálogo en Firestore, reduciendo alucinaciones y falsos positivos mediante alineación por similitud fonética, semántica y multimodal (imágenes).

## Target Users
* **Usuarios de WhatsApp:** Reciben respuestas con precios exactos, imágenes correctas y fichas técnicas correspondientes.
* **Operadores de Negocio:** Mantienen control total sobre las motocicletas recomendadas y el cumplimiento legal de Habeas Data.

## Technical Context
* **Backend:** Python 3.13 / FastAPI / Vertex AI / Google GenAI SDK.
* **Persistencia:** Firestore (`prospectos`, `pagina/catalogo/items`).
* **Multimodalidad:** Gemini 2.5 Flash para visión y análisis general.

## Requirements

### Active
- [ ] R7: Alinear imágenes entrantes en WhatsApp con `imagen_url` canónica en Firestore (Milestone 2).
- [ ] R8: Implementar `match_catalog_item_by_image` en `CatalogService` con prioridad ID -> URL -> SequenceMatcher (Milestone 2).
- [ ] R9: Validar integridad (Anti-Null Masking) de ítems del catálogo inyectados a Vision AI (Milestone 2).
- [ ] R10: Sincronizar el interés del prospecto (`moto_interest`) sin evadir el flujo legal de Habeas Data (Milestone 2).

---
*Last updated: 2026-07-11*