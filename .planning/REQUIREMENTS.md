# Requirements

## Overview
Requerimientos técnicos para la implementación de la Similitud Multimodal de Imagen.

## V1 — Must Have
These are table stakes. The product doesn't work without them.

| ID | Requirement | Phase | Status |
|----|-------------|-------|--------|
| R7 | Mapear la imagen de WhatsApp con el pool del catálogo físico (ID, nombre, imagen_url) inyectado dinámicamente en Gemini 2.5 Flash. | 1 | Planned |
| R8 | Implementar `match_catalog_item_by_image` en `CatalogService` con precedencia ID -> URL exacta -> difflib/SequenceMatcher. | 1 | Planned |
| R9 | Blindar la serialización del catálogo con validación de valores no nulos y traceback (Anti-Null Masking). | 1 | Planned |
| R10| Guardar síncronamente `moto_interest` en la colección `prospectos` sin eludir el consentimiento legal de Habeas Data. | 1 | Planned |
| R11| Integrar la capa adaptadora en la ruta multimedia del webhook en `whatsapp.py`. | 1 | Planned |
| R12| Suite de pruebas automatizadas completa en `tests/test_multimodal_similitude.py`. | 1 | Planned |

---
*Last updated: 2026-07-11*