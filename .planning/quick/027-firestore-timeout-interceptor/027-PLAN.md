---
task: 027
name: BOT-INFRA-33 — Firestore Timeout Interceptor
description: Inyectar control de timeout asíncrono en todas las operaciones de I/O de Firestore del MemoryService para prevenir el congelamiento del orquestador de webhooks ante degradación de red GCP, con despacho de mensaje de contingencia y propagación de excepción.
---

# Quick Task 027: BOT-INFRA-33 — Firestore Timeout Interceptor

## Objective
Blindar el MemoryService contra degradación de red GCP inyectando `asyncio.wait_for` en cada operación I/O de Firestore, despachando un mensaje de contingencia profesional al lead afectado y propagando la excepción hacia el enrutador para detener `ai_brain.py`.

## Análisis de Impacto (get_neighbors auditado)

| Módulo | Función Afectada | Riesgo |
|--------|-----------------|--------|
| `whatsapp.py` | `handle_statuses`, `handle_message` | ALTO — punto de entrada de webhooks |
| `admin.py` | `save_message` | MEDIO — llamada interna de admin |
| `main.py` | `shutdown` | BAJO — ya tiene wait_for |

**God Nodes verificados**: Los God Nodes del grafo (GET, handleSave, submitLead) pertenecen al frontend Next.js. El MemoryService Python no figura como God Node en el grafo estático — cambio es seguro quirúrgicamente.

## Tasks

<task type="auto">
  <name>T1: Inyectar DB_TIMEOUT en config.py</name>
  <files>app/core/config.py</files>
  <action>Agregar `self.db_timeout: int = int(os.getenv('DB_TIMEOUT', '5'))` en el constructor de Settings, después de la línea del puerto. Sin tocar _validate_config ni _log_config_status.</action>
  <verify>python3 -c "from app.core.config import settings; print('DB_TIMEOUT:', settings.db_timeout)"</verify>
  <done>settings.db_timeout devuelve 5 por defecto</done>
</task>

<task type="auto">
  <name>T2: Implementar _firestore_io() en MemoryService</name>
  <files>app/services/memory_service.py</files>
  <action>
    1. Importar whatsapp_service de forma lazy dentro del interceptor (evitar circular import).
    2. Agregar método estático async `_firestore_io(coro, timeout, phone, label)` que envuelve la corutina en asyncio.wait_for.
    3. En TimeoutError: logger.exception forense + await de mensaje de contingencia + re-raise.
    4. En google.api_core.exceptions (connectivity): mismo tratamiento.
    5. Envolver TODAS las llamadas de I/O de Firestore en los métodos públicos: save_message, get_chat_history, get_prospect_data, create_prospect_if_missing, create_prospect, clear_memory, delete_prospect_completely, update_prospect_summary, generate_and_update_summary, transition_to_in_progress, set_human_help_status, update_whatsapp_status, update_last_interaction.
  </action>
  <verify>python3 -m pytest tests/test_race_condition_fix.py tests/test_memory_merge.py tests/test_reset_flow.py tests/test_read_asymmetry.py tests/test_memory_stream_coverage.py -v 2>&1 | tail -20</verify>
  <done>Todos los tests existentes PASSED + timeout se dispara en mock > 5s</done>
</task>

<task type="auto">
  <name>T3: Suite de regresión BOT-INFRA-33</name>
  <files>tests/test_infra_33_timeout.py</files>
  <action>Crear suite pytest que inyecta un mock de latencia artificial (> 5s via asyncio.sleep) en Firestore y certifica: 1. TimeoutError dispara, 2. logger.exception registra traza, 3. mensaje de contingencia se envía via whatsapp_service mock, 4. excepción se propaga.</action>
  <verify>python3 -m pytest tests/test_infra_33_timeout.py -v 2>&1 | tail -20</verify>
  <done>Suite nueva PASSED, score de coherencia ≥ 0.900</done>
</task>

---
*Created: 2026-05-16*
