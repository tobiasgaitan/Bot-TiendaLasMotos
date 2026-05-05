# Requirements

## Overview
Requisitos funcionales y arquitectónicos para la implementación del Agente de Triaje y el desacoplamiento del CerebroIA, siguiendo el ticket BOT-ARQ-801-TRIAJE.

## V1 — Must Have
These are table stakes. The product doesn't work without them.

| ID | Requirement | Phase | Status |
|----|-------------|-------|--------|
| R1 | `current_agent` persistido en Firestore y `MemoryService` (triage\|finance). | 1 | Planned |
| R2 | `whatsapp.py` rutea payload en base a `current_agent`. | 1 | Planned |
| R3 | `app/services/triage_agent.py` inyectado independientemente. | 2 | Planned |
| R4 | Agente de Triaje extrae Nombre y Ciudad (Truncado a 50 chars, UTF-8). | 2 | Planned |
| R5 | Gate Legal: Transición a `finance` bloqueada si `habeas_data` es falso. | 2 | Planned |
| R6 | Observabilidad HTTP estricta (Zero-Silent-Failures) en Triaje. | 2 | Planned |

## Out of Scope
- Reestructuración de la lógica interna del `MotorFinanciero`.
- Modificación del `EXTRACTION_SCHEMA` en `ai_brain.py`.

---
*Last updated: 2026-05-05*
