---
task: 026
name: Hotfix Firestore Timeout
description: Timeout en escrituras asíncronas de Firestore durante ráfagas de webhooks de estado
---

# Quick Task 026: Hotfix Firestore Timeout

## Objective
Aislar y resolver los timeouts de escritura en Firestore limitando la concurrencia en la recepción de Meta Statuses mediante un semáforo asíncrono.

## Tasks

<task type="auto">
  <name>Implement Async Semaphore</name>
  <files>app/services/memory_service.py</files>
  <action>Instanciar self._status_semaphore = asyncio.Semaphore(5) en el constructor e interceptar el cuerpo de update_whatsapp_status con un bloque async with self._status_semaphore:.</action>
  <verify>pytest</verify>
  <done>Pruebas pasan sin regresiones en test_memory_merge, test_reset_flow o test_read_asymmetry.</done>
</task>

---
*Created: 2026-05-15*
