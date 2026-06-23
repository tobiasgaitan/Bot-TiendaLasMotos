---
task: 051
name: hotfix_schema_alignment
description: Align and verify EXTRACTION_SCHEMA in ai_brain.py for legal compliance and prospect identity persistence.
---

# Quick Task 051: hotfix_schema_alignment

## Objective
Verify that EXTRACTION_SCHEMA contains all critical keys for legal compliance and identity tracking ('habeas_data_accepted', 'habeas_data_accepted_sent', 'nombre', 'ciudad'), ensuring alignment with business logic and Firestore schemas.

## Tasks

<task type="auto">
  <name>Align extraction schema</name>
  <files>app/services/ai_brain.py</files>
  <action>Verify and align EXTRACTION_SCHEMA to ensure the four critical keys are explicitly defined under the 'extracted' object.</action>
  <verify>uv run python3 -c "import app.services.ai_brain as a; print(a.EXTRACTION_SCHEMA)"</verify>
  <done>EXTRACTION_SCHEMA explicitly contains 'habeas_data_accepted', 'habeas_data_accepted_sent', 'nombre', and 'ciudad'.</done>
</task>

<task type="auto">
  <name>Verify integrity</name>
  <files>tests/test_identity_legal_gate.py</files>
  <action>Run the full test suite using pytest and the coherence score evaluation command to verify zero regression and 100% success rate.</action>
  <verify>npx agent-cli eval</verify>
  <done>All 131 tests pass with a coherence score of 1.000.</done>
</task>
