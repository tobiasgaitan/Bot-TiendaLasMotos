---
task: 070
name: Hotfix Reset Recovery - Idempotencia Post-Borrado
description: Reparar el flujo post-reset del bot garantizando idempotencia, telemetría Langfuse, y cobertura QA con exists:False
---

# Quick Task 070: Hotfix Reset Recovery

## Objective
Reparar la interrupción del flujo conversacional posterior al comando /reset causada por el método fantasma `update_last_interaction` y la ausencia de blindaje para documentos completamente borrados (`exists: False`).

## Tasks

<task type="auto">
  <name>Implementar update_last_interaction con Langfuse y aislamiento E.164</name>
  <files>app/services/memory_service.py</files>
  <action>Agregar método update_last_interaction que reciba phone_number como string E.164 pre-sanitizado (sin PhoneNormalizer interno), use set(merge=True) para idempotencia, y registre traza Langfuse con @observe() o langfuse_context</action>
  <verify>python3 -c "from app.services.memory_service import MemoryService; assert hasattr(MemoryService, 'update_last_interaction')"</verify>
  <done>Método existe, no importa PhoneNormalizer internamente, registra traza Langfuse</done>
</task>

<task type="auto">
  <name>Extender blindaje zombi para caso is_fully_deleted</name>
  <files>app/routers/whatsapp.py</files>
  <action>Agregar rama is_fully_deleted en el blindaje de concurrencia (L595-604) que invoque create_prospect_if_missing y refresh de prospect_data ANTES de evaluar el historial</action>
  <verify>grep -n "is_fully_deleted" app/routers/whatsapp.py</verify>
  <done>La variable is_fully_deleted existe y activa la reconstrucción del documento</done>
</task>

<task type="auto">
  <name>Test post-reset con exists:False y aserciones rígidas</name>
  <files>tests/test_zombie_recovery_flow.py</files>
  <action>Agregar test_handle_message_background_post_reset_recovery que simule exists:False en la primera llamada, exists:True en subsecuentes, y valide con aserciones rígidas que prohíban retornos vacíos/None</action>
  <verify>python3 -m pytest tests/test_zombie_recovery_flow.py -v</verify>
  <done>Ambos tests pasan con Score 1.000</done>
</task>

---
*Created: 2026-06-26*
