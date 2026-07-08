---
task: 138
name: hotfix-habeas-emoji-reaction
description: Intercept WhatsApp affirmative reactions and force immediate Habeas Data acceptance in Firestore/memory before inference.
---

# Quick Task 138: hotfix-habeas-emoji-reaction

## Objective
Ensure that when a user reacts with an affirmative emoji (👍) to sign Habeas Data, we immediately mutate `habeas_data_accepted = True` síncronamente in Firestore and in memory before invoking CerebroIA.pensar_respuesta.

## Tasks

<task type="auto">
  <name>Intercept positive reaction and force database and memory mutation</name>
  <files>
    - app/routers/whatsapp.py
  </files>
  <action>
    - In `app/routers/whatsapp.py` inside `_handle_message_background`:
      - Keep track of `is_positive_reaction` when extracting the reaction payload.
      - In the session management flow, if `is_positive_reaction` is True, synchronously await `ms.update_prospect_summary(user_phone, "", {"habeas_data_accepted": True})` to update Firestore.
      - Ensure that `prospect_data` dictionary in memory also has `habeas_data_accepted = True` before/after re-fetching.
  </action>
  <verify>
    npx @tobiasgaitan/agent-cli eval
  </verify>
  <done>
    Verification passes and score remains at 1.000.
  </done>
</task>

<task type="auto">
  <name>Inject test case in tests/test_identity_legal_gate.py</name>
  <files>
    - tests/test_identity_legal_gate.py
  </files>
  <action>
    - Add a test case `test_whatsapp_reaction_payload_direct_legal_acceptance` that emulates the WhatsApp reaction webhook payload and asserts that `habeas_data_accepted` is immediately committed to memory/Firestore before AI inference.
  </action>
  <verify>
    pytest tests/test_identity_legal_gate.py
  </verify>
  <done>
    All tests in test_identity_legal_gate.py pass successfully.
  </done>
</task>
