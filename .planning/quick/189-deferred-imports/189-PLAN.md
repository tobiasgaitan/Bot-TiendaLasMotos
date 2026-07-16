---
task: 189
name: Deferred Imports app/main.py
description: Move all heavy external network SDK imports inside app/main.py, app/routers/whatsapp.py, and app/routers/admin.py to run inside the lifespan background task or under demand (lazy imports), achieving module import time < 0.1s.
---

# Quick Task 189: Deferred Imports app/main.py

## Objective
Move heavy external infrastructure imports (google.cloud, google.oauth2, vertex_ai) to run inside lifespan or lazily under demand, reducing app/main.py initial import time to <0.1s.

## Tasks

<task type="auto">
  <name>Refactor app/main.py and routers to use lazy imports</name>
  <files>
    <file>app/main.py</file>
    <file>app/routers/whatsapp.py</file>
    <file>app/routers/admin.py</file>
    <file>app/core/security.py</file>
  </files>
  <action>Remove module-level imports of heavy external SDKs and move them locally inside functions or initialization blocks.</action>
  <verify>.venv/bin/python -c "import time; t0 = time.time(); import app.main; elapsed = time.time() - t0; print('Import elapsed:', elapsed); assert elapsed < 1.0"</verify>
  <done>Module app.main imports in < 1 second and the test suite passes.</done>
</task>

<task type="auto">
  <name>Add strict module import timing assertion in tests/test_startup_lock.py</name>
  <files>
    <file>tests/test_startup_lock.py</file>
  </files>
  <action>Create a test in tests/test_startup_lock.py to validate that app.main imports in less than 1.0 second.</action>
  <verify>.venv/bin/pytest tests/test_startup_lock.py</verify>
  <done>All tests in test_startup_lock.py pass, including the new module-level import speed test.</done>
</task>

---
*Created: 2026-07-16*
