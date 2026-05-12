---
task: 023
name: Restore MemoryService API and Sincronía
description: Restaura los métodos críticos eliminados en v9.6.0 para eliminar los AttributeError en whatsapp.py y garantizar la persistencia de estados.
---

# Quick Task 023: Restore MemoryService API and Sincronía

## Objective
Restaurar la API pública de `MemoryService` (`generate_and_update_summary`, `transition_to_in_progress`, `set_human_help_status`, `update_whatsapp_status`, `update_last_interaction`) alineándolas con el estándar de Bloqueo Lineal (v9.6.0) y normalización estricta E.164.

## Tasks

<task type="auto">
  <name>Restaurar métodos en MemoryService</name>
  <files>app/services/memory_service.py</files>
  <action>
    Inyectar los métodos restaurados del historial de Git (commits 323c40c, d1a4572, 3c5319e) en app/services/memory_service.py.
    Asegurar que:
    1. Se use `PhoneNormalizer.normalize(phone_number)` para toda búsqueda de documentos.
    2. Los métodos sean `async` y utilicen `await self.get_ref()` o `await doc_ref.get()`.
    3. Se implemente lógica de Latch en `transition_to_in_progress`.
    4. `generate_and_update_summary` use el `ai_brain` pasado por parámetro para la extracción.
  </action>
  <verify>python3 -c "from app.services.memory_service import MemoryService; from unittest.mock import MagicMock; ms = MemoryService(MagicMock()); print('✅ generate_and_update_summary' if hasattr(ms, 'generate_and_update_summary') else '❌'); print('✅ transition_to_in_progress' if hasattr(ms, 'transition_to_in_progress') else '❌')"</verify>
  <done>Los métodos existen y el código no tiene errores de sintaxis.</done>
</task>

<task type="auto">
  <name>Verificación de Integridad con el Router</name>
  <files>app/routers/whatsapp.py</files>
  <action>Realizar una verificación estática (grep/ast) para asegurar que las llamadas en whatsapp.py coinciden con las nuevas firmas.</action>
  <verify>grep -E "generate_and_update_summary|transition_to_in_progress|set_human_help_status" app/routers/whatsapp.py</verify>
  <done>Las llamadas están presentes y apuntan a los métodos restaurados.</done>
</task>

---
*Created: 2026-05-11*
