---
task: 056
name: hotfix-health-check-state-uncouple
description: Uncouple health check endpoint from app.state.config_loader dependencies
---

# Quick Task 056: hotfix-health-check-state-uncouple

## Objective
Uncouple the /health endpoint from app.state.config_loader dependencies, substituting it with a safe and fault-tolerant return supported by try/except blocks and forensic logging, to prevent AttributeError exceptions when accessed during startup.

## Tasks

<task type="auto">
  <name>Modify health_check in app/main.py</name>
  <files>app/main.py</files>
  <action>Replace the health_check endpoint implementation in app/main.py with a safe getattr check and try/except blocks around config_loader, catalog_service, and storage_service calls.</action>
  <verify>Run the new test_health_check unit test.</verify>
  <done>The health check returns a 200 HTTP response even when app.state.config_loader is not set or initialized.</done>
</task>

<task type="auto">
  <name>Create unit test for health check</name>
  <files>tests/test_health_check.py</files>
  <action>Create a unit test checking that /health behaves safely when config_loader is not initialized on app.state.</action>
  <verify>.venv/bin/pytest tests/test_health_check.py</verify>
  <done>The tests pass successfully.</done>
</task>

---
*Created: 2026-06-24*
