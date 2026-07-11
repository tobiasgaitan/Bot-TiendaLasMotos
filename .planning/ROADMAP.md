# Roadmap - Bot-TiendaLasMotos
 
## Tasks Completadas (v10.31.0)
- [x] Reestructuración del Lifespan de FastAPI y la inicialización de servicios core a nivel de módulo en app/main.py para garantizar hidratación secuencial y bloqueante (60/60 ítems devueltos) en producción y CLI, con inicialización inline en pytest (BOT-ARCHITECTURE-LIFESPAN-LINEAR-159).
- [x] Implementar Adaptador Local de Observabilidad Langfuse v4 bajo el Patrón Adaptador sin modificar site-packages ni provocar shadowing en namespaces (BOT-BUGFIX-LANGFUSE-DECORATOR-REGRESSION).
- [x] Unificar el pipeline de egreso de mensajes de texto y de imágenes en whatsapp.py para evitar Mocking Blindness y omitir la persistencia duplicada (BOT-BUGFIX-UNIFIED-EGRESS-PIPELINE-125).
- [x] Corregir la expresión regular de extracción de URLs de imágenes y purgar grupos vacíos para prevenir fallas al interceptar URLs complejas en WhatsApp (BOT-BUGFIX-MARKDOWN-IMAGE-REGRESSION-122).
- [x] Actualización del modelo multimodal de VisionService a gemini-2.5-flash e implementación de tests unitarios robustos ante payloads nulos con Zero-Silent-Failures (BOT-VISION-UPGRADE).
- [x] Corrección en el enrutamiento de imágenes de catálogo desacoplando la dependencia de '[MOTO_DETECTADA]' e inyección de logs estructurados forenses en caso de fallo (BOT-VISION-PARSER).
- [x] Sanitización y alineación fonética fuzzy de transcripción en bloque audio para resolver variaciones tipográficas degradadas (BOT-ROUTER-AUDIO-FUZZY-ALIGNMENT-124).
- [x] Corregir regresión en el procesamiento de audios mediante la inyección de la última pregunta del bot en generate_and_update_summary (BOT-BUGFIX-AUDIO-REGRESSION-121).

## Milestone 2: Similitud Multimodal de Imagen [IN PROGRESS]

### Progress

| Phase | Name | Status | Plans | Date |
|-------|------|--------|-------|------|
| 1 | Similitud Multimodal e Integración | In Progress | `implementation_plan.md` | 2026-07-11 |

### Phases

#### Phase 1: Similitud Multimodal e Integración
**Goal:** Implementar el pipeline completo de comparación de imágenes y alineación con las URLs de catálogo y metadatos de Firestore.
**Requirements:** [R7, R8, R9, R10, R11, R12]
- [ ] Implementar `match_catalog_item_by_image` en `CatalogService`
- [ ] Refinar `analyze_image` y `_process_moto` en `VisionService`
- [ ] Integrar el flujo en `whatsapp.py`
- [ ] Generar y ejecutar tests en `tests/test_multimodal_similitude.py`
- [ ] Validar no regresión y eval general

---
*Last updated: 2026-07-11*
