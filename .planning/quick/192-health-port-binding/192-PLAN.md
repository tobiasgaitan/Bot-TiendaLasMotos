---
task: 192
name: Health Port Binding & Catalog Decoupling
description: Isolate health endpoint from catalog size constraints and move the >= 60 items check exclusively to WhatsApp middlewares.
---

# Quick Task 192: Health Port Binding & Catalog Decoupling

## Objective
Isolate the `/health` endpoint from catalog size restrictions (ensuring immediate HTTP 200 and `"status": "starting"` prior to/without full size hydration), and move the rigid catalog size check (at least 60 items) exclusively inside the WhatsApp router middlewares in `app/routers/whatsapp.py` to prevent GCP container port binding timeout crashes.

## Tasks

<task type="auto">
  <name>Modify app/main.py</name>
  <files>[app/main.py]</files>
  <action>Remove the min_catalog_items check from the deferred initialization task and inline initialization in app/main.py. Ensure catalog_ready is set to True once initialization is complete (even if catalog size is less than 60). Verify `/health` continues to return "starting" while initialization is in progress.</action>
  <verify>.venv/bin/pytest tests/test_startup_lock.py</verify>
  <done>The minimum catalog item size check is completely removed from app/main.py, and catalog_ready is set to True upon initialization completion regardless of catalog size.</done>
</task>

<task type="auto">
  <name>Modify tests/test_startup_lock.py</name>
  <files>[tests/test_startup_lock.py]</files>
  <action>Update test cases in tests/test_startup_lock.py to align with catalog size validation decoupling from main.py, and add a test verifying via TestClient that GET /health returns HTTP 200 OK and "status": "starting" immediately when the catalog is empty (0 items) before hydration is complete.</action>
  <verify>.venv/bin/pytest tests/test_startup_lock.py</verify>
  <done>All tests in tests/test_startup_lock.py pass, including the new validation for immediately returning HTTP 200 and 'starting' when catalog has 0 items before hydration.</done>
</task>
