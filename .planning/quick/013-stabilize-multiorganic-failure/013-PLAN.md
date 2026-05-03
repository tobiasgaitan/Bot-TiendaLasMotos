---
task: 013
name: Stabilize Multiorganic Failure
description: Sincronizar deploy.yml, reordenar lifespan en main.py y endurecer config.py.
---

# Quick Task 013: Stabilize Multiorganic Failure

## Objective
Resolve critical race conditions and configuration desyncs across CI/CD and app startup.

## Tasks

<task type="auto">
  <name>Sync CI/CD Workflows</name>
  <files>.github/workflows/deploy.yml</files>
  <action>Add PHONE_NUMBER_ID, WHATSAPP_TOKEN, and FIRESTORE_COLLECTION to the deploy command env vars.</action>
  <verify>grep "PHONE_NUMBER_ID" .github/workflows/deploy.yml</verify>
  <done>deploy.yml contains all necessary environment variables.</done>
</task>

<task type="auto">
  <name>Reorder Main Lifespan</name>
  <files>app/main.py</files>
  <action>Move ConfigLoader initialization before catalog_service initialization.</action>
  <verify>grep -n "ConfigLoader(db)" app/main.py</verify>
  <done>ConfigLoader is initialized before catalog_service.initialize.</done>
</task>

<task type="auto">
  <name>Harden Settings Configuration</name>
  <files>app/core/config.py</files>
  <action>Remove insecure fallbacks and force error on missing critical variables.</action>
  <verify>python3 -c "from app.core.config import settings" 2>&1 | grep "RuntimeError" || true</verify>
  <done>Settings() raises RuntimeError if critical variables are missing.</done>
</task>

---
*Created: 2026-05-03*
