# Roadmap

## Milestone 1: Caché Semántica de Catálogo

### Progress

| Phase | Name | Status | Plans | Date |
|-------|------|--------|-------|------|
| 1 | Arquitectura Core (Pure Python Math) | Completed | — | — |
| 2 | Intercepción en CatalogService y Pruebas | Completed | — | — |
| 4.2 | Optimización de Costos y Seguridad | Completed | — | 2026-05-16 |
| 4.3 | Optimización de Prompts y Compresión de Contexto | Completed | — | 2026-05-16 |
| 4.4 | Alineación de Tool Calling y Robustez de Errores | Completed | — | 2026-05-17 |

### Phases

#### Phase 1: Arquitectura Core
**Goal:** Implementar `SemanticCacheService` capaz de usar algoritmos de similitud locales puros (N-gramas/Levenshtein) sobre un diccionario en RAM.
**Requirements:** R1, R3
- [x] Construir y testear similitud de cadenas sin dependencias externas.
- [x] Implementar hidratación síncrona en memoria.

#### Phase 2: Intercepción y Verificación PCC
**Goal:** Acoplar la caché en `CatalogService` de forma quirúrgica, manteniendo PCC y verificando con tests.
**Requirements:** R2, R4, R5
- [x] Intercepción en `search_items`.
- [x] Tests de variaciones tipográficas.
- [x] Validación con `npx agent-cli eval`.

#### Phase 4.2: Optimización de Costos y Seguridad
**Goal:** Validar resistencia algorítmica frente a inyecciones de prompts (Red Teaming), asegurando el bloqueo de la herramienta `calculate_credit_score` si `habeas_data_accepted` es False.
**Requirements:** Ticket BOT-SEC-42
- [x] Desarrollar suite de estrés adversarial en pytest.
- [x] Garantizar política de Zero-Silent-Failures registrando logs forenses ante fallas de seguridad.

#### Phase 4.3: Optimización de Prompts y Compresión de Contexto
**Goal:** Reducir el payload del catálogo inyectado en el prompt para optimizar la ventana de contexto y los costos operativos.
**Requirements:** Ticket BOT-PERF-43
- [x] Intervención quirúrgica en `catalog_service.py` limitando el campo `specs` a 10 palabras mediante `_summarize()`.
- [x] Aprobación de despliegue mediante `npx agent-cli eval`.

**Quality Control & Anti-Null Masking (v9.9.7):**
- [x] [BOT-PERF-45] Refactorizar la resolución de herramientas en `ai_brain.py` para consumir `search_items` y unificar la llave canónica `price`.
- [x] Inyectar suite de aserción en `pytest` que prohíba de forma estricta los retornos vacíos o fallbacks silenciosos en la entrega de cuotas.

#### Phase 4.4: Alineación de Tool Calling y Robustez de Errores
**Goal:** Contener la regresión crítica en `ai_brain.py` y blindar el flujo de tool-calling de catálogo con validación nula y Zero-Silent-Failures.
**Requirements:** Ticket BOT-PERF-46
- [x] [BOT-PERF-46] Alinear `search_catalog` con `search_items` de `CatalogService`.
- [x] Inicializar explícitamente variables del scope condicional para evitar `UnboundLocalError`.
- [x] Validar de forma estricta que no exista enmascaramiento nulo en llaves críticas y lanzar `ValueError`.
- [x] Forzar interrupción síncrona con re-raise en fallas del catálogo.
- [x] Suite de no-regresión en `pytest` y validación con `npx agent-cli eval` al 100%.

---
*Last updated: 2026-05-20*
- [x] BOT-BE-53: Paridad restaurada (price/precio) e integración de bonos de contado (Score 1.000).
- [x] BOT-BE-035: Purga de llaves legacy y alineación de firma de calculate_credit_score (Score 1.000).
- [x] BOT-AUDIT-103: Resolución de latencia crítica en WhatsApp webhook, refactorización asíncrona de generate_summary y shim de compatibilidad para Langfuse v4 (Score 1.000).
- [x] BOT-FIN-104: Conmutación a Brilla de Gases, captura de cédula e intercepción de Crediorbe (Score 1.000).
- [x] BOT-FIN-104 (Corrección): Adaptar búsqueda de catálogo a propiedades reales en español de Firestore (Score 1.000).
- [x] BOT-HOTFIX-39: Corrección de variable inexistente _lf por langfuse_context en telemetry de ai_brain.py (Score 1.000).

