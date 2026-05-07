---
task: 018
name: Fix GitHub Actions Deploy Syntax
description: Correct the illegal --source option and positional argument in deploy-beta.yml by switching to direct gcloud run deploy.
---

# Quick Task 018: Fix GitHub Actions Deploy Syntax

## Objective
Resolve the 'No such option: --source' error in the beta pipeline by refactoring the deployment step to use the standard `gcloud run deploy` command, which correctly supports source-based deployments and custom service names.

## Tasks

<task type="auto">
  <name>Refactor deploy-beta.yml</name>
  <files>.github/workflows/deploy-beta.yml</files>
  <action>Replace the 'uvx google-agents-cli deploy' command with 'gcloud run deploy bot-tiendalasmotos-beta' using correct gcloud syntax for --source and --set-env-vars.</action>
  <verify>grep "gcloud run deploy" .github/workflows/deploy-beta.yml</verify>
  <done>Workflow updated to use standard gcloud deployment syntax.</done>
</task>

<task type="auto">
  <name>Push to Beta Branch</name>
  <files>None</files>
  <action>Commit and push the fix to trigger the pipeline.</action>
  <verify>git push origin beta</verify>
  <done>Changes pushed and pipeline re-triggered.</done>
</task>

---
*Created: 2026-05-07*
