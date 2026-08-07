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
| 1 | `app/services/survey_service.py` (purged) | Texto user-facing `"CrediOrbe"` en rama REDIRECT. Módulo muerto purgado en BOT-BUILD-LEGACY-JUDGE-012; denominador M4-003; test tumba `test_m4_003_survey_service_purgado`; guard FIX-E extendido a `judge_service.py`. | EJECUTADO (M4-003) |

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

---

## BOT-PLAN-FIX-HARDCODE-ENTITY-LEAK-007 — Registrado 2026-07-25

String user-facing con entidades hardcoded detectado durante el inventario
forense del ticket. Es código muerto (0 callers en `app/`), por lo que quedó
FUERA del hotfix por decisión explícita del Auditor (riesgo runtime cero).
Candidato a purga de módulo completo junto con `survey_service.py`.

### Código muerto no cableado (purga NO autorizada en este ticket)

| # | Ubicación | Hallazgo | Estado |
|---|-----------|----------|--------|
| 1 | `app/services/financial_service.py:437-451` (`_generate_generic_response`) | String user-facing "🏍️ Simulación de Crédito" con `Banco de Bogotá` y `Crédito Brilla` hardcoded (viola neutralidad PASO 3/4). Alcanzable solo vía `simulate_credit` (L380) / alias `simular_credito` (L546), ambos SIN callers en `app/`. | PENDIENTE |

---

## BOT-BUILD-REVERT-VISUAL-LOCK-009 — Registrado 2026-07-26

REVERSIÓN de FIX-008 (commit `0e53ce6`): el envío de imágenes de catálogo como
Markdown en texto plano mostraba al usuario el string literal `![Nombre](URL)`
— WhatsApp NO renderiza Markdown como imagen embebida. Restaurada la doctrina
Media API (`send_image_message`, payload `type='image'` + `link` + `caption`),
blindada por `tests/test_media_api_catalog_images_009.py`.

### Causa raíz del error 131053 (investigación, paso 6 del ticket)

Evidencia Cloud Logging (2026-07-25/26): el 131053 llega vía **STATUS webhook**
(entrega asíncrona) con `Downloading media from weblink failed with http code
404`. Los 2 incidentes capturados fueron precedidos por Strategy A con URLs
`auteco.com.co/wp-content/uploads/*.webp` — URLs **ausentes** de los 59 docs
de Firestore (4 campos URL verificados) y del código → **alucinación del LLM**
(fabrica URLs del CDN de auteco en lugar de copiar el Image URL canónico
Firebase del tool output). Las entregas con URL Firebase canónica no muestran
131053 adyacente en la ventana analizada. El Auditor determinó además un fallo
transitorio de Firebase Storage/CORS (7:34 a.m.) como factor del incidente
original. **Conclusión: el formato de envío (Media API) siempre fue correcto;
el vector residual son las URLs no canónicas.**

### Deuda viva (CRÍTICA post-reversión): URL-lock anti-alucinación

| # | Ubicación | Diseño propuesto | Estado |
|---|-----------|------------------|--------|
| 1 | `app/routers/whatsapp.py` (`_process_and_send_egress_message`) + `app/services/ai_brain.py` | Con Media API restaurada, una URL alucinada vuelve a poder matar la entrega COMPLETA (imagen+caption) vía 131053 silencioso. Diseñar URL-lock: validar el Markdown URL contra los `image_url` canónicos (`_items_by_image_url_norm` o búsqueda por nombre en alt-text) y sustituir por el canónico ANTES de enviar. Complemento: el guardarraíl `hallucinated_model` de ai_brain.py valida nombres de moto pero NO URLs. | PENDIENTE — ticket separado |
