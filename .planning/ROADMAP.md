# Roadmap - Bot-TiendaLasMotos
 
## Tasks Completadas (v10.45.12)
- [x] Desacoplar la validación de tamaño mínimo del catálogo del inicio del contenedor y del endpoint de salud `/health` en `app/main.py` (permitiendo HTTP 200 y `"status": "starting"` inmediato) y confinar el bloqueo rígido de tamaño del catálogo (len >= 60) exclusivamente dentro de los middlewares de WhatsApp en `app/routers/whatsapp.py` [BOT-INFRA-BUGFIX-HEALTH-PORT-BINDING-192].
- [x] Refactorizar `skip_greeting` en `ai_brain.py` para impedir bypass del saludo en el primer contacto/reset de la sesión (`has_no_legitimate_history = True`), e implementar la validación del guardrail de inicialización de catálogo robustecido en `webhook_handler` y `task_processor` de `whatsapp.py` validando que la caché de Firestore contenga al menos `settings.min_catalog_items` (60 ítems) en producción, con bypass controlado para pruebas unitarias (`is_test_mode`) [BOT-BRAIN-BUGFIX-FIRST-CONTACT-ALIGNMENT-191].
- [x] Inyectar un retardo asíncrono no bloqueante estricto de 2 segundos (await asyncio.sleep(2)) al inicio absoluto de '_run_deferred_initialization' en app/main.py y actualizar el caso de prueba 'test_deferred_init_port_available_before_hydration' para verificar la responsividad inmediata del puerto 8080 en '/health' [BOT-BACKEND-BUGFIX-LIFESPAN-DELAY-190].
- [x] Eliminar el bloque de inicialización síncrona a nivel de módulo en app/main.py que bloqueaba Uvicorn antes de abrir el puerto 8080 en Cloud Run. Mover toda la inicialización pesada (Firestore, Secret Manager, ConfigLoader, CatalogService) a un asyncio.create_task() background lanzado desde el lifespan handler. Health endpoint con status degradado "starting"/"healthy" [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188].
- [x] Refactorizar la validación perimetral alfabética en CatalogService para aplicar normalización fonética antes de SequenceMatcher en tokens cortos (<= 5 caracteres), agregar whitelist de tokens numéricos (500, 125, 150, 160, 200, 100), y forzar síncronamente el skip_greeting y actualizar moto_interest en ai_brain.py ante coincidencia en caliente del catálogo [BOT-BACKEND-BUGFIX-CATALOG-PERIMETER-187].
- [x] Refactorizar el método `_assemble_skip_greeting_prompt` en `app/services/ai_brain.py` para evitar que la ausencia de `moto_interest` en `prospect_data` genere un error de referencia (falso negativo) cuando el usuario transiciona de una consulta de categoría a un modelo específico, permitiendo la búsqueda prioritaria en el catálogo [BOT-BACKEND-BUGFIX-ROUTER-GREETING-ALIGNMENT-186].
- [x] Modificar el motor de prompts en app/services/ai_brain.py para unificar de forma determinista el comportamiento de saludos. Si skip_greeting es True, se suprime/reescribe cualquier instrucción conflictiva del PASO 1 o reglas de presentación de forma dinámica en tiempo de ejecución (Runtime Prompt Assembly), inyectando una regla inquebrantable de iniciar la respuesta directamente con la presentación de la motocicleta [BOT-BACKEND-BUGFIX-ROUTER-GREETING-ALIGNMENT-185].
- [x] Reescribir por completo el flujo de Brilla de Gases en app/services/financial_service.py eliminando parches estáticos y alineando secuencialmente el cálculo paso a paso en Python con TypeScript (precio de catálogo base amortizable, matrícula docsTotal y cuota_aval_mensual) [BOT-BACKEND-FINANCIAL-CASCADING-EXACT-PARITY-184].
- [x] Equalización de la matriz de Firestore de Brilla de Gases (anular la adición lineal de 'seguro_vida' flat de 15,000 COP) cuando uso_matriz es True, delegando el cobro amortizado al coeficiente compuesto, y alineando las aserciones de tests correspondientes (BOT-BACKEND-FINANCIAL-MATRIX-EQUALIZATION-182).
- [x] Omitir el cobro lineal flat de 'cuota_aval_mensual' en Phase 3 del motor financiero cuando se utiliza el factor de la matriz de Firestore (uso_matriz == True), resolviendo el doble cobro e inflación de cuotas en WhatsApp, y alineando las aserciones correspondientes en la suite de tests (BOT-BACKEND-FINANCIAL-FACTOR-ALIGNMENT-181).
- [x] Estructuración del motor financiero y alineamiento de aserciones rígidas en `test_pcc_ficha_tecnica.py` e `integration` tests, erradicando Crediorbe de la simulación ciega preventiva, arrojando excepciones explícitas ante fallos de gRPC o NoneType, y curando la polución de estado global en tests (BOT-BACKEND-FINANCIAL-TYPE-STRICT-ALIGNMENT-180).
- [x] Refactorizar de forma quirúrgica el módulo `app/services/ai_brain.py` para dinamizar las variables de asignación financiera, removiendo Crediorbe de la simulación preventiva y sustituyendo por Brilla de Gases, alineando asimismo las aserciones de tests unitarios (BOT-BACKEND-ORCHESTRATOR-ALIGNMENT-177).
- [x] Refactorizar `app/services/financial_service.py` para remover condicionales rígidos de crediorbe, cambiar la entidad por omisión a Brilla de Gases, y ajustar la simulación genérica y fallback defensivo (BOT-BACKEND-FINANCIAL-PURGE-175).
- [x] Alinear de forma rígida todos los flags `skip_greeting` en las llamadas satélites de `whatsapp.py` e implementar aserciones rígidas de argumentos (`assert_called_with`) en los tests (BOT-BACKEND-HOTFIX-ROUTER-BRANCH-ALIGNMENT-175).
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
*Last updated: 2026-07-16*
