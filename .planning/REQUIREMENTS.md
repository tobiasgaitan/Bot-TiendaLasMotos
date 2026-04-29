# Requirements — BOT-STRUC-765-EVOLUTION

## Overview
Refactorización sistémica quirúrgica del backend del Bot TiendaLasMotos para eliminar
acoplamiento, hardcodeo financiero y bloqueos de observabilidad. Alcance: 5 archivos
principales con cambios no destructivos (Valla de Chesterton respetada).

## V1 — Must Have
Estas son las condiciones mínimas. El sistema regresa sin ellas.

| ID | Requirement | Fase | Status |
|----|------------|------|--------|
| R1 | `EXTRACTION_SCHEMA` como constante de módulo `EXTRACTION_SCHEMA: dict` en `ai_brain.py` (antes de la clase `CerebroIA`) | 1 | Planned |
| R2 | Eliminar `from app.services.survey_service import survey_service` de `whatsapp.py` (import muerto, código removido 2026-03-12) | 1 | Planned |
| R3 | `tasa_mensual = 2.22` hardcoded en `finance.py:342` reemplazado por llamada a `config_service.get_financial_config().get("tasa_nmv_fintech", 2.22)` | 1 | Planned |
| R4 | `memory_service.py:123` — eliminar alias `or data.get("habeasData")` → solo `data.get("habeas_data", False)` | 1 | Planned |
| R5 | `_download_media()` en `whatsapp.py:990` migrado a `StorageService.download_media(media_id)` con captura de `httpx.HTTPStatusError` | 2 | Planned |
| R6 | Reemplazar `except Exception as e` genéricos en funciones HTTP de `whatsapp.py` (≥5 rutas críticas) con captura explícita + `logger.error(response.text)` | 2 | Planned |
| R7 | Suite `tests/test_habeas_data_regression.py` pasa al 100% tras los cambios | 3 | Planned |

## V2 — Nice to Have
Mejoras para después de la estabilización.

| ID | Requirement | Priority | Status |
|----|------------|----------|--------|
| R10 | Mover constantes de telemetría (`LATENCY_BASE`, `JITTER_RANGE`) a `ConfigService` | Medium | Backlog |
| R11 | Añadir trazado distribuido con `request_id` en headers de Meta Graph API | High | Backlog |
| R12 | Generar `tests/test_storage_service.py` para validar `download_media()` aislado | Medium | Backlog |

## Out of Scope
- `juan_pablo_personality` — Inmutable por mandato contractual del usuario.
- Reescritura de lógica de negocio del AI Brain — Solo refactorización estructural.
- Cambio de modelo Gemini — Fuera del alcance del ticket.
- Frontend (Next.js CRM) — No aplica.

---
*Última actualización: 2026-04-28*
