# Project State — BOT-STRUC-765-EVOLUTION

## Current Position
**Phase:** 1 — Naming Lock + Hardcode Elimination
**Status:** Approved by Tobias. Ready for execution in a NEW CONVERSATION.
**Last activity:** 2026-04-28 — Roadmap approved with conditions (Beta branch deployment, strict async/await for storage, notify Frontend of schema changes).

## Audit Summary (PAA Completado)
Archivos verificados físicamente:
- `app/services/ai_brain.py` ✅ (1,215 LOC)
- `app/routers/whatsapp.py` ✅ (1,018 LOC)
- `app/services/finance.py` ✅ (568 LOC)
- `app/services/survey_service.py` ✅ (369 LOC)
- `app/services/config_service.py` ✅ (227 LOC)
- `app/services/storage_service.py` ✅ (134 LOC)
- `app/services/memory_service.py` ✅ (741 LOC)

## Key Decisions
| Decision | Fase | Fuente | Racional |
|----------|------|--------|----------|
| `EXTRACTION_SCHEMA` → constante de módulo | 1 | Ticket | Naming Lock + Inmutabilidad |
| Eliminar import muerto `survey_service` | 1 | Arqueología 2026-03-12 | Código muerto documentado |
| `tasa_mensual = 2.22` → ConfigService siempre | 1 | Ticket + SSOT | Eliminación magic number |
| `habeasData` alias eliminado | 1 | Ticket | Naming Lock snake_case |
| `_download_media` → `StorageService` | 2 | Ticket + SRP | Desacoplamiento |
| `except Exception` → `httpx.HTTPStatusError` | 2 | Ticket | Zero-Silent-Failures |

## Blockers/Concerns
- ⚠️ `tests/test_habeas_data_regression.py` puede no existir — se crea en Fase 3 si es necesario.
- ⚠️ Verificar que `StorageService` ya tiene el cliente `httpx` y token importado antes de Fase 2.

---
*Última actualización: 2026-04-28*
