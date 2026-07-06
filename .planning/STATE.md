# Current State - Bot-TiendaLasMotos
**Versión Actual:** v10.22.9
**Último Hito:** hotfix-bot-startup-nonblocking: Implemented non-blocking background startup task (BOT-INFRA-TIMEOUT-110)
**Coherence Score:** 1.000 (207/207 Tests PASSED)

## Estado de la Ruta Crítica
- Implementación de Log Sink nativo en GCP Cloud Logging para captura de fallas de validación de catálogo (`CATALOG_VALIDATION_FAIL`) y excepciones de base de datos (`_firestore_io`).
- Desacoplamiento asíncrono asumiendo reenvíos vía tópicos de Pub/Sub con Dead Letter Topic (DLT) y Exponential Backoff en la suscripción push del webhook.
- Aislamiento en `.gcloudignore` canónico de GCP para omitir exclusiones locales y empaquetar de forma correcta.
- Enriquecimiento estructurado en `ai_brain.py` asociando `user_id` y `query` a logs forenses de error de validación.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 128 | Lifespan non-blocking background initialization and guards | 2026-07-06 | 0082ec3 | 128-bot-startup-nonblocking-110 |
| 127 | Startup locking, timeout fail-fast and webhook 503 guards | 2026-07-06 | a16e29d | 127-bot-startup-lock-109 |
| 126 | Normalizar formato Ficha Tecnica y revertir flexibilización en orquestador | 2026-07-06 | c2b142e | 126-bot-perf-align-108 |
| 125 | Flexibilizar regex de Ficha Tecnica en AgenticOrchestrator | 2026-07-06 | 0d68f16 | 125-bot-perf-align-107 |
| 124 | Purge duplicate local catalog service and use singleton | 2026-07-06 | bc4ae40 | 124-bot-arq-singleton-106 |
| 105 | Double buffering in CatalogService.load_catalog | 2026-07-06 | cf4d660 | 105-hotfix-catalog-double-buffer |
| 123 | Align _LangfuseContextShim interface | 2026-07-06 | fba73eb | 123-hotfix-bot-telemetry-123 |
| 122 | Promoción de rama beta a main para release v10.22.5 | 2026-07-06 | 4b5c45c | 122-promocion-a-main-v10.22.5 |
| 121 | Stateless alignment of catalog context for the Judge Service in whatsapp.py | 2026-07-06 | c26943a | 121-hotfix-bot-judge-alignment |
| 119 | Forensic trace extraction for search_catalog tool call rejection | 2026-07-05 | 96c5eee | 119-hotfix-bot-study-120 |
| 118 | Drift Interceptor alias literal validation failure | 2026-07-05 | 5388b02 | 118-hotfix-bot-bugfix-118 |
| 117 | Dynamic motorcycle keywords and catalog tool validation turn | 2026-07-05 | 13bf040 | 117-hotfix-bot-bugfix-117 |
| 115 | Cold Start Drift Interceptor logic restoration | 2026-07-05 | 58738b0 | 115-hotfix-bot-bugfix-115 |
| 114 | webhook redundant config load protection | 2026-07-05 | 1d55c41 | 114-hotfix-bot-perf-114 |
| 068 | webhook blocking sync awaits | 2026-06-25 | 114e0a0 | 068-hotfix-webhook-sync-block |
| 069 | corregir mock namespace en test zombie | 2026-06-26 | a07a42b | 069-hotfix-test-namespace-patch |
| 070 | hotfix reset recovery idempotencia post-borrado | 2026-06-26 | b96b716 | 070-hotfix-reset-recovery |
| 071 | webhook trace propagation | 2026-06-26 | a7379b8 | 071-hotfix-trace-propagation |
| 072 | install k6 binary in qa-pipeline.yml | 2026-06-27 | 2853b67 | 072-hotfix-ci-k6-binary |
| 075 | replace gpg keyserver with atomic curl pipeline for k6 | 2026-06-27 | 8de00f4 | 075-hotfix-ci-k6-gpg |
| 076 | dynamic HMAC signature in k6 test (crypto.hmac) | 2026-06-27 | 2fc3e2d | 076-hotfix-k6-dynamic-hmac |
| 077 | calibrar umbrales k6 a latencias reales LLM+Firestore | 2026-06-27 | 054e56b | 077-hotfix-k6-thresholds |
| 078 | ajustar umbrales k6 para CI hardware (p95<30s, p99<40s) | 2026-06-27 | a1a6e89 | 078-hotfix-k6-ci-hardware-thresholds |
| 079 | hotfix-ci-uv-cache | 2026-07-02 | bea7ab7 | 079-hotfix-ci-uv-cache |
| 080 | Log Sink y Pub Sub Alerting | 2026-06-28 | 23640bb | 080-log-sink-pubsub-alerting |
| 081 | hotfix-anonymous-quota | 2026-06-30 | 5eeb5d6 | 081-hotfix-anonymous-quota |
| 082 | hotfix-brain-return-contingency | 2026-06-30 | 28cf79c | 082-hotfix-brain-return-contingency |
| 083 | hotfix-meta-e2e-alignment | 2026-06-30 | c93b898 | 083-hotfix-meta-e2e-alignment |
| 084 | hotfix-e2e-exception-shortcircuit | 2026-07-01 | 9545720 | 084-hotfix-e2e-exception-shortcircuit |
| 085 | hotfix-brain-habeas-moto-interest | 2026-07-01 | 24554cd | 085-hotfix-brain-habeas-interest |
| 086 | hotfix-habeas-premature-block | 2026-07-01 | 262fd1d | 086-hotfix-habeas-premature-block |
| 087 | hotfix bypass interceptor collision | 2026-07-02 | 0df70dc | 087-hotfix-bypass-interceptor-collision |
| 089 | hotfix-catalog-import-leak | 2026-07-02 | e5df74a | 089-hotfix-catalog-import-leak |
| 090 | hotfix-blind-quota-parity | 2026-07-02 | b87291a | 090-hotfix-blind-quota-parity |
| 091 | hotfix-sticker-habeas | 2026-07-02 | 1d28f47 | 091-hotfix-sticker-habeas |
| 092 | hotfix-catalog-interceptor | 2026-07-02 | 47ef061 | 092-hotfix-catalog-interceptor |
| 094 | hotfix-async-firestore-stream | 2026-07-02 | da56b17 | 094-hotfix-async-firestore-stream |
| 096 | hotfix-tool-phase-isolation | 2026-07-02 | f94b830 | 096-hotfix-tool-phase-isolation |
| 099 | bot-brain-alignment (synonym inject, prompt purge, hard-cap, TTL) | 2026-07-03 | 06bd7b3 | 099-bot-brain-alignment |
| 100 | qa-semantic-plumbing (7 prompt interception tests) | 2026-07-03 | 922e776 | 100-qa-semantic-plumbing |
| 101 | bot-arch-state-101 (Tool Rejection Pattern) | 2026-07-03 | 4059ae0 | 101-bot-arch-state-101 |
| 102 | bot-resilience-102 (Drift Interceptor & Null Masking) | 2026-07-04 | 07743c0 | 102-bot-resilience-102 |
| 103 | bot-resilience-103 (Bypass de Drift Interceptor & logging) | 2026-07-04 | 76c193c | 103-bot-resilience-103 |
| 104 | bot-resilience-104 (Decouple catalog aliases & remove circular imports) | 2026-07-04 | a6f43b4 | 104-bot-resilience-104 |
| 111 | hotfix-bot-revert-111 (Reversión dura al Ticket 104) | 2026-07-04 | ba3947f | 111-hotfix-bot-revert-111 |
| 113 | Semiautomatica Casing Collision | 2026-07-05 | 2d15eff | 113-hotfix-bot-bugfix-113 |


