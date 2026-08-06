# Roadmap - Bot-TiendaLasMotos
 
## Tasks Completadas (v10.47.5+)
- [x] **AUD-CIERRE-RUTAS-010 (v10.54.0): Rediseño de la doctrina de CIERRE DE FASE** [app/core/prompts.py, app/core/personality.json, app/services/scoring_service.py, app/services/ai_brain.py, tests/test_cierre_rutas_010.py, tests/test_brilla_conmutacion.py, tests/test_fix_catalog_profile_001.py]. Vía A: prompt reescrito y sincronizado a Firestore vía `scripts/sync_full_prompt.py` (triple aserción + evidencia en `scripts/evidence/`). Vía B: enforcement determinista POST-JSON con `resolve_cierre_route`; `score`/`strategy`/`entity` del JSON inalterados; campo aditivo `cierre_ruta`; logger forense. Doctrina: R1 ≥750 Banco; R2 500-749 revisión humana; R3 ≤499+gas afirmativo Brilla; R4 ≤499+gas negativo rechazo. Certificación: **689 tests PASSED, Coherence Score 1.000**.
- [x] **AUD-FP-AUTO-REG-009 (v10.53.1): Fix temporal R1∧R2 en auto-fill forma_pago="Crédito"** [app/services/memory_service.py, tests/test_forma_pago_autofill_007.py]. Relajación R1/R2 en capa ALT-1 con R3 intacta; reconciliación pin B-3; T8/T9 aditivos. Cero cambios en `ai_brain.py`, `juan_pablo_personality`, `whatsapp.py`, `_merge_extracted_data` ni espejos dashboard. Certificación: **684 tests PASSED, Coherence Score 1.000**.
- [x] **AUD-DEUDA-DASH-008 (v10.53.0): Extensión del writer de score_resultado a media y fallback del Juez** [app/routers/whatsapp.py, tests/test_score_persist_media_fallback_008.py]. Protocolo F2 read-only en `prospectos/` (9 docs): 0 llaves dashboard fantasma → clasificación (i) muertas/vestigiales. G1–G5 consumen `_score_resultado` y reutilizan `persist_credit_score_result` (transacción padre+historial, bucket 300s). Sin cambios en `ai_brain.py`, `juan_pablo_personality`, `catalog_service.py`, `pagina/catalogo/items`, `normalize_imagen_url.py`, `reset`; sin backfill. HANDOFF intacto. Certificación: **682 tests PASSED, Coherence Score 1.000**.
- [x] **O1 (v10.52.1): Erradicación catalog_items + agent-cli publish NO-OP** [attic/backup, attic/seed_catalog.py, docs, scripts/buscar_y_destruir.py]. Backup bloqueante, borrado de 4 docs en Firestore prod, seed archivado, SSOT `pagina/catalogo/items` documentado. Certificación: **673 tests PASSED, Coherence Score 1.000**.
- [x] **AUD-FP-AUTO-007 (v10.52.0): Auto-fill determinista forma_pago="Crédito"** [memory_service.py, whatsapp.py]. Denominador 673.
- [x] **AUD-SCORE-PERSIST-001 (v10.51.0): Persistencia atómica score_resultado** [memory_service.py, ai_brain.py, whatsapp.py]. Denominador 666.
- [x] **Etapa 4 (Milestone 3): Cierre de Fase Operativo & Certified** [BOT-BUILD-FIX-SUMMARY-MOTO-INTEREST-001, BOT-BUILD-FIX-MATRIX-RESTART-001, BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO-v2, BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO]. Flujo E2E completo certificado desde enganche inicial hasta CIERRE DE FASE sin timeouts ni reinicios. Persistencia garantizada de los 8 datos de la matriz de perfilamiento en Firestore. Deuda técnica residual documentada (saludo repetitivo cosmético, entidad "Crediorbe" obsoleta, pregunta genérica FAQ brake). Certificación: **516 tests PASSED, Coherence Score 1.000** (arnés eval 516).
    - **FIX-SUMMARY-MOTO-INTEREST-001 (v10.47.4):** REGLA DE PIVOTE en generate_summary. Si el usuario menciona marca de competencia pero el bot ofrece equivalente del catálogo, el extractor DEBE persistir el modelo del catálogo, NO dejar vacío.
    - **FIX-MATRIX-RESTART-001 (v10.47.3):** Mapeo semántico de ingresos_mensuales. Enmienda ADITIVA de descripción del campo en EXTRACTION_SCHEMA: "Dos mínimos" → "3411810", "Tres mínimos" → "5117715", etc.
    - **FIX-CATALOG-PROFILE-001-AMPLIADO-v2 (v10.47.2):** Erradicación de instrucciones obsoletas en PHASE_3_CREDIT_PROFILING. Reemplazo de instrucción obsoleta por "MATRIZ DE PERFILAMIENTO (8 datos) → CIERRE DE FASE".
    - **FIX-CATALOG-PROFILE-001-AMPLIADO (v10.47.1):** Blindaje integral del flujo de perfilamiento crediticio. Carga dinámica de searchBy, timeout 25s, reintentos, 5 campos STRING en EXTRACTION_SCHEMA, checklist determinista.
