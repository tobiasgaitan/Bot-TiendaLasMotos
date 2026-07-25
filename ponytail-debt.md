# Ponytail Debt Register

Registro de deuda técnica detectada durante auditorías. Cada entrada referencia
el ticket que la originó y su estado.

---

## BOT-AUDIT-ETAPA5-ZSF-001 — Registrado 2026-07-25

Bare `except:` fuera de scope del ticket (el ticket cubrió únicamente los 3
helpers de parsing en `app/routers/whatsapp.py`).

### Código de tests (prioridad baja)

| # | Ubicación | Patrón actual | Estado |
|---|-----------|---------------|--------|
| 1 | `tests/test_ai_adapter.py:18` | `except: pass` | PENDIENTE |
| 2 | `tests/test_pcc_ficha_tecnica.py:1218` | `except:` (bloque) | PENDIENTE |

### Referencia: tickets separados emitidos por el Planner (servicios)

| Ticket | Ubicación | Patrón actual | Severidad propuesta |
|--------|-----------|---------------|---------------------|
| ZSF-002 | `app/services/financial_service.py:510` | `except: moto_cc = 0.0` | HIGH (parsing financiero) |
| ZSF-003 | `app/services/survey_service.py:316` | `except: pass` | MEDIUM-HIGH (borrado Firestore silencioso) |
| ZSF-004 | `app/services/vision_service.py:349` | `except: return {}` | MEDIUM (JSON parse LLM) |
| ZSF-005 | `app/services/audio_service.py:153` | `except: pass` | LOW (cleanup temp, benigno) |

**Nota de auditoría:** `app/services/ai_brain.py` fue verificado y NO contiene
bare `except:` — la hipótesis de extensión del patrón a ese módulo quedó descartada.

---

## BOT-BUILD-FIX-E-CREDIORBE-ERADICATION-001 — Registrado 2026-07-25

Residuos de nomenclatura 'Crediorbe' detectados durante la erradicación FIX-E y
dejados fuera de scope por decisión explícita del owner.

### Código muerto no cableado (purga NO autorizada en FIX-E — ticket aparte)

| # | Ubicación | Hallazgo | Estado |
|---|-----------|----------|--------|
| 1 | `app/services/survey_service.py:261` | Texto user-facing `"CrediOrbe"` en rama REDIRECT. El servicio no tiene callers en `app/` y su contrato con `evaluate_profile` está roto (espera `action_type`/`payload` inexistentes → KeyError → HANDOFF). Candidato a purga de módulo completo. | PENDIENTE |

### Fixtures cosméticos sin impacto funcional (nomenclatura en tests/scripts legacy)

| # | Ubicación | Patrón | Estado |
|---|-----------|--------|--------|
| 2 | `tests/test_judge_service.py:197,231,256` | Strings de ejemplo "con Crediorbe" | PENDIENTE |
| 3 | `tests/test_identity_legal_gate.py:106` | String de simulación | PENDIENTE |
| 4 | `tests/test_read_asymmetry.py:138` | Payload fixture | PENDIENTE |
| 5 | `tests/test_agentic_loop_async.py:192-199,292-297,776` | Mocks entity/link Crediorbe (aserciones entidad-agnósticas, verde post-FIX-E) | PENDIENTE |
| 6 | `tests/test_financial_fallback.py:24` | `ENTIDAD = "Crediorbe"` (tests de fallback entidad-agnósticos) | PENDIENTE |
| 7 | `tests/test_perf_45.py:65-66,110,145-146` | Mocks Crediorbe (verde post-FIX-E vía rama else) | PENDIENTE |
| 8 | `tests/test_pcc_ficha_tecnica.py:294-295` | Mock evaluate_profile entity Crediorbe (aserciones L271/L623 exigen AUSENCIA — alineadas con FIX-E) | PENDIENTE |
| 9 | `scripts/init_v6_config.py:182-197` | Config legacy "CrediOrbe" (script one-shot histórico) | PENDIENTE |
| 10 | `attic/tmp/*` | Scratch files con referencias | IGNORADO (attic) |

## Deuda de Entorno Local (No bloqueante para producción)
- **Archivo:** `app/core/security.py:57`
- **Error:** `ImportError: cannot import name 'secretmanager' from 'google.cloud'`
- **Tests afectados (6):** 
  - `test_brilla_gases_real_firestore_cuotas`
  - `test_agility_fusion_exact_parity`
  - `test_apache_160_brilla_golden_parity`
  - `test_cc_zero_does_not_assume_125_cc_regression`
  - `test_raider_125_brilla_post_fix_414444`
  - `test_raider_125_anti_regression_416086`
- **Causa:** Paquete `google-cloud-secret-manager` ausente en el venv local de Python del sistema.
- **Impacto:** Solo afecta ejecución local con `python3 -m pytest`. Bajo `npx agent-cli eval` (entorno oficial con venv completo) la suite pasa 527/527 verde.
- **Fix trivial:** `pip install google-cloud-secret-manager` en el entorno local.
