---
task: 153
name: Hotfix Audio Lineage Sync
description: BOT-ROUTER-AUDIO-LINEAGE-123 — Desacoplar el bloque LINEAR BLOCKING de la restricción msg_type=='text' para garantizar sincronización de memoria end-to-end para mensajes de audio post-reset.
---

# Quick Task 153: Hotfix Audio Lineage Sync

## Objetivo

Garantizar paridad de linaje de datos Entrada→Procesamiento→Persistencia para audio, eliminando
la posibilidad de que un payload de audio post-reset consuma contexto obsoleto y reinyecte el flag
`human_help_requested=True`.

## Diagnóstico Forense (Autopsia Física)

### Causa Raíz Confirmada — Arquitectura Asimétrica

El flujo de `msg_type == "text"` (L1023–L1061) ejecuta el LINEAR BLOCKING
(`generate_and_update_summary` + re-fetch de `prospect_data`) desde el contexto de sesión
**ya cargado** en la sección §2 (L852–1007), que incluye:
- `prospect_data` fresco post-reset (L996)
- Verificación `human_help_requested` (L1000–1002)
- `current_history` actualizado (L944)

El flujo `elif msg_type == "audio"` (L1243+) **duplica** la lógica de sesión de forma autónoma
(L1249–1261) pero **sin heredar el estado post-reset de la sección §2**. La consecuencia:

1. Si llega `/reset` (texto) → Firestore borrado → prospect_data = `{exists: False}` → sesión §2
   recrea el prospecto → `prospect_data` fresco → LINEAR BLOCKING correcto.

2. Si llega audio inmediatamente después del reset (antes de que el cache de la sección §2 se propague):
   - El bloque `audio` en L1249 llama `ms.create_prospect_if_missing` ✓
   - Pero L1256 hace `get_prospect_data` **antes** de `generate_and_update_summary`
   - Si el dato en Firestore aún contiene un `human_help_requested: True` residual de la sesión
     anterior (race condition entre delete y create), L1257-1259 silencia el bot **sin chance de
     sincronización**.
   - El `generate_and_update_summary` del audio (L1283) no tiene acceso al `prospect_data` recién
     hidratado de §2, porque §2 devuelve early `return` antes de llegar a L1243 cuando
     `human_help_requested` es True.

### Causa Secundaria Confirmada — `human_help_requested` Residual

La section §2 (L1000-1002) verifica `human_help_requested` **después** de `transition_to_in_progress`
(L990) y `get_prospect_data` refresh (L996). Si el delete del reset fue exitoso pero el create_prospect
(L936-937) no eliminó el flag (por un documento recién recreado con campos heredados), el check de
L1000 silencia el bot antes de alcanzar el bloque audio.

El bloque audio tiene su propia verificación en L1257-1259, que sufre el mismo problema: si el
`get_prospect_data` del audio ve un doc con `human_help_requested: True` (residual pre-sync), el
bot se silencia sin ejecutar el LINEAR BLOCKING.

### Solución Quirúrgica

**Opción elegida:** Mover la verificación `human_help_requested` del bloque `audio` (L1257-1259)
**después** del `generate_and_update_summary` + re-fetch (L1283-1291), de modo que el re-fetch
post-sync sea el dato autoritativo. Esto espeja exactamente el patrón del bloque `text`.

---

## Tareas

<task type="auto">
  <name>TASK-1: Reordenar verificación human_help_requested en bloque audio post-LINEAR-BLOCKING</name>
  <files>app/routers/whatsapp.py</files>
  <action>
    En el bloque `elif msg_type == "audio"` (aprox. L1243–1292), mover el check de
    `human_help_requested` (actualmente en L1257-1259, ANTES de la transcripción) para que ocurra
    DESPUÉS del re-fetch post-generate_and_update_summary (después de L1291). Esto garantiza que el
    check usa el `prospect_data` sincronizado con Firestore, no el dato potencialmente obsoleto.

    El orden final del bloque audio debe ser:
    1. create_prospect_if_missing (sin cambio)
    2. update_last_interaction (sin cambio)
    3. get_prospect_data inicial (solo para cargar current_history)
    4. get_chat_history (sin cambio)
    5. download_media / transcribe (sin cambio)
    6. save_message transcription (sin cambio)
    7. generate_and_update_summary [LINEAR BLOCKING] (sin cambio)
    8. RE-FETCH prospect_data (re-fetch autoritativo)
    9. *** AQUÍ: verificación human_help_requested post-sync ***
    10. get_chat_history post-sync (para inferencia con contexto fresco)
    11. AI inference / judge (sin cambio)
  </action>
  <verify>cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos && python3 -c "import ast; ast.parse(open('app/routers/whatsapp.py').read()); print('AST OK')"</verify>
  <done>El check de human_help_requested en el bloque audio usa prospect_data post-generate_and_update_summary</done>
</task>

<task type="auto">
  <name>TASK-2: Inyectar test de caracterización — ráfaga /reset seguida de audio ('Reader')</name>
  <files>tests/test_audio_regression.py</files>
  <action>
    Añadir `test_audio_lineage_post_reset_no_desertion` al final del archivo. Este test:
    1. Simula que `get_prospect_data` devuelve `human_help_requested: True` en la primera llamada
       (estado residual post-reset).
    2. Simula que tras `generate_and_update_summary`, el re-fetch devuelve `human_help_requested: False`
       (estado correcto post-sync con Firestore limpio).
    3. Afirma que `pensar_respuesta` FUE llamado (el bot no se silenció con el dato obsoleto).
    4. Afirma que `generate_and_update_summary` fue llamado exactamente una vez (sincronización
       bloqueante ejecutada).
    5. Afirma que `set_human_help_status(True)` NO fue llamado (no hay falsa deserción).
  </action>
  <verify>cd /Users/tobiasgaitangallego/Bot-TiendaLasMotos && python3 -m pytest tests/test_audio_regression.py -v 2>&1 | tail -20</verify>
  <done>El nuevo test pasa, prohibiendo la reinyección del flag de deserción por contexto obsoleto</done>
</task>

---
*Creado: 2026-07-10*
