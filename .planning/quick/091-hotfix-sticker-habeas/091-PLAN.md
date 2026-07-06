---
task: 091
name: hotfix_sticker_habeas
description: El bot no procesa stickers de autorización debido a que el enrutador de WhatsApp transfiere la descripción del VisionService directamente a pensar_respuesta en lugar de normalizar el emoji afirmativo a 'Sí' para el flujo legal.
---

# Quick Task 091: hotfix_sticker_habeas

## Objective
Normalize affirmative WhatsApp stickers (e.g. thumbs up / pulgar arriba) to "Sí" in the webhook router before calling pensar_respuesta, triggering HabeasDataBypassInterrupt for legal approval.

## Tasks

<task type="auto">
  <name>Implement conditional sticker interceptor in whatsapp.py</name>
  <files>[app/routers/whatsapp.py]</files>
  <action>Add checks for msg_type == 'sticker' and affirmative emoji mappings in vision_response or metadata, normalizing it to 'Sí' and wrapping the think loop call with HabeasDataBypassInterrupt exception handling.</action>
  <verify>.venv/bin/pytest tests/test_identity_legal_gate.py</verify>
  <done>Affirmative stickers are successfully normalized to 'Sí' and trigger HabeasDataBypassInterrupt if consent is pending.</done>
</task>

<task type="auto">
  <name>Build specialized test case in tests/test_identity_legal_gate.py</name>
  <files>[tests/test_identity_legal_gate.py]</files>
  <action>Create a unit test simulating a 'sticker' payload that maps to 'Sí' and forces habeas_data_accepted=True or raises HabeasDataBypassInterrupt.</action>
  <verify>.venv/bin/pytest tests/test_identity_legal_gate.py</verify>
  <done>Test suite includes tests simulating incoming sticker webhook processing and assertions pass.</done>
</task>

---
*Created: 2026-07-02*
