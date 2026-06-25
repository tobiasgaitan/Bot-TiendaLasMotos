---
task: 066
name: Purge Legacy Methods and Normalize Timestamps
description: Se detectó duplicidad de lógica de mezcla (merge_data y _merge_extracted_data), redundancia de marcas de tiempo (updated_at, last_updated) y alias legacy expuestos en MemoryService.
---

# Quick Task 066: Purge Legacy Methods and Normalize Timestamps

## Objective
Remover métodos legacy (`merge_data` y `create_prospect`) y normalizar marcas de tiempo para usar únicamente `fecha` asegurando Score de Coherencia 1.000.

## Tasks

<task type="auto">
  <name>Refactor MemoryService and Unit Test</name>
  <files>app/services/memory_service.py, tests/test_memory_merge.py</files>
  <action>Eliminar duplicidad de mezcla, reemplazar timestamps por fecha, e incluir un unit test de llaves en español.</action>
  <verify>pytest tests/test_memory_merge.py && npx agent-cli eval</verify>
  <done>Verificaciones pasan con 100% asserts y score de 1.000</done>
</task>

---
*Created: 2026-06-24*
