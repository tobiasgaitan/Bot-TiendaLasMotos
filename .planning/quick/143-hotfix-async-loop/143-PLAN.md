---
task: 143
name: hotfix-async-loop
description: Implement synchronous/blocking mechanism in whatsapp.py to prevent webhook race conditions and ensure Firestore persistence completes before releasing the request
---

# Quick Task 143: hotfix-async-loop

## Objective
Prevent race conditions and context rot under concurrent webhook bursts by serializing message handling per canonical phone number using an asynchronous lock.

## Tasks

<task type="auto">
  <name>Implement asyncio session locks in whatsapp.py</name>
  <files>[app/routers/whatsapp.py]</files>
  <action>Add a session-based locking mechanism (_session_locks and _get_session_lock) and wrap the message processing loop in _handle_message_background with an async lock context manager.</action>
  <verify>.venv/bin/pytest tests/test_agentic_loop_async.py</verify>
  <done>Session locking logic added to whatsapp.py and async tests pass successfully.</done>
</task>
