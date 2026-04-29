# ROADMAP — BOT-STRUC-765-EVOLUTION

## Milestone 1: Inmutabilidad Estructural y Naming Lock
**Objetivo:** Eliminar hardcodeo, código muerto e inconsistencias de naming sin tocar lógica de negocio.

### Progress
| Fase | Nombre | Status | Planes | Fecha |
|------|--------|--------|--------|-------|
| 1 | Naming Lock + Hardcode Elimination | Planned | — | — |
| 2 | SRP: StorageService + Zero-Silent-Failures | Planned | — | — |
| 3 | Verificación y Test Suite | Planned | — | — |

---

### Phase 1: Naming Lock + Hardcode Elimination
**Goal:** Asegurar que el `EXTRACTION_SCHEMA` sea inmutable y global, eliminar código muerto del import `survey_service`, corregir el magic number de `tasa_mensual` en `finance.py`, y resolver la Regresión de Nomenclatura `habeasData` en `memory_service`.

**Requirements:** [R1, R2, R3, R4]

**Archivos afectados:**
- `app/services/ai_brain.py` — Elevar `EXTRACTION_SCHEMA` a constante de módulo
- `app/routers/whatsapp.py` — Eliminar import muerto `survey_service`
- `app/services/finance.py` — Eliminar `tasa_mensual = 2.22` hardcoded (línea 342)
- `app/services/memory_service.py` — Eliminar alias `habeasData` (línea 123)

**Entregables:**
- [ ] `EXTRACTION_SCHEMA` como `dict` constante de módulo antes de `class CerebroIA`
- [ ] Import `survey_service` eliminado de `whatsapp.py` sin romper funcionalidad
- [ ] `finance.py:342` — eliminar `tasa_mensual = 2.22` reemplazando por carga directa de ConfigService
- [ ] `memory_service.py:123` — llave única `habeas_data`, alias eliminado

**Guardrails de Valla de Chesterton:**
- `survey_service` fue removido de la lógica el 2026-03-12 (documentado en código). El import es código muerto seguro de eliminar.
- `tasa_mensual = 2.22` en `finance.py` ya tiene un bloque `if self._config_service:` que lo sobreescribe — eliminar el fallback hardcoded obliga a pasar siempre por ConfigService.

---

### Phase 2: SRP — StorageService + Zero-Silent-Failures
**Goal:** Mover `_download_media()` de `whatsapp.py` a `StorageService` como método público `download_media()`. Reemplazar los bloques `except Exception as e` genéricos en las 5 rutas HTTP críticas por captura explícita de `httpx.HTTPStatusError` con log del body nativo del proveedor.

**Requirements:** [R5, R6]

**Archivos afectados:**
- `app/services/storage_service.py` — Añadir método `download_media(media_id: str) -> Optional[bytes]`
- `app/routers/whatsapp.py` — Eliminar `_download_media()` local, importar desde `storage_service`, actualizar 2 call sites (líneas 333 y 683)
- `app/routers/whatsapp.py` — Reemplazar `except Exception as e` genéricos en rutas HTTP

**Rutas HTTP críticas para Zero-Silent-Failures (verificadas físicamente):**
| Línea | Función | Tipo Error |
|-------|---------|-----------|
| 154 | `verify_webhook` | HTTP 400 de Meta |
| 210 | `receive_webhook` | HTTP 500 de Meta |
| 840 | `_handle_message` | httpx genérico |
| 960 | `send_whatsapp_message` | HTTP 400/500 de Meta |
| 1005 | `_download_media` (→ StorageService) | httpx genérico |

**Entregables:**
- [ ] `StorageService.download_media(media_id)` con `httpx.HTTPStatusError` explícito + log `r.text`
- [ ] `_download_media` local eliminado de `whatsapp.py`
- [ ] Mínimo 5 bloques `except Exception` → `except httpx.HTTPStatusError as e: logger.error(e.response.text)`
- [ ] Todos los call sites actualizados (`storage_service.download_media(media_id)`)

---

### Phase 3: Verificación y Test Suite
**Goal:** Ejecutar la suite de regresión de `habeas_data` y verificar que los cambios no rompieron ningún contrato.

**Requirements:** [R7]

**Entregables:**
- [ ] `tests/test_habeas_data_regression.py` — crear si no existe, ejecutar, pasar al 100%
- [ ] Verificación manual de importaciones (`python3 -c "from app.services.ai_brain import CerebroIA"`)
- [ ] Commit de backup antes de cada fase (Checkpoint de Seguridad)
- [ ] Git push a `beta` con mensaje convencional

---

## Contratos JSON Voorhees (Fase de Diseño — Inmutables)

### Contrato 1: EXTRACTION_SCHEMA (ai_brain.py)
```json
{
  "constant_name": "EXTRACTION_SCHEMA",
  "location": "app/services/ai_brain.py",
  "placement": "Antes de class CerebroIA (nivel de módulo)",
  "type": "dict",
  "keys_immutable": [
    "summary", "extracted.nombre", "extracted.ciudad",
    "extracted.moto_interes", "extracted.moto_ofrecida",
    "extracted.moto_aceptada", "extracted.habeas_data",
    "extracted.forma_pago", "extracted.ocupacion",
    "extracted.datacredito", "extracted.vivienda",
    "extracted.servicios_publicos", "extracted.moto_confirmada"
  ],
  "naming_lock": "habeas_data"
}
```

### Contrato 2: StorageService.download_media (storage_service.py)
```json
{
  "method": "download_media",
  "class": "StorageService",
  "file": "app/services/storage_service.py",
  "signature": "async def download_media(self, media_id: str) -> Optional[bytes]",
  "error_handling": "httpx.HTTPStatusError explicit + logger.error(e.response.text)",
  "meta_api_version": "v25.0",
  "returns_on_failure": null
}
```

### Contrato 3: Naming Lock memory_service.py:123
```json
{
  "field": "habeas_data",
  "before": "data.get('habeas_data') or data.get('habeasData') or data.get('habeas_data_accepted', False)",
  "after": "data.get('habeas_data') or data.get('habeas_data_accepted', False)",
  "rationale": "habeasData es un alias camelCase no documentado. Naming Lock enforce snake_case."
}
```

---
*Última actualización: 2026-04-28*
