# Requirements

## Overview
Requerimientos técnicos para la implementación de la Similitud Multimodal de Imagen.

## V1 — Must Have
These are table stakes. The product doesn't work without them.

| ID | Requirement | Phase | Status |
|----|-------------|-------|--------|
| R7 | Mapear la imagen de WhatsApp con el pool del catálogo físico (ID, nombre, imagen_url) inyectado dinámicamente en Gemini 2.5 Flash. | 1 | Done |
| R8 | Implementar `match_catalog_item_by_image` en `CatalogService` con precedencia ID -> URL exacta -> difflib/SequenceMatcher. | 1 | Done |
| R9 | Blindar la serialización del catálogo con validación de valores no nulos y traceback (Anti-Null Masking). | 1 | Done |
| R10| Guardar síncronamente `moto_interest` en la colección `prospectos` sin eludir el consentimiento legal de Habeas Data. | 1 | Done |
| R11| Integrar la capa adaptadora en la ruta multimedia del webhook en `whatsapp.py`. | 1 | Done |
| R12| Suite de pruebas automatizadas completa en `tests/test_multimodal_similitude.py`. | 1 | Done |

## V2 — Refactorización Estructural Etapa 1 [BOT-PLAN-REFACTOR-ETAPA1-197]
Requerimientos de la fase `03-refactor-etapa1` (God Nodes, idempotencia durable, desambiguación ConfigLoader). Aprobados por el Auditor en el Plan Definitivo Etapa 1.

| ID | Requirement | Phase | Status |
|----|-------------|-------|--------|
| RF-1 | Idempotencia durable del pipeline webhook: reclamo atómico create-only en `processed_webhooks` dentro del embudo `_handle_message_background`, con liberación del reclamo ante excepción (efecto exactly-once bajo reintentos de Cloud Tasks). [Resolución R-B] | 3 | Done [BOT-BUILD-REFACTOR-ETAPA1-WAVE2-200] |
| RF-2 | Gateway de Estado Transicional: costuras `_open_session_and_refresh` y `_mark_ponytail_deprioritized` unificando la secuencia CRM y las 4 escrituras físicas `ponytail_status=DEPRIORITIZED` (la enumeración "5" del plan original era doble conteo del sitio de audio), con cero cambio semántico. | 3 | Done [BOT-BUILD-REFACTOR-03-03] |
| RF-3 | Desambiguación de namespaces: renombrar la clase homónima de `app/services/config_loader.py` a `FinanceConfigLoader`; el identificador `ConfigLoader` queda reservado a la matriz de personalidad (`app/core/config_loader.py`). [Resolución R-C] | 3 | Done [BOT-BUILD-REFACTOR-03-04-03-05; certificación de grafo BOT-BUILD-REFACTOR-03-05-RESIDUAL] |
| RF-4 | Higiene asíncrona: `refresh_config` bajo `asyncio.to_thread`, tracking/flush en `audit_service`, cableado de `MemoryService.shutdown()` en lifespan, purga de global vestigial `motor_financiero` y deriva de versiones. | 3 | Done [BOT-BUILD-REFACTOR-03-04-03-05; hardening atómico residual BOT-BUILD-REFACTOR-03-05-RESIDUAL] |
| RF-5 | Fragmentación de `_handle_message_background_impl` en pipelines de medios, cognitivo y egreso con DI explícita; impl reducido a orquestador (<300 líneas) con firmas públicas inmutables. | 3 | Open |
| RF-6 | Red de caracterización Feathers del flujo Meta→Firestore (`tests/test_characterization_etapa1.py`, 5 pins CH-1…CH-5) como red de seguridad previa a toda intervención. | 3 | In Progress [BOT-BUILD-REFACTOR-ETAPA1-WAVE1-199] |

---
*Last updated: 2026-07-21 | RF-3/RF-4 cerrados [BOT-BUILD-REFACTOR-03-05-RESIDUAL]: invariante de atomicidad del refresh demostrado (7/7 `tests/test_refresh_atomicity.py`), 367/367 tests PASSED bajo `.venv` (Python 3.13), grafo regenerado con 0 aristas cruzadas core↔finance.*