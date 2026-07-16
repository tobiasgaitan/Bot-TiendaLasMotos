---
task: 193
name: Health Port Binding Hotfix
description: Refactor the health endpoint in app/main.py to be immediately and synchronously responsive (returning starting status if not ready) and add robust test verification.
---

# Quick Task 193: Health Port Binding Hotfix

## Objective
Refactor the `/health` endpoint in `app/main.py` to be synchronous and immediately return `{"status": "starting", "detail": "Catalog initialization in progress"}` when `catalog_ready` is False, avoiding any external service or storage calls. Implement `test_health_endpoint_never_returns_503_during_hydration` in `tests/test_startup_lock.py`.

## Tasks

<task type="auto">
  <name>Modify app/main.py</name>
  <files>[app/main.py]</files>
  <action>Refactor the /health endpoint to be synchronous and return the starting status immediately if catalog_ready is False, bypassing any potential exceptions or network calls from uninitialized services.</action>
  <verify>.venv/bin/pytest tests/test_health_check.py</verify>
  <done>The /health endpoint is refactored to be synchronous and immediately responsive when not ready.</done>
</task>

<task type="auto">
  <name>Modify tests/test_startup_lock.py</name>
  <files>[tests/test_startup_lock.py]</files>
  <action>Implement test_health_endpoint_never_returns_503_during_hydration using TestClient to assert HTTP 200 OK and status/detail checks in dehydrated states.</action>
  <verify>.venv/bin/pytest tests/test_startup_lock.py</verify>
  <done>The test is implemented and passes successfully.</done>
</task>
