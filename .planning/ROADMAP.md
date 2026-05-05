# Roadmap

## Milestone 1: Desacoplamiento de CerebroIA

### Progress

| Phase | Name | Status | Plans | Date |
|-------|------|--------|-------|------|
| 1 | Handoff y Memoria | Planned | 2 | 2026-05-05 |
| 2 | Agente de Triaje | Planned | 3 | 2026-05-05 |

### Phases

#### Phase 1: Handoff y Memoria
**Goal:** Establecer la infraestructura de persistencia atómica y el ruteo del orquestador `whatsapp.py`.
**Requirements:** R1, R2
- [ ] Modificar `memory_service.py` para soportar `current_agent`.
- [ ] Refactorizar `whatsapp.py` para leer `current_agent` e inyectar el servicio correspondiente.

#### Phase 2: Agente de Triaje
**Goal:** Construir el `TriageAgent` con validación de FASE 4 y asegurar el Gate Legal.
**Requirements:** R3, R4, R5, R6
- [ ] Crear `triage_agent.py` con observabilidad HTTP.
- [ ] Implementar extracción de Nombre/Ciudad con JSON Voorhees.
- [ ] Implementar Gate de Habeas Data antes de cambiar `current_agent` a `finance`.

---
*Last updated: 2026-05-05*
