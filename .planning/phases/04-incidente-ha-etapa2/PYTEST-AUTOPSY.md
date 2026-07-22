# PYTEST AUTOPSY — Incidente H-A · Milestone 3 Etapa 2 (BOT-BUILD-INCIDENT-HA-201)

**Fecha:** 2026-07-22 · **Commit certificado:** `fc24e56` (beta) · **Entorno:** `.venv` Python 3.13 (pin documentado) · **Runner:** `./.venv/bin/pytest -v --tb=short --durations=20`
**Salida cruda completa:** `evidence/pytest-full-output.txt`

---

## 1. Conteo explícito

| Métrica | Valor |
|---------|-------|
| **Tests PASSED** | **378/378 (0 failed)** |
| Subtests PASSED | 2 |
| Skipped | 2 (justificados §5) |
| **RuntimeWarnings** | **0** (`grep -c RuntimeWarning` sobre la salida → 0) |
| Duración total | 73.99s |
| Coherence Score (`npx agent-cli eval`) | **1.000 ≥ 0.9 — DEPLOY AUTHORIZED** (`evidence/agent-cli-eval.txt`) |

## 2. Confirmación del STARTUP-GUARD sin bypass (HA-2)

- Guard **estricto e incondicional** en `webhook_handler` y `task_processor` (`app/routers/whatsapp.py`): sin `is_test_mode`, sin sniffing de Mocks, sin `should_bypass`.
- Escaneo del seam: `grep -rnE "is_test_mode|TEST_MODE" app/ tests/conftest.py .github/` → **0 hits**.
- Pins del guard en la suite (ambos PASSED):
  - `tests/test_startup_lock.py::test_webhook_handler_rejects_with_503_if_catalog_not_fully_loaded PASSED`
  - `tests/test_startup_lock.py::test_task_processor_rejects_with_503_if_catalog_not_fully_loaded PASSED`
- El guard se ejerce con el umbral de producción (60) vía fixture `real_lifespan_client` (lifespan real + catálogo dinámico): `test_api_bounds.py::test_webhook_signature_valid PASSED`, `test_health_check.py` ×2 PASSED, `test_robots.py` PASSED.
- Tests del guard migrados a mocking dinámico (04-02): `test_startup_lock` (11), `test_characterization_etapa1`, `test_router_concurrency`, `test_audio_regression`, `test_config_startup` — todos PASSED.
- Validadores nuevos (04-04): `test_pcc_pro_regex_validators_dynamic_catalog`, `test_pcc_pro_regex_mutation_checks`, `test_pii_sanitize_fields_contract_with_regex_validators`, `test_pii_validators_mutation_checks` — todos PASSED.

## 3. Durations — 20 tests más lentos (salida real)

```
6.27s call     tests/test_pcc_ficha_tecnica.py::test_brilla_gases_real_firestore_cuotas
6.22s call     tests/test_pcc_ficha_tecnica.py::test_agility_fusion_exact_parity
4.63s call     tests/test_regression_203.py::test_boxer_competitor_tool_loop_returns_alternative
4.06s call     tests/test_regression_203.py::test_raider_125_helper_path_414444
3.68s call     tests/test_pcc_ficha_tecnica.py::test_raider_125_anti_regression_416086
3.60s call     tests/test_pcc_ficha_tecnica.py::test_cc_zero_does_not_assume_125_cc_regression
3.58s call     tests/test_pcc_ficha_tecnica.py::test_raider_125_brilla_post_fix_414444
3.33s call     tests/test_pcc_ficha_tecnica.py::test_apache_160_brilla_golden_parity
2.72s call     tests/test_startup_lock.py::test_startup_lifespan_timeout_recovers_and_commits_catalog_ready
2.53s call     tests/test_startup_lock.py::test_health_returns_starting_immediately_when_catalog_empty_before_hydration
2.53s call     tests/test_startup_lock.py::test_deferred_init_port_available_before_hydration
2.06s setup    tests/test_api_bounds.py::test_webhook_signature_invalid
2.05s setup    tests/test_api_bounds.py::test_webhook_signature_missing
2.05s setup    tests/test_robots.py::test_robots_txt
2.05s setup    tests/test_health_check.py::test_health_check_with_uninitialized_state
2.05s setup    tests/test_health_check.py::test_health_check_with_initialized_state
2.02s setup    tests/test_api_bounds.py::test_webhook_signature_valid
2.00s call     tests/test_startup_lock.py::test_startup_lifespan_successful_initialization_sets_catalog_ready_true
2.00s call     tests/test_startup_lock.py::test_startup_lifespan_catalog_size_check_fails_in_production
2.00s call     tests/test_startup_lock.py::test_startup_lifespan_init_failure_keeps_catalog_ready_false
```

**Nota de duraciones:** los `setup` de ~2.05s son el fixture `real_lifespan_client` atravesando el `asyncio.sleep(2)` real del deferred init (BOT-190) — coste deliberado de fidelidad al camino de producción, documentado en 04-03b.

## 4. Warnings

Sección de warnings de la salida: sin RuntimeWarning transversal (0 ocurrencias en el log completo). La suite conserva el pin determinista de `test_zombie_recovery_flow.py` (BOT-BUILD-MULTIMODAL-CIERRE-196).

## 5. Skipped (2) — justificación línea a línea

| Test | Razón |
|------|-------|
| `scripts/test_intent_evaluator.py::test_intent_evaluator` | SKIP preexistente (marcador `Dep...` del arnés de scripts — ajeno al Incidente H-A) |
| `scripts/test_memory_survey_state.py::test_survey_state_integration` | SKIP preexistente del arnés de scripts (ídem) |

Ambos skips existían en la baseline 374 pre-incidente (mismo conteo 2) — cero skips nuevos introducidos.

## 6. Evidencia forense complementaria

- `evidence/final-forensic-scan.log` — re-verificación remota: 0 tokens EAA reales, 0 material PEM real, 0 seam, 6 ramas en SHAs finales.
- `evidence/agent-cli-eval.txt` — salida real del eval con Coherence 1.000.

---
*Autopsia generada: 2026-07-22 | Incidente H-A CLOSED — 378/378 PASSED, 0 failed, 0 RuntimeWarnings*
