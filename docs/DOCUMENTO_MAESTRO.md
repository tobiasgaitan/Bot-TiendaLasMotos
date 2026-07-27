🛡️ Documento Maestro: Estado de Desarrollo Core (v10.48.0)
Versión: v10.48.0 (Milestone 3 Etapa 6 — BLINDAJE CONDUCTUAL DEL AGENTE & CERTIFIED)
Estado: PRODUCTION READY / GCP LIVE
Coherence Score: 1.000 (Certificado vía GSD Framework - 638/638 Tests PASSED, 0 failed)

🚀 Últimos Hitos Consolidados (Línea de Producción)

1.  Blindaje Conductual del Agente e Integridad del Embudo - Etapa 6 (v10.48.0) [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001 / #M3-ETAPA6-001]:  Cuatro blindajes certificados. (a) URL-Lock anti-alucinación en la capa de egreso (egress_guard_service.py): whitelist default-deny (firebasestorage.googleapis.com / tiendalasmotos.com / slm.bancodebogota.com), sustitución automática contra el SSOT del catálogo (match normalizado → stem único → tokens únicos) y extirpación sin candidato; degradado imagen→texto; integrado en los 3 puntos de egreso pre-Meta. (b) Validadores coercitivos de longitud <REGLAS_DE_LONGITUD_Y_CONCISION_WHATSAPP>: truncado por \n (máx 4 líneas) y luego por caracteres (máx 350), con preservación de la pregunta de cierre y exención de anclas legales protegidas (script cuota PASO 3/4). (c) Deuda residual erradicada: FIX-B Ampliado (guard anti-saludo por dato `ocupacion` truthy, independiente de la fase-string, + supresor coercitivo de prefijo post-generación), FIX-D (_evaluate_profiling_matrix como SSOT único + mapa canónico de 8 preguntas; genérico hardcoded eliminado), FIX-E (sync_full_prompt.py como CANAL ÚNICO con read-back forense: triple aserción sobre Firestore prod archivada en scripts/evidence/ — paridad byte-exacta SHA-256 verificada, 0 "Crediorbe", "Brilla de Gases"/"nuestro sistema" presentes; guard continuo en suite). (d) Intercepción semántica FAQ vs. Embudo con anclaje de contexto en 3 capas: Capa A (function_response de query_faq con pregunta pendiente VERBATIM), Capa B (freno FAQ saneado, sin referencia muerta <credit_matrix_rules>, rama COMPLETO), Capa C (guard coercitivo post-generación en PHASE_3: re-inyección determinista de la pregunta de la matriz si el LLM cambia de tema). Certificación: 638 tests PASSED, Coherence 1.000 — DEPLOY AUTHORIZED.

2.  Cierre Certificado Milestone 3 - Etapa 4 (v10.47.5):  Operatividad completa del flujo E2E desde el enganche inicial hasta el CIERRE DE FASE sin timeouts ni reinicios. Persistencia garantizada de los 8 datos de la matriz de perfilamiento en Firestore. Certificación: 516 tests PASSED, Coherence 1.000 — DEPLOY AUTHORIZED.

2.  FIX-SUMMARY-MOTO-INTEREST-001 (v10.47.4):  REGLA DE PIVOTE en generate_summary (L2746 ai_brain.py). Si el usuario menciona marca de competencia (ej. Boxer) pero el bot ofrece equivalente del catálogo (TVS Sport 100), el extractor DEBE persistir el modelo del catálogo, NO dejar vacío. Erradicación de instrucción obsoleta "déjalo vacío o no la extraigas". Preservación de contexto tras primer turno de competencia.

3.  FIX-MATRIX-RESTART-001 (v10.47.3):  Mapeo semántico de ingresos_mensuales (L124-127 ai_brain.py). Enmienda ADITIVA de descripción del campo en EXTRACTION_SCHEMA: "Dos mínimos" → "3411810", "Tres mínimos" → "5117715", "2 palos" → "2000000", "500 mil" → "500000". Bias negativo acotado: vacío SOLO si no se mencionaron ingresos; si se mencionó en CUALQUIER forma, NUNCA dejar vacío. Persistencia garantizada en Firestore.

4.  FIX-CATALOG-PROFILE-001-AMPLIADO-v2 (v10.47.2):  Erradicación de instrucciones obsoletas en PHASE_3_CREDIT_PROFILING. FIX-A (L1616-1623): Reemplazo de instrucción obsoleta "Ejecuta calculate_credit_score ¡DETENTE AQUÍ!" por "MATRIZ DE PERFILAMIENTO (8 datos) → CIERRE DE FASE". FIX-B (L1779-1790): Condicionamiento de CRITICAL IDENTITY RULE por fase (anti-saludos en PHASE_3). FIX-C (L1346): Actualización de descripción de herramienta (eliminación de "Paso 9" inexistente). Erradicación de bloqueo de 3 minutos.

5.  FIX-CATALOG-PROFILE-001-AMPLIADO (v10.47.1):  Blindaje integral del flujo de perfilamiento crediticio. FIX-1: Carga dinámica de searchBy para marcas de competencia (Boxer → TVS Sport 100). FIX-2A: Timeout asíncrono de 25s para llamadas Gemini. FIX-2B: Presupuesto de reintentos para transitorios (5xx, candidatos vacíos). FIX-4A: 5 campos STRING en EXTRACTION_SCHEMA (ingresos_mensuales, gastos_mensuales, plan_celular, tiene_gas_natural, mora_y_paz_salvo). FIX-4B: Checklist determinista de perfilamiento (_build_profiling_checklist L512-568). Certificación: 501 passed + 2 subtests, Coherence 1.000.

6.  Milestone 3 Etapa 4 Inicial (v10.47.0):  Coherence Audit, Prompt XML Refactor & Blind Credit Backend Fallback. Reestructuración semántica de juan_pablo_personality con separación estricta por bloques XML. Migración de lógica de valores fijos (SMLV, parámetros ciegos de crédito) al backend. Consolidación de reglas de catálogo y manejo de competencia.

📊 Matriz Histórica de Cambios y Estabilidad (v10.0.0 a v10.47.5)

| Versión / Ticket | Componente Afectado | Descripción del Ajuste Quirúrgico y Protección Core |
|------------------|---------------------|-----------------------------------------------------|
| BOT-PLAN-HARDENING-EGRESS-FUNNEL-001 (v10.48.0) | egress_guard_service.py (nuevo); whatsapp.py (3 puntos de egreso); ai_brain.py (anclas certificadas); scripts/sync_full_prompt.py | URL-Lock default-deny + sustitución SSOT catálogo + extirpación; coerción 4 líneas/350 chars con preservación de pregunta; FIX-B Ampliado (guard por `ocupacion` + supresor prefijo); FIX-D (_evaluate_profiling_matrix SSOT + mapa 8 preguntas); FIX-E (canal único de sync + read-back forense Firestore prod); anclaje FAQ 3 capas. |
| BOT-BUILD-FIX-SUMMARY-MOTO-INTEREST-001 (v10.47.4) | ai_brain.py (L2746) | REGLA DE PIVOTE en generate_summary: extraer modelo de catálogo ofrecido (TVS Sport 100), NO marca de competencia (Boxer). Preservación de contexto en primer turno. |
| BOT-BUILD-FIX-MATRIX-RESTART-001 (v10.47.3) | ai_brain.py (L124-127) | Mapeo semántico de ingresos_mensuales: "Dos mínimos" → "3411810", "Tres mínimos" → "5117715", "2 palos" → "2000000". Persistencia garantizada en Firestore. |
| BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO-v2 (v10.47.2) | ai_brain.py (L1616-1623, L1779-1790, L1346) | Erradicación de instrucciones obsoletas: PHASE_3 instruction (anti-bloqueo 3min), CRITICAL IDENTITY RULE condicionada por fase, descripción de herramienta actualizada (sin "Paso 9"). |
| BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO (v10.47.1) | ai_brain.py (múltiples) | FIX-1: searchBy dinámico; FIX-2A: Timeout 25s Gemini; FIX-2B: Presupuesto reintentos; FIX-4A: 5 campos EXTRACTION_SCHEMA; FIX-4B: Checklist determinista (_build_profiling_checklist). |
| BOT-BACKEND-188 | app/main.py | Migración de inicialización pesada (Firestore, Secret Manager) a asyncio.create_task() background desde lifespan handler. |
| BOT-BACKEND-187 | CatalogService | Normalización fonética previa a SequenceMatcher en tokens cortos (≤5 caracteres) y whitelist de cilindrajes (100, 125, 150, 160, 200, 500). |
| BOT-FINANCIAL-184 | financial_service.py | Sincronización secuencial estricta paso a paso del flujo Brilla de Gases en Python en paridad exacta con lógica TypeScript. |
| BOT-FINANCIAL-181 | Phase 3 Financial | Omisión de cobro flat de cuota_aval_mensual y seguro_vida cuando uso_matriz == True para erradicar inflación de cuotas en WhatsApp. |
| BOT-INFRA-33 | _firestore_io | Interceptor de I/O con asyncio.wait_for limitado a 5s para evitar congelamiento de sockets y mitigar ráfagas concurrentes. |
| BOT-ROUTER-120 | whatsapp.py | Implementación de Locks de Sesión asíncronos (asyncio.Lock) por número E.164. Serializa webhooks para asegurar commit en Firestore. |
| BOT-INFRA-171 | MessageBuffer | Guardrail de idempotencia síncrona en frontera mediante register_wamid con bloqueo por sesión para fulminar duplicados de Meta. |
| BOT-PERF-41 | CatalogService | Caché semántica local con bypass inmediato del LLM si score fuzzy es ≥0.85, reduciendo 100% consumo innecesario de tokens. |
| BOT-SEC-50 | S-TOON_Middleware | Jaula de Faraday virtual mediante tags `<S_START>` y `<S_END>` para blindar entradas contra Prompt Injections estructurales. |
| BOT-QA-LOOP-107 | CerebroIA | Bucle agéntico asíncrono de auto-reparación. Si falla formato visual, reintenta automáticamente hasta N_max=3 con temperatura 0.1. |

🏛️ Directivas Inmutables de Arquitectura

1.  **Mandato de Bloqueo CRM (_CRM_PROTECTED_FIELDS):** Queda estrictamente prohibido que el motor de extracción de la IA pise, degrade o modifique las cuotas financieras reales o campos manuales introducidos por el asesor comercial.

2.  **Zero-Silent-Failures:** Queda terminantemente prohibido capturar excepciones genéricas sin inyectar un log forense estructurado completo (logger.exception). Toda contingencia de red o timeout debe retornar un _ContingencySnapshot controlado.

3.  **Visual-Lock (PCC Pro):** Toda respuesta que mencione una motocicleta debe incluir de forma obligatoria el precio formateado ($) y la imagen estructurada en Markdown nativo (![]()) recuperada de search_catalog.

4.  **REGLA DE PIVOTE (v10.47.4):** Si el usuario menciona marca de competencia pero el bot ofrece equivalente del catálogo, el extractor DEBE persistir el modelo del catálogo en moto_interest, NO dejar vacío.

5.  **Mapeo Semántico de Ingresos (v10.47.3):** El extractor DEBE mapear expresiones coloquiales ("Dos mínimos", "2 palos", "500 mil") a valores numéricos exactos. Bias negativo: vacío SOLO si no se mencionaron ingresos.

6.  **Gobernanza de Fuentes de Verdad:** SSOT Documental = docs/BUSINESS_RULES.md (guía de estilo y reglas de negocio para humanos). SSOT de Ejecución = campo `searchBy` del catálogo en Firestore + prompt `juan_pablo_personality` (sync vía scripts/sync_full_prompt.py). En caso de divergencia, prevalece siempre el SSOT de Ejecución.

📋 Estado Actual del Embudo Comercial "Juan Pablo"

**PASO 1 (Enganche de Valor):** Saludo condicional + search_catalog + Visual-Lock (imagen + precio). Pivote de competencia habilitado (Boxer → TVS Sport 100).

**PASO 2 (Simulación Ciega Anticipada):** calculate_credit_score con datos ciegos (Brilla de Gases, SMLV, 10% inicial). Timeout 25s + reintentos.

**PASO 3 (Entrega de Cuota Enganche):** Lectura de JSON + entrega de cuota aproximada (24 meses) + script de Habeas Data.

**PASO 4 (Muro Legal):** Autorización de política de privacidad (Ley 1581). habeas_data_accepted → true.

**PASO 5 (Identidad y Transición):** Nombre + Ciudad (Sanitize PII: 50 chars máx). Transición a MATRIZ_DE_PERFILAMIENTO_ESTRICTA.

**MATRIZ (8 datos):** Ocupación → Contrato → Ingresos (mapeo semántico) → Datacrédito → Gastos → Gas Natural → Vivienda → Plan Celular. Checklist determinista (_build_profiling_checklist).

**CIERRE DE FASE:** Evaluación de puntaje → 4 rutas (Banco de Bogotá ≥750, Revisión humana 500-749, Brilla <499, Rechazo <499 sin Brilla). **(BOT-BUILD-FIX-CIERRE-4-RUTAS-002: reexpresión doctrinal — disparo JSON-driven: el LLM INVOCA calculate_credit_score y lee el score numérico del JSON; erradicada la alucinación "evalúa el puntaje crediticio simulado internamente" de personality.json y prompts.py. Las 4 rutas son inmutables y tienen PRIORIDAD ABSOLUTA sobre el function response. Backend: mandato coercitivo [MANDATO DE CIERRE DE FASE] cuando el checklist alcanza COMPLETO + logs terminales [AI FALLBACK REASON] en agotamiento de reintentos.)**

⚠️ Deuda Técnica Residual Documentada

1.  ~~**Saludo repetitivo en matriz (cosmético)**~~ **RESUELTO (v10.48.0 — FIX-B Ampliado, BOT-PLAN-HARDENING-EGRESS-FUNNEL-001):** guard estático por dato `ocupacion` truthy (independiente de la fase-string) en la inyección de prompt + supresor coercitivo de prefijo post-generación (`_strip_leading_greeting`). Pin estático anti-regresión en tests.

2.  ~~**Entidad "Crediorbe" obsoleta**~~ **RESUELTO y CERRADO FORENSEMENTE (v10.48.0 — FIX-E re-sync, BOT-PLAN-HARDENING-EGRESS-FUNNEL-001):** `scripts/sync_full_prompt.py` ejecutado como CANAL ÚNICO contra Firestore prod (`configuracion/juan_pablo_personality.system_instruction`): deriva detectada (10101 vs 10328 chars) y corregida; triple aserción post-sync archivada en `scripts/evidence/` (paridad byte-exacta SHA-256, 0 "Crediorbe", presencia "Brilla de Gases"/"nuestro sistema"). Guard continuo en suite (`tests/test_fix_e_firestore_parity_guard.py`, subprocess aislado). Residual operativo manual (ajeno al prompt): borrar doc `financial_config/general/financieras/crediorbe` en Firestore prod.

3.  ~~**Pregunta genérica en FAQ brake (L508)**~~ **RESUELTO (v10.48.0 — FIX-D, BOT-PLAN-HARDENING-EGRESS-FUNNEL-001):** `_get_pending_funnel_question` PHASE_3 evalúa la matriz vía `_evaluate_profiling_matrix` (SSOT compartido con `_build_profiling_checklist`) y retorna la pregunta exacta del mapa canónico de 8 entradas; rama COMPLETO → mandato de cierre de fase. Genérico hardcoded erradicado con pin estático.

🎯 Próximos Pasos (Milestone 3 - Etapas 5, 7)

**Etapa 5:** Resolución de Concurrencia y Aislamiento de Código Legado (fragmentación de _handle_message_background_impl, Algoritmo de Feathers, erradicación de background tasks).

**Etapa 6:** ✅ CERRADA (v10.48.0) — Blindaje Conductual del Agente ejecutado y certificado [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001]: FIX-B Ampliado, FIX-E re-sync forense, validadores coercitivos 4 líneas/350 chars, URL-Lock, anclaje FAQ. Hallazgos colaterales H-COL-1 (tono) y H-COL-2 parcial (BUSINESS_RULES vs catálogo): ~~cuarentena C5 por mandato expreso~~ **RESUELTOS (2026-07-27 — cuarentena C5 levantada, intervención 100% documental):** H-COL-1 — script de BUSINESS_RULES.md alineado a primera persona singular ("No manejo la [Moto_Competencia]..."), en paridad verbatim con el prompt vivo; H-COL-2 — bloque "Gobernanza de Datos" insertado en BUSINESS_RULES.md (SSOT Documental vs SSOT de Ejecución + Regla de Precedencia) y Directiva Inmutable #6 (Gobernanza de Fuentes de Verdad).

**Etapa 7:** Sincronización GSD (/gsd-sync), Certificación de Coherencia (npx agent-cli eval ≥0.9), Despliegue (npx agent-cli deploy → publish).