- [x] **Etapa 3 (Milestone 3): Concurrencia y Fragmentación RF-5 del God Node whatsapp.py** [BOT-BUILD-ETAPA3-WAVE01…WAVE06]. Seis waves certificadas. Red de caracterización Feathers, higiene asíncrona, costuras DI, fragmentación pipelines, latencia forense. Certificación: **431/431 tests + 2 subtests, Coherence Score 1.000**.
- [x] **Incidente H-A (Milestone 3 Etapa 2):** Saneamiento forense del historial Git y reestructuración del arnés de pruebas [BOT-BUILD-INCIDENT-HA-201]. Rotación T0 credenciales, erradicación is_test_mode, mocking dinámico, 8 validadores regex PCC Pro + Sanitize PII. Certificación: 378/378 tests PASSED, Coherence Score 1.000.
- [x] Erradicar vulnerabilidad concurrente en Singletons de configuración (ConfigLoader y FinanceConfigLoader) mediante RLock interno y commit atómico. 367/367 tests verdes [BOT-BUILD-REFACTOR-03-05-RESIDUAL].
- [x] Restaurar enrutamiento de intención técnica en payloads visuales (imagen + caption) con ampliación de TECH_SPEC_TOKENS y Visual Lock. 368/368 tests [BOT-BUILD-BUGFIX-MULTIMODAL-CAPTION-01].
- [x] Saneamiento agresivo de credenciales en config.py (.strip()) + test unitario [BOT-INFRA-BUGFIX-TOKEN-STRIP-194].
- [x] Endpoint /health con HTTP 200 inmediato + desacople validación catálogo [BOT-INFRA-BUGFIX-HEALTH-PORT-BINDING-192].
- [x] Refactorizar skip_greeting en ai_brain.py + guardrail catálogo en whatsapp.py [BOT-BRAIN-BUGFIX-FIRST-CONTACT-ALIGNMENT-191].
- [x] Retardo asíncrono 2s en _run_deferred_initialization [BOT-BACKEND-BUGFIX-LIFESPAN-DELAY-190].
- [x] Inicialización pesada movida a asyncio.create_task() en lifespan [BOT-BACKEND-BUGFIX-CONTAINER-CRASH-188].
- [x] Validación perimetral con normalización fonética + whitelist numérica [BOT-BACKEND-BUGFIX-CATALOG-PERIMETER-187].
- [x] _assemble_skip_greeting sin error ante ausencia de moto_interest [BOT-BACKEND-BUGFIX-ROUTER-GREETING-ALIGNMENT-186].
- [x] Unificación determinista de saludos con Runtime Prompt Assembly [BOT-BACKEND-BUGFIX-ROUTER-GREETING-ALIGNMENT-185].
- [x] Reescritura flujo Brilla de Gases con paridad Python/TypeScript [BOT-BACKEND-FINANCIAL-CASCADING-EXACT-PARITY-184].
- [x] Equalización matriz Brilla de Gases (anular seguro_vida flat) [BOT-BACKEND-FINANCIAL-MATRIX-EQUALIZATION-182].
- [x] Omitir cobro lineal cuota_aval_mensual cuando uso_matriz=True [BOT-BACKEND-FINANCIAL-FACTOR-ALIGNMENT-181].
- [x] Estructuración motor financiero + erradicación Crediorbe [BOT-BACKEND-FINANCIAL-TYPE-STRICT-ALIGNMENT-180].
- [x] Dinamización variables financieras + sustitución Crediorbe por Brilla [BOT-BACKEND-ORCHESTRATOR-ALIGNMENT-177].
- [x] Remover condicionales rígidos de crediorbe en financial_service.py [BOT-BACKEND-FINANCIAL-PURGE-175].
- [x] Alineación flags skip_greeting + aserciones rígidas [BOT-BACKEND-HOTFIX-ROUTER-BRANCH-ALIGNMENT-175].
- [x] Refactorización firmas cerebro_ia.pensar_respuesta + _evaluate_skip_greeting [BOT-BACKEND-BUGFIX-ROUTER-GREETING-ALIGNMENT-173].
- [x] Guardrail idempotencia síncrona con register_wamid [BOT-BACKEND-HOTFIX-WEBHOOK-IDEMPOTENCY-LOCK-171].
- [x] Validación perimetral con sinónimos regionales [BOT-BACKEND-HOTFIX-PERIMETER-COLLOQUIAL-ALIGNMENT-170].
- [x] Inicialización CatalogService con DI de ConfigLoader [BOT-BACKEND-HOTFIX-CATALOG-INITIALIZATION-SYNC-169].
- [x] Filtro stopwords conversacionales [BOT-BACKEND-HOTFIX-CONVERSATIONAL-STOPWORD-STRIPPING-168].
- [x] Filtro stopwords comerciales genéricas [BOT-BACKEND-HOTFIX-GENERIC-STOPWORD-STRIPPING-167].
- [x] Mapeo alias plural/diminutivo de categorías [BOT-BACKEND-HOTFIX-PLURAL-ALIAS-ALIGNMENT-166].
- [x] Recuperación y mapeo alias categorías catálogo [BOT-BACKEND-HOTFIX-CATALOG-ALIAS-RECOVERY-165].
- [x] Alineación observabilidad con Langfuse v4 [BOT-BRAIN-OBSERVABILITY-ALIGN-164].
- [x] Calibración umbral catálogo + aislamiento numérico [BOT-BACKEND-CATALOG-THRESHOLD-163].
- [x] Reestructuración Lifespan FastAPI + hidratación secuencial bloqueante [BOT-ARCHITECTURE-LIFESPAN-LINEAR-159].
- [x] Adaptador Local Observabilidad Langfuse v4 [BOT-BUGFIX-LANGFUSE-DECORATOR-REGRESSION].
- [x] Unificación pipeline egreso texto+imágenes [BOT-BUGFIX-UNIFIED-EGRESS-PIPELINE-125].
- [x] Corrección regex extracción URLs imágenes [BOT-BUGFIX-MARKDOWN-IMAGE-REGRESSION-122].
- [x] Actualización VisionService a gemini-2.5-flash [BOT-VISION-UPGRADE].
- [x] Enrutamiento imágenes desacoplando [MOTO_DETECTADA] [BOT-VISION-PARSER].
- [x] Sanitización y alineación fonética fuzzy audio [BOT-ROUTER-AUDIO-FUZZY-ALIGNMENT-124].
- [x] Corrección regresión procesamiento audios [BOT-BUGFIX-AUDIO-REGRESSION-121].
- [x] Cierre Milestone 2 Phase 1 (Similitud Multimodal) [BOT-BUILD-MULTIMODAL-CIERRE-196].

