# BOT-STRUC-765-EVOLUTION — Refactorización Sistémica v2.0

## Vision
Eliminar los God Nodes detectados en `ai_brain.py` (1,215 LOC) y `whatsapp.py` (1,018 LOC)
mediante fragmentación quirúrgica de responsabilidades, blindaje completo de observabilidad
Zero-Silent-Failures, y resolución del hardcodeo financiero residual en `finance.py`.
El ticket exige que `SurveyService` sea eliminado del árbol de importaciones activas (ya fue
removido de la lógica pero su importación singleton persiste), que `_download_media()` sea
movido a `StorageService`, y que el `EXTRACTION_SCHEMA` se eleve a constante global inmutable
con Naming Lock garantizado (`habeas_data`).

## Core Value
El sistema debe poder procesar mensajes de WhatsApp → AI Brain → Firestore → Meta sin ningún
bloque `except Exception as e` genérico que silencie el payload nativo del proveedor (38
ocurrencias auditadas físicamente). Cada fallo de red debe exponer el body HTTP completo.

## Target Users
- **Auditor (Tobias):** Visibilidad total de fallos de integración Meta/GCP via logs estructurados.
- **AI Brain (Juan Pablo):** Configuración financiera siempre desde ConfigService (sin magic numbers).
- **StorageService:** Único responsable de descargas de medios binarios de Meta Graph API.

## Technical Context

### Hallazgos del PAA (Verificados Físicamente)
| Archivo | LOC | Hallazgo Crítico |
|---------|-----|-----------------|
| `app/services/ai_brain.py` | 1,215 | `extraction_schema` definido como local dentro de función (no global inmutable). 18 `except Exception` genéricos. |
| `app/routers/whatsapp.py` | 1,018 | `_download_media()` vive aquí violando SRP. `survey_service` importado pero **no usado** (línea 29). 20 `except Exception` genéricos. |
| `app/services/finance.py` | 568 | Hardcoded `tasa_mensual = 2.22` en línea 342 como fallback antes de consultar `config_service`. Patrón correcto (ConfigService) ya existe. |
| `app/services/survey_service.py` | 369 | Módulo importado en `whatsapp.py` como singleton aunque la state machine fue removida el 2026-03-12 (comentario documentado). |
| `app/services/config_service.py` | 227 | `DEFAULT_FINANCIAL` dict ya contiene los valores correctos. Es el SSOT. |
| `app/services/storage_service.py` | 134 | Módulo existe y ya es singleton. Capacidad de extensión disponible. |
| `app/services/memory_service.py` | 741 | Doble fallback en línea 123: `habeas_data` or `habeasData` or `habeas_data_accepted`. Regresión de nomenclatura activa. |

### Decisions Tomadas
| Decisión | Fuente | Racional | Estado |
|----------|--------|----------|--------|
| `EXTRACTION_SCHEMA` como constante de módulo en `ai_brain.py` | Ticket | Naming Lock + reutilización | Aprobado |
| `_download_media()` → `StorageService.download_media()` | Ticket + SRP | Desacoplamiento | Aprobado |
| Eliminar import `survey_service` de `whatsapp.py` | Arqueología | Código muerto post 2026-03-12 | Aprobado |
| Reemplazar `except Exception` por `httpx.HTTPStatusError` en rutas HTTP | Ticket | Zero-Silent-Failures | Aprobado |
| `tasa_mensual` hardcode en `finance.py:342` → eliminar magic number | Ticket | SSOT ConfigService | Aprobado |

## Requirements

### V1 — Must Have
| ID | Requirement | Fase | Status |
|----|------------|------|--------|
| R1 | `EXTRACTION_SCHEMA` elevado a constante global de módulo en `ai_brain.py` | 1 | Planned |
| R2 | Eliminar import muerto `survey_service` de `whatsapp.py` | 1 | Planned |
| R3 | `_download_media()` migrado a `StorageService.download_media()` con HTTP explícito | 2 | Planned |
| R4 | Todos los `except Exception` en rutas HTTP → `httpx.HTTPStatusError` + log body | 2 | Planned |
| R5 | `tasa_mensual = 2.22` en `finance.py:342` eliminado — siempre vía ConfigService | 1 | Planned |
| R6 | `memory_service.py:123` unificar a solo `habeas_data` (eliminar alias `habeasData`) | 1 | Planned |
| R7 | Test de regresión `habeas_data` supera suite `tests/test_habeas_data_regression.py` | 3 | Planned |

### Out of Scope
- Reescritura total de `ai_brain.py` — Solo cambios quirúrgicos por bloques.
- Cambios en `juan_pablo_personality` — Inmutable por mandato de usuario.
- Cambios en rutas de Firestore — Contrato de persistencia no se altera.
- Migración a nueva base de datos.

---
*Inicializado: 2026-04-28 — Ticket BOT-STRUC-765-EVOLUTION*
