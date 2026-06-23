---
task: 047
name: api-boundary-optimization
description: Implement Meta webhook signature verification, template payload sanity, and content assertion test.
---

# Quick Task 047: API Boundary Optimization

## Objective
Enhance API boundaries by verifying Meta webhook signatures, adding payload sanity checks for template variables, and establishing content assertion tests to prevent regressions.

## Tasks

<task type="auto">
  <name>Configure App Secret and Webhook Signature Verification</name>
  <files>[app/core/config.py, app/routers/whatsapp.py]</files>
  <action>Add WHATSAPP_APP_SECRET setting and verify X-Hub-Signature-256 header in webhook_handler in app/routers/whatsapp.py.</action>
  <verify>Run unit tests to verify the signature checks.</verify>
  <done>Signature validation correctly blocks unsigned/invalid requests and accepts valid ones.</done>
</task>

<task type="auto">
  <name>Payload Sanity for Meta Templates</name>
  <files>[app/services/whatsapp_service.py]</files>
  <action>Implement conditional bypass to completely omit the 'components' key from template payloads when no dynamic variables exist.</action>
  <verify>Run tests sending template with empty/None variables and assert that components key is omitted.</verify>
  <done>Templates with empty or no variables are built without the components key.</done>
</task>

<task type="auto">
  <name>Establish API Boundary and Content Assertion Tests</name>
  <files>[tests/test_api_bounds.py]</files>
  <action>Create unit tests verifying webhook signature validation, template payload sanity, and content assertions (checking 'Ficha Tecnica:' presence and preventing silent None or empty strings).</action>
  <verify>.venv/bin/pytest tests/test_api_bounds.py</verify>
  <done>All tests under test_api_bounds.py pass successfully.</done>
</task>

---
*Created: 2026-06-23*