## Milestone 3: Refactorización Arquitectónica y Blindaje del Embudo [IN PROGRESS]

### Progress

| Phase | Name | Status | Date |
|-------|------|--------|------|
| 1 | Topología, Arqueología de Integridad y Diseño Estático (PAA) | Completed | 2026-07-15 |
| 2 | Incidente H-A (Saneamiento Historial Git y Reestructuración de Pruebas) | Completed | 2026-07-18 |
| 3 | Concurrencia y Fragmentación RF-5 (God Node whatsapp.py) | Completed | 2026-07-22 |
| 4 | Cierre de Fase Operativo & Certified | Completed | 2026-07-25 |
| O1 | Erradicación colección huérfana `catalog_items` (v10.52.1) | Completed | 2026-08-05 |
| DASH-008 | Extensión score_resultado a media/fallback del Juez (v10.53.0) | Completed | 2026-08-05 |
| REG-009 | Fix temporal R1∧R2 auto-fill forma_pago (v10.53.1) | Completed | 2026-08-06 |
| 5 | Resolución de la Concurrencia y Aislamiento de Código Legado | Pending | - |
| 6 | Blindaje Conductual del Agente e Integridad del Embudo | Pending | - |
| 7 | Sincronización GSD, Certificación de Coherencia y Despliegue | Pending | - |