- v10.13.1: hotfix-anonymous-quota: Cuotas de simulación ciega preventivas y anonimización de Brilla de Gases.
- v10.14.0: hotfix-brain-return-contingency: Resolución de la contingencia de retorno de PermissionError en `ai_brain.py` y robustecimiento de aserciones en test.
- v10.14.1: hotfix-meta-e2e-alignment: Resolución de la fuga de contexto en contingencias de PermissionError y robustecimiento del parser de precios.
- v10.15.0: hotfix-e2e-exception-shortcircuit: Excepción `HabeasDataBypassInterrupt` para cortocircuito limpio del while loop en `pensar_respuesta`.
- v10.15.2: hotfix-habeas-premature-block: Remoción quirúrgica del interceptor `PermissionError` prematuro (BOT-SEC-42) que colisionaba con `HabeasDataBypassInterrupt` en `calculate_credit_score`. Flujo linealizado con bifurcación `is_accepted`. Coherence Score: 1.000 (159/159 Tests PASSED).
- v10.15.3: hotfix-bypass-interceptor-collision: Intercepción directa de HabeasDataBypassInterrupt en el router de WhatsApp para aprobación inmediata con cuota ciega y script legal sin pasar por el supervisor. Coherence Score: 1.000 (169/169 Tests PASSED).
- v10.15.4: hotfix-catalog-import-leak: Exposición explícita de CatalogService en app/services/__init__.py para restablecer la paridad de inicialización y contención quirúrgica de fuga de contexto en HabeasDataBypassInterrupt. Coherence Score: 1.000 (170/170 Tests PASSED).
- v10.15.5: hotfix-blind-quota-parity: Cuota inicial exacta del 10% del precio obtenido y copywriting del PASO 3 en la rama ciega de calculate_credit_score. Coherence Score: 1.000 (170/170 Tests PASSED).
- v10.15.6: hotfix-sticker-habeas: Normalización de stickers afirmativos a 'Sí' y captura de HabeasDataBypassInterrupt en media handler. Coherence Score: 1.000 (171/171 Tests PASSED).
- v10.15.7: hotfix-catalog-interceptor: Expansión de sinónimos coloquiales, fallback de coincidencia de tokens y contingencias anti-vacías en búsqueda de catálogo. Coherence Score: 1.000 (171/171 Tests PASSED).
- v10.16.2: hotfix-async-firestore-stream: Aislamiento de operaciones de I/O síncronas de Firestore (.stream()) del event loop de FastAPI usando asyncio.to_thread() en 6 callsites del webhook y en /refresh_catalog. Coherence Score: 1.000 (162/162 Tests PASSED).
- v10.17.0: hotfix-tool-phase-isolation: Aislamiento de calculate_credit_score de PHASE_1_PROFILING. La herramienta de crédito solo se inyecta en PHASE_2_HABEAS_DATA y PHASE_3_CREDIT_PROFILING. Coherence Score: 1.000 (162/162 Tests PASSED).
- v10.18.0: bot-brain-alignment-099: Inyección dinámica de `category_aliases` (sinónimos regionales) en el System Prompt. Purga condicional de 'REGLA DE CREDITO CIEGO' cuando `calculate_credit_score` no está en el toolset. Hard-cap de 2 function calls por turn. TTL `dispatch_deadline=120s` en Cloud Tasks. Coherence Score: 1.000 (168/169 Tests PASSED — 1 pre-existing failure).
- v10.18.1: qa-semantic-plumbing-100: 7 tests de intercección de prompt (`test_semantic_plumbing.py`) asertando presencia/ausencia de `<diccionario_sinonimos_regionales>`, purga de `REGLA DE CREDITO CIEGO`, hard-cap y aplanamiento de Firestore indexed-dict. Coherence Score: 1.000 (175/176 Tests PASSED).
- v10.18.2: bot-arch-state-101: Reversión de exclusión de calculate_credit_score en Fase 1, eliminación de purga de prompt y desarrollo del Tool Rejection Pattern en ejecución. Coherence Score: 1.000 (186/186 Tests PASSED).
- v10.19.0: bot-resilience-102: Flexibilización del Drift Interceptor (umbral a 0.30), Null Masking opcional para summary/descripcion, y fallback de imágenes. Coherence Score: 1.000 (189/189 Tests PASSED).
- v10.19.1: bot-resilience-103: Bypass del Drift Interceptor para alias regionales y coincidencia parcial de modelos de moto con logging explícito (Zero-Silent-Failures). Coherence Score: 1.000 (191/191 Tests PASSED).
- v10.21.0: bot-resilience-104: Desacoplamiento de alias de catálogo y resolución de importación circular deadlock en caliente. Coherence Score: 1.000 (192/192 Tests PASSED).
- v10.22.1: hotfix-bot-perf-114: Restauración del blindaje asíncrono en la inicialización del webhook y suite de pruebas unitarias. Coherence Score: 1.000 (195/195 Tests PASSED).
- v10.22.2: hotfix-bot-bugfix-115: Restauración de la bifurcación lógica de Cold Start en el Drift Interceptor y aserciones de test. Coherence Score: 1.000 (197/197 Tests PASSED).
- v10.22.3: hotfix-bot-bugfix-117: Refactorización dinámica del interceptor de palabras clave de motocicletas e integración del test de alias. Coherence Score: 1.000 (198/198 Tests PASSED).
- v10.22.4: hotfix-bot-bugfix-118: Drift Interceptor alias literal validation failure on compuesto/conectores. Coherence Score: 1.000 (198/198 Tests PASSED).
