# Roadmap - Bot-TiendaLasMotos
 
## Tasks Completadas (v10.40.0)
- [x] Refactorización de las firmas de llamada a 'cerebro_ia.pensar_respuesta' en todas las ramas de procesamiento de 'app/routers/whatsapp.py' e implementación de '_evaluate_skip_greeting' para saludos dinámicos (BOT-BACKEND-BUGFIX-ROUTER-GREETING-ALIGNMENT-173).
- [x] Implementación de guardrail de idempotencia síncrona en la frontera del enrutador usando register_wamid de MessageBuffer para fulminar peticiones duplicadas antes de encolarlas (BOT-BACKEND-HOTFIX-WEBHOOK-IDEMPOTENCY-LOCK-171).
- [x] Refactorización de los bucles de validación perimetral alfabética en CatalogService para permitir la coincidencia de sinónimos regionales y expansiones contra search_tokens (BOT-BACKEND-HOTFIX-PERIMETER-COLLOQUIAL-ALIGNMENT-170).
- [x] Refactorización de la inicialización de CatalogService con inyección de dependencias de ConfigLoader y control fail-fast (BOT-BACKEND-HOTFIX-CATALOG-INITIALIZATION-SYNC-169).
- [x] Filtro de stopwords conversacionales (saludos, fórmulas de cortesía y verbos comerciales) en el pre-procesamiento de tokens de control alfabético en CatalogService (BOT-BACKEND-HOTFIX-CONVERSATIONAL-STOPWORD-STRIPPING-168).
- [x] Filtro de stopwords comerciales genéricas en el pre-procesamiento del perímetro alfabético en CatalogService (BOT-BACKEND-HOTFIX-GENERIC-STOPWORD-STRIPPING-167).
- [x] Mapeo flexible de alias en plural/diminutivo de categorías de catálogo con protección de colisiones en monosílabos (BOT-BACKEND-HOTFIX-PLURAL-ALIAS-ALIGNMENT-166).
- [x] Recuperación y mapeo inicial de alias de categorías de catálogo en CatalogService (BOT-BACKEND-HOTFIX-CATALOG-ALIAS-RECOVERY-165).
- [x] Alinear quirúrgicamente el módulo de observabilidad y trazas en whatsapp.py con las firmas nativas del SDK de Langfuse v4 (BOT-BRAIN-OBSERVABILITY-ALIGN-164).
- [x] Calibración de Umbral de Catálogo y Aislamiento Numérico en CatalogService para evitar colisiones de marcas y cilindrajes (BOT-BACKEND-CATALOG-THRESHOLD-163).
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
