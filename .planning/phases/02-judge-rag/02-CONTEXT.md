# Phase 2: Tríada RAG y IA-as-a-Judge - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

## Phase Boundary
Implementación de la Tarea 2.3: Sincronización de Personalidad y Salida Elegante (Fallback). Integración de la Matriz de 9 Criterios en el prompt de Juan Pablo y configuración de fallback de supervisor con trazabilidad en Langfuse.

## Implementation Decisions

### Sincronización de Prompts
- **DECIDED:** Incluir los 9 Criterios DETALLADAMENTE en el `system_instruction` de `prompts.py`. No resúmenes ejecutivos.
- **DECIDED:** Mandatos innegociables para protocolos Brilla y Ciudad.

### Lógica de Reintentos
- **DECIDED:** Mantener el límite de 2 reintentos (3 intentos en total).

### Observabilidad (Langfuse)
- **DECIDED:** Tag obligatorio `JUDGE_CRITICAL_FALLBACK`.
- **DECIDED:** Registrar el motivo del último rechazo (C1-C9) como metadato en el trace de Langfuse.

### Tono del Fallback
- **DECIDED:** El mensaje del "Supervisor" debe guardarse en el historial de chat de Firestore como un mensaje del `model`.

## Specific Ideas
- "Disculpa, no estoy seguro de la respuesta, permíteme le pregunto a mi supervisor y te comento." (Mensaje de fallback).
- "Cacería de los 3 errores de 'Catalog Scoring'" para alcanzar el Score 1.000.

## Deferred Ideas
- N/A

---
*Phase: 02-judge-rag*
*Context gathered: 2026-05-11*
