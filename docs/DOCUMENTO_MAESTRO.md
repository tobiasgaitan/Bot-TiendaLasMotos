🛡️ Documento Maestro: Estado de Desarrollo Core (v10.47.5)
Versión: v10.47.5 (Milestone 3 Etapa 4 — CIERRE DE FASE OPERATIVO & CERTIFIED)
Estado: PRODUCTION READY / GCP LIVE
Coherence Score: 1.000 (Certificado vía GSD Framework - 516/516 Tests PASSED, 0 failed)

🚀 Últimos Hitos Consolidados (Línea de Producción)

1.  Cierre Certificado Milestone 3 - Etapa 4 (v10.47.5):  Operatividad completa del flujo E2E desde el enganche inicial hasta el CIERRE DE FASE sin timeouts ni reinicios. Persistencia garantizada de los 8 datos de la matriz de perfilamiento en Firestore. Deuda técnica residual documentada (saludo repetitivo cosmético en matriz, entidad "Crediorbe" obsoleta en fallback). Certificación: 516 tests PASSED, Coherence 1.000 — DEPLOY AUTHORIZED.

2.  FIX-SUMMARY-MOTO-INTEREST-001 (v10.47.4):  REGLA DE PIVOTE en generate_summary (L2746 ai_brain.py). Si el usuario menciona marca de competencia (ej. Boxer) pero el bot ofrece equivalente del catálogo (TVS Sport 100), el extractor DEBE persistir el modelo del catálogo, NO dejar vacío. Erradicación de instrucción obsoleta "déjalo vacío o no la extraigas". Preservación de contexto tras primer turno de competencia.

3.  FIX-MATRIX-RESTART-001 (v10.47.3):  Mapeo semántico de ingresos_mensuales (L124-127 ai_brain.py). Enmienda ADITIVA de descripción del campo en EXTRACTION_SCHEMA: "Dos mínimos" → "3411810", "Tres mínimos" → "5117715", "2 palos" → "2000000", "500 mil" → "500000". Bias negativo acotado: vacío SOLO si no se mencionaron ingresos; si se mencionó en CUALQUIER forma, NUNCA dejar vacío. Persistencia garantizada en Firestore.

4.  FIX-CATALOG-PROFILE-001-AMPLIADO-v2 (v10.47.2):  Erradicación de instrucciones obsoletas en PHASE_3_CREDIT_PROFILING. FIX-A (L1616-1623): Reemplazo de instrucción obsoleta "Ejecuta calculate_credit_score ¡DETENTE AQUÍ!" por "MATRIZ DE PERFILAMIENTO (8 datos) → CIERRE DE FASE". FIX-B (L1779-1790): Condicionamiento de CRITICAL IDENTITY RULE por fase (anti-saludos en PHASE_3). FIX-C (L1346): Actualización de descripción de herramienta (eliminación de "Paso 9" inexistente). Erradicación de bloqueo de 3 minutos.

5.  FIX-CATALOG-PROFILE-001-AMPLIADO (v10.47.1):  Blindaje integral del flujo de perfilamiento crediticio. FIX-1: Carga dinámica de searchBy para marcas de competencia (Boxer → TVS Sport 100). FIX-2A: Timeout asíncrono de 25s para llamadas Gemini. FIX-2B: Presupuesto de reintentos para transitorios (5xx, candidatos vacíos). FIX-4A: 5 campos STRING en EXTRACTION_SCHEMA (ingresos_mensuales, gastos_mensuales, plan_celular, tiene_gas_natural, mora_y_paz_salvo). FIX-4B: Checklist determinista de perfilamiento (_build_profiling_checklist L512-568). Certificación: 501 passed + 2 subtests, Coherence 1.000.

6.  Milestone 3 Etapa 4 Inicial (v10.47.0):  Coherence Audit, Prompt XML Refactor & Blind Credit Backend Fallback. Reestructuración semántica de juan_pablo_personality con separación estricta por bloques XML. Migración de lógica de valores fijos (SMLV, parámetros ciegos de crédito) al backend. Consolidación de reglas de catálogo y manejo de competencia.

📊 Matriz Histórica de Cambios y Estabilidad (v10.0.0 a v10.47.5)

| Versión / Ticket | Componente Afectado | Descripción del Ajuste Quirúrgico y Protección Core |
|------------------|---------------------|-----------------------------------------------------|
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

📋 Estado Actual del Embudo Comercial "Juan Pablo"

**PASO 1 (Enganche de Valor):** Saludo condicional + search_catalog + Visual-Lock (imagen + precio). Pivote de competencia habilitado (Boxer → TVS Sport 100).

**PASO 2 (Simulación Ciega Anticipada):** calculate_credit_score con datos ciegos (Brilla de Gases, SMLV, 10% inicial). Timeout 25s + reintentos.

**PASO 3 (Entrega de Cuota Enganche):** Lectura de JSON + entrega de cuota aproximada (24 meses) + script de Habeas Data.

**PASO 4 (Muro Legal):** Autorización de política de privacidad (Ley 1581). habeas_data_accepted → true.

**PASO 5 (Identidad y Transición):** Nombre + Ciudad (Sanitize PII: 50 chars máx). Transición a MATRIZ_DE_PERFILAMIENTO_ESTRICTA.

**MATRIZ (8 datos):** Ocupación → Contrato → Ingresos (mapeo semántico) → Datacrédito → Gastos → Gas Natural → Vivienda → Plan Celular. Checklist determinista (_build_profiling_checklist).

**CIERRE DE FASE:** Evaluación de puntaje → 4 rutas (Banco de Bogotá ≥750, Revisión humana 500-749, Brilla <499, Rechazo <499 sin Brilla).

⚠️ Deuda Técnica Residual Documentada

1.  **Saludo repetitivo en matriz (cosmético):** El bot continúa diciendo "¡Hola, Carlos!" en cada turno de la matriz. FIX-B no está funcionando completamente. Impacto: UX, no funcional. Ticket pendiente: BOT-BUILD-FIX-SALUDO-RESIDUAL-001.

2.  ~~**Entidad "Crediorbe" obsoleta**~~ **RESUELTO (BOT-BUILD-FIX-E-CREDIORBE-ERADICATION-001):** personality.json PASO 2 re-sincronizado a "Brilla de Gases"; rama FINTECH purgada de scoring_service (score 400-699 → fallback Brilla); intercepción Crediorbe (BOT-FIN-104) purgada de ai_brain.py; defaults y fallbacks de config_service/config_loaders unificados; seed script actualizado. Pendiente paso operativo manual: borrar doc `financial_config/general/financieras/crediorbe` en Firestore prod.

3.  **Pregunta genérica en FAQ brake (L508):** _get_pending_funnel_question PHASE_3 retorna pregunta genérica en lugar de <siguiente_pendiente> del checklist. Ticket pendiente: FIX-D (v2.1).

🎯 Próximos Pasos (Milestone 3 - Etapas 5, 6, 7)

**Etapa 5:** Resolución de Concurrencia y Aislamiento de Código Legado (fragmentación de _handle_message_background_impl, Algoritmo de Feathers, erradicación de background tasks).

**Etapa 6:** Blindaje Conductual del Agente (FIX-B Ampliado, FIX-E re-sync, validadores coercitivos 4 líneas/350 chars).

**Etapa 7:** Sincronización GSD (/gsd-sync), Certificación de Coherencia (npx agent-cli eval ≥0.9), Despliegue (npx agent-cli deploy → publish).