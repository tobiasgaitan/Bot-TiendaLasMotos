---
task: 049
name: fix-qa-cache-workflow
description: Fallo en qa-pipeline.yml debido a la ausencia de package-lock.json y npm ci.
---

# Quick Task 049: fix-qa-cache-workflow

## Objective
Remove npm cache configuration from actions/setup-node in qa-pipeline.yml workflow, change npm ci to npm install, add playwright and whap dependencies to package.json, start the FastAPI bot server in background, and adapt webhook response payloads for integration tests.

## Tasks

<task type="auto">
  <name>Surgical Refactoring of workflow, dependencies, and webhook handler</name>
  <files>.github/workflows/qa-pipeline.yml package.json app/routers/whatsapp.py app/main.py</files>
  <action>Remove setup-node cache, setup python and uv, run uvicorn in background in qa-pipeline.yml; add playwright and whap mock server to package.json; update webhook_handler and lifespan exception handler to run seamlessly in test mode.</action>
  <verify>git diff .github/workflows/qa-pipeline.yml package.json app/routers/whatsapp.py app/main.py</verify>
  <done>All components are updated and the local pytest suite passes successfully.</done>
</task>
