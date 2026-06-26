---
task: 071
name: hotfix-trace-propagation
description: Decorate webhook background handler to propagate Langfuse tracing
---

# Quick Task 071: Langfuse Trace Propagation

## Objective
Ensure the Meta webhook background handler (`_handle_message_background` in `app/routers/whatsapp.py`) initiates a Langfuse trace root and propagates context (user_id and session_id) so that all downstream agentic execution steps are correctly nested within the same parent trace.

## Tasks

<task type="auto">
  <name>Decorate Webhook Handler and Propagate Context</name>
  <files>
    <file>app/routers/whatsapp.py</file>
  </files>
  <action>
    Import langfuse observe and langfuse_context with graceful fallback in app/routers/whatsapp.py.
    Decorate _handle_message_background with @observe(name="whatsapp_webhook_background").
    Inside _handle_message_background, once user_phone is normalized, invoke langfuse_context.update_current_trace with user_id, session_id, and metadata.
  </action>
  <verify>pytest tests/test_trace_propagation.py</verify>
  <done>The handler is successfully decorated and passes the verification test asserting that the decorator is applied and updates the trace context correctly.</done>
</task>

<task type="auto">
  <name>Create Tracing Verification Test</name>
  <files>
    <file>tests/test_trace_propagation.py</file>
  </files>
  <action>
    Create a unit test file tests/test_trace_propagation.py that mocks langfuse.decorators.observe and langfuse_context.update_current_trace.
    Execute _handle_message_background in a mock setup and verify that the trace is initialized and the context is updated.
  </action>
  <verify>pytest tests/test_trace_propagation.py</verify>
  <done>All tests in test_trace_propagation.py pass and verify trace propagation.</done>
</task>

---
*Created: 2026-06-26*
