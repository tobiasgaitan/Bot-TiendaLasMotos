# BOT-ARQ-801-TRIAJE — Desacoplamiento Monolito CerebroIA

## Vision
Implementar un Agente de Triaje (`triage_agent.py`) para gestionar la captura de intención (Fase 1) y el Gate Legal de Habeas Data (Fase 3). Este agente actuará como el primer punto de contacto, validando Nombre, Ciudad y consentimiento legal antes de delegar la sesión al Agente Especialista Financiero mediante un estado persistido en Firestore.

## Core Value
El desacoplamiento reduce la carga cognitiva de `CerebroIA` y garantiza que la lógica financiera solo se active cuando los requisitos legales y de perfilamiento básico (Habeas Data, Nombre, Ciudad) estén satisfechos. Se implementa un Gate Legal absoluto con persistencia atómica.

## Target Users
- **Usuarios de WhatsApp:** Reciben una atención fluida y transparente sobre el tratamiento de sus datos.
- **Equipo de Ventas/Finanzas:** Reciben prospectos ya validados legalmente y con datos básicos completos.
- **Desarrolladores:** Arquitectura modular más fácil de mantener y auditar.

## Technical Context

### Arquitectura de Delegación (State-Based Handoff)
- **Persistencia:** Campo `current_agent` en el documento de sesión de Firestore (`triage` | `finance`).
- **Ruteo:** `whatsapp.py` lee `current_agent` vía `memory_service` y delega el payload.
- **Gate Legal:** Bloqueo absoluto. No hay transición a `finance` sin `habeas_data=True`, `nombre` y `ciudad`.

### Saneamiento (Protocolo JSON Voorhees)
- **Truncamiento:** Nombre y Ciudad truncados a 50 caracteres.
- **Normalización:** UTF-8 y eliminación de caracteres de control.
- **Inmutabilidad:** `EXTRACTION_SCHEMA` en `ai_brain.py` permanece bloqueado.

## Requirements

### V1 — Must Have
- [ ] **R1:** Crear `app/services/triage_agent.py` como clase independiente (Singleton pattern).
- [ ] **R2:** Extender `MemoryService` para soportar el campo `current_agent` y la lógica de validación de requisitos de handoff.
- [ ] **R3:** Refactorizar `whatsapp.py` para implementar el ruteo basado en `current_agent`.
- [ ] **R4:** Implementar el "Gate Legal" en el Agente de Triaje (Captura de consentimiento afirmativo).
- [ ] **R5:** Garantizar observabilidad HTTP completa (Zero-Silent-Failures) en las llamadas del Agente de Triaje.

### Out of Scope
- Modificar el `EXTRACTION_SCHEMA` de `ai_brain.py`.
- Alterar la lógica interna de `MotorFinanciero`.
- Cambios en la UI del Admin Simulator.

## Key Decisions

| Decision | Source | Rationale | Outcome |
|----------|--------|-----------|---------|
| Estado en Firestore | User | Evitar redirecciones en memoria temporal, garantizar resiliencia. | Decidido |
| TriageAgent independiente | User | Aislamiento de "context window" de la lógica de crédito. | Decidido |
| Truncamiento PII | User | Cumplimiento estricto de FASE 4 (Saneamiento). | Decidido |
| Bloqueo Legal Absoluto | User | Seguridad jurídica (Habeas Data) antes de perfilamiento. | Decidido |

---
*Last updated: 2026-05-05 after initialization — Ticket BOT-ARQ-801-TRIAJE*
