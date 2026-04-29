---
task: 006
name: fix-cicd-uv
description: Inject 'setup-uv' step into GitHub Actions workflows to fix 'uvx' missing command [BOT-DEBT-CICD-006]
---

# Quick Task 006: Fix CICD UV Infrastructure

## Objective
Restore deployment capability by ensuring the GitHub Actions runners have the `uv` tool installed before attempting to use `uvx`.

## Tasks

<task type="auto">
  <name>Inject setup-uv in deploy.yml</name>
  <files>
    <file>.github/workflows/deploy.yml</file>
  </files>
  <action>Add the astral-sh/setup-uv step before the 'Deploy to Cloud Run' step in .github/workflows/deploy.yml.</action>
  <verify>grep "astral-sh/setup-uv" .github/workflows/deploy.yml</verify>
  <done>Step is present in the workflow file.</done>
</task>

<task type="auto">
  <name>Inject setup-uv in deploy-beta.yml</name>
  <files>
    <file>.github/workflows/deploy-beta.yml</file>
  </files>
  <action>Add the astral-sh/setup-uv step before the 'Deploy to Cloud Run' step in .github/workflows/deploy-beta.yml.</action>
  <verify>grep "astral-sh/setup-uv" .github/workflows/deploy-beta.yml</verify>
  <done>Step is present in the workflow file.</done>
</task>

<task type="auto">
  <name>Push changes to remote</name>
  <files>
    <file>.github/workflows/deploy.yml</file>
    <file>.github/workflows/deploy-beta.yml</file>
  </files>
  <action>Commit the changes and push to the beta branch to trigger the pipeline.</action>
  <verify>git log -n 1 --oneline</verify>
  <done>Changes are committed and pushed.</done>
</task>

---
*Created: 2026-04-29*
