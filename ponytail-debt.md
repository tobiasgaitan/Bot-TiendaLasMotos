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
