# Current State - Bot-TiendaLasMotos
**Versión Actual:** v10.15.6
**Último Hito:** hotfix-sticker-habeas: Normalización de stickers afirmativos a 'Sí' y captura de HabeasDataBypassInterrupt en media handler.
**Coherence Score:** 1.000 (171/171 Tests PASSED)

## Estado de la Ruta Crítica
- Implementación de Log Sink nativo en GCP Cloud Logging para captura de fallas de validación de catálogo (`CATALOG_VALIDATION_FAIL`) y excepciones de base de datos (`_firestore_io`).
- Desacoplamiento asíncrono asumiendo reenvíos vía tópicos de Pub/Sub con Dead Letter Topic (DLT) y Exponential Backoff en la suscripción push del webhook.
- Aislamiento en `.gcloudignore` canónico de GCP para omitir exclusiones locales y empaquetar de forma correcta.
- Enriquecimiento estructurado en `ai_brain.py` asociando `user_id` y `query` a logs forenses de error de validación.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 068 | webhook blocking sync awaits | 2026-06-25 | 114e0a0 | 068-hotfix-webhook-sync-block |
| 069 | corregir mock namespace en test zombie | 2026-06-26 | a07a42b | 069-hotfix-test-namespace-patch |
| 070 | hotfix reset recovery idempotencia post-borrado | 2026-06-26 | b96b716 | 070-hotfix-reset-recovery |
| 071 | webhook trace propagation | 2026-06-26 | a7379b8 | 071-hotfix-trace-propagation |
| 072 | install k6 binary in qa-pipeline.yml | 2026-06-27 | 2853b67 | 072-hotfix-ci-k6-binary |
| 075 | replace gpg keyserver with atomic curl pipeline for k6 | 2026-06-27 | 8de00f4 | 075-hotfix-ci-k6-gpg |
| 076 | dynamic HMAC signature in k6 test (crypto.hmac) | 2026-06-27 | 2fc3e2d | 076-hotfix-k6-dynamic-hmac |
| 077 | calibrar umbrales k6 a latencias reales LLM+Firestore | 2026-06-27 | 054e56b | 077-hotfix-k6-thresholds |
| 078 | ajustar umbrales k6 para CI hardware (p95<30s, p99<40s) | 2026-06-27 | a1a6e89 | 078-hotfix-k6-ci-hardware-thresholds |
| 079 | hotfix-ci-uv-cache | 2026-06-27 | bea7ab7 | 079-hotfix-ci-uv-cache |
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

- v10.13.1: hotfix-anonymous-quota: Cuotas de simulación ciega preventivas y anonimización de Brilla de Gases.
- v10.14.0: hotfix-brain-return-contingency: Resolución de la contingencia de retorno de PermissionError en `ai_brain.py` y robustecimiento de aserciones en test.
- v10.14.1: hotfix-meta-e2e-alignment: Resolución de la fuga de contexto en contingencias de PermissionError y robustecimiento del parser de precios.
- v10.15.0: hotfix-e2e-exception-shortcircuit: Excepción `HabeasDataBypassInterrupt` para cortocircuito limpio del while loop en `pensar_respuesta`.
- v10.15.2: hotfix-habeas-premature-block: Remoción quirúrgica del interceptor `PermissionError` prematuro (BOT-SEC-42) que colisionaba con `HabeasDataBypassInterrupt` en `calculate_credit_score`. Flujo linealizado con bifurcación `is_accepted`. Coherence Score: 1.000 (159/159 Tests PASSED).
- v10.15.3: hotfix-bypass-interceptor-collision: Intercepción directa de HabeasDataBypassInterrupt en el router de WhatsApp para aprobación inmediata con cuota ciega y script legal sin pasar por el supervisor. Coherence Score: 1.000 (169/169 Tests PASSED).
- v10.15.4: hotfix-catalog-import-leak: Exposición explícita de CatalogService en app/services/__init__.py para restablecer la paridad de inicialización y contención quirúrgica de fuga de contexto en HabeasDataBypassInterrupt. Coherence Score: 1.000 (170/170 Tests PASSED).
- v10.15.5: hotfix-blind-quota-parity: Cuota inicial exacta del 10% del precio obtenido y copywriting del PASO 3 en la rama ciega de calculate_credit_score. Coherence Score: 1.000 (170/170 Tests PASSED).
- v10.15.6: hotfix-sticker-habeas: Normalización de stickers afirmativos a 'Sí' y captura de HabeasDataBypassInterrupt en media handler. Coherence Score: 1.000 (171/171 Tests PASSED).

