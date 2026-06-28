# Current State - Bot-TiendaLasMotos
**Versión Actual:** v10.13.0
**Último Hito:** Cierre del ticket BOT-INFRA-ALERT-080 — Log Sink y Pub Sub Alerting para CATALOG_VALIDATION_FAIL
**Coherence Score:** 1.000 (167/167 Tests PASSED)

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

- v10.13.0: Implementar Log Sink y Pub Sub Alerting para CATALOG_VALIDATION_FAIL.
