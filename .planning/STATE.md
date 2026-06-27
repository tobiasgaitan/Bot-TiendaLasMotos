# Current State - Bot-TiendaLasMotos
**Versión Actual:** v10.12.9
**Último Hito:** Cierre del ticket BOT-INFRA-CI-078 — Ajuste de umbrales k6 http_req_duration para runners compartidos de GitHub Actions (p95<30s, p99<40s)
**Coherence Score:** 1.000 (167/167 Tests PASSED)

## Estado de la Ruta Crítica
- Implementación del método `update_last_interaction` en `MemoryService` con aislamiento E.164, `set(merge=True)` idempotente y vinculación de telemetría Langfuse.
- Extensión del blindaje zombi del router (`is_fully_deleted`) para cubrir el escenario post-reset con documentos completamente borrados (`exists: False`).
- Inyección de test de integración `test_handle_message_background_post_reset_recovery` con aserciones rígidas anti-null que prohíben retornos vacíos, None o estructuras truncadas.
- Mitigación total de la interrupción del flujo conversacional posterior al comando `/reset`.
- Decoración del enrutador asíncrono con `@observe` e inyección de contexto de observabilidad (`user_id`, `session_id`, `metadata`) con un adaptador seguro No-Op.
- Compilación y AST validados con paridad absoluta.

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

- v10.13.0: Inicialización del sistema de alertas automáticas nativas GCP para CATALOG_VALIDATION_FAIL.