### Phases

#### Phase 5: Resolución de la Concurrencia y Aislamiento de Código Legado
**Goal:** Desarticular el acoplamiento peligroso en los interceptores del enrutador de WhatsApp y restaurar las leyes de asincronía/sincronía.
- [ ] RF-5: Fragmentación de _handle_message_background_impl — Aplicación del Algoritmo de Feathers
- [ ] Valla de Chesterton: Arqueología pragmática (git blame) antes de desmantelar lógica
- [ ] Erradicación de background tasks en ejes prioritarios del embudo comercial
- [ ] Instrumentación de resiliencia: try/except + continue + logger.exception(e)

#### Phase 6: Blindaje Conductual del Agente e Integridad del Embudo "Juan Pablo"
**Goal:** Armonización final de la lógica del conector tecnológico con la superestructura inmutable del agente comercial.
- [ ] Mapeo exhaustivo de flujos superpuestos de intercepción semántica (FAQ vs. embudo)
- [ ] Blindaje de variables restringidas exclusivas del CRM (_CRM_PROTECTED_FIELDS)
- [ ] Instauración de interceptores de intención validando el bonus de recomendación comercial
- [ ] Validadores coercitivos para truncar respuestas que excedan 4 líneas / 350 caracteres
- [ ] Resolución de deuda residual de Etapa 4: FIX-B Ampliado, FIX-E

#### Phase 7: Sincronización GSD, Certificación de Coherencia y Despliegue
**Goal:** Sincronización del conocimiento, validación implacable de la estabilidad estructural, y diseminación hacia GCP Cloud Run.
- [ ] Comando /gsd-sync para consolidar Documento Maestro, STATE.md, ROADMAP.md
- [ ] Evaluación de fuego (npx agent-cli eval) — abortar si Coherence Score < 0.9
- [ ] git push origin beta + verificación de GitHub Actions
- [ ] npx agent-cli deploy (beta) → npx agent-cli publish (producción)
- [ ] Cierre de chat para mitigar Context Rot

---

## Milestone 2: Similitud Multimodal de Imagen [COMPLETED]

| Phase | Name | Status | Date |
|-------|------|--------|------|
| 1 | Similitud Multimodal e Integración | Completed | 2026-07-11 |

---
*Last updated: 2026-08-05*
