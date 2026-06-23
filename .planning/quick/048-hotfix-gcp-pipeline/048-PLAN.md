---
task: 048
name: hotfix-gcp-pipeline
description: Fix GCP Cloud Run version misalignment and offline stoon compilation in CI/CD pipeline
---

# Quick Task 048: Hotfix GCP Pipeline Alignment

## Objective
Align the GCP Cloud Run beta service with version v10.8.0 by fixing the CI/CD pipeline to package the correct dependencies and use an offline git clone of the S-TOON protocol during Docker compilation.

## Tasks

<task type="auto">
  <name>Modify app/main.py startup check</name>
  <files>
    <file>app/main.py</file>
  </files>
  <action>Update the startup check log in app/main.py to print '🚀 STARTUP CHECK: v10.8.0 - API Boundary Protection'.</action>
  <verify>grep "🚀 STARTUP CHECK: v10.8.0 - API Boundary Protection" app/main.py</verify>
  <done>Log string matches exactly.</done>
</task>

<task type="auto">
  <name>Update Dockerfile for offline git clone</name>
  <files>
    <file>Dockerfile</file>
  </files>
  <action>Modify the Dockerfile to COPY the pre-cloned S-TOON-Protocol directory and configure git insteadOf to redirect GitHub S-TOON URL to local directory before running uv sync.</action>
  <verify>grep "insteadOf" Dockerfile</verify>
  <done>Dockerfile is updated with COPY and git configuration.</done>
</task>

<task type="auto">
  <name>Update GHA Workflows to pre-clone stoon and force Dockerfile</name>
  <files>
    <file>.github/workflows/deploy-beta.yml</file>
    <file>.github/workflows/deploy.yml</file>
  </files>
  <action>Add a step in GHA workflows to pre-clone S-TOON-Protocol and ensure gcloud run deploy uses --dockerfile=Dockerfile.</action>
  <verify>grep "Pre-clone S-TOON" .github/workflows/deploy-beta.yml</verify>
  <done>Workflows are updated to pre-clone stoon and use --dockerfile.</done>
</task>

<task type="auto">
  <name>Verify locally and push changes</name>
  <files>
    <file>app/main.py</file>
    <file>Dockerfile</file>
    <file>.github/workflows/deploy-beta.yml</file>
    <file>.github/workflows/deploy.yml</file>
  </files>
  <action>Run evaluation and unit tests locally, commit changes and push to beta branch to trigger the pipeline.</action>
  <verify>git log -n 1 --oneline</verify>
  <done>All tests pass, and commits are pushed to origin/beta.</done>
</task>
