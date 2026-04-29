---
task: 003
name: CLI Environment Isolation
description: Create .npmrc, scaffold private package.json, and replace gcloud with uvx google-agents-cli
---

# Quick Task 003: CLI Environment Isolation

## Objective
Isolate the CLI environment from the public npm registry by configuring a private scope, scaffolding the internal tool's `package.json`, and updating Google Cloud deployments to use the ADK 2026 standard `uvx google-agents-cli`.

## Tasks

<task type="auto">
  <name>Create .npmrc and package.json</name>
  <files>.npmrc, package.json</files>
  <action>Create .npmrc in project root to map @tiendalasmotos to a private registry to avoid ghost code. Create package.json scaffolding the internal tool @tiendalasmotos/agent-cli.</action>
  <verify>cat .npmrc && cat package.json</verify>
  <done>.npmrc and package.json are correctly created</done>
</task>

<task type="auto">
  <name>Update GitHub Actions to use uvx</name>
  <files>.github/workflows/deploy.yml, .github/workflows/deploy-beta.yml</files>
  <action>Replace `gcloud run deploy` commands with `uvx google-agents-cli` as requested.</action>
  <verify>grep -r "uvx google-agents-cli" .github/workflows/</verify>
  <done>Workflows use uvx google-agents-cli exclusively.</done>
</task>

<task type="auto">
  <name>Update deploy.sh to use uvx</name>
  <files>deploy.sh</files>
  <action>Replace `gcloud run deploy` with `uvx google-agents-cli` in deploy.sh.</action>
  <verify>grep "uvx google-agents-cli" deploy.sh</verify>
  <done>Script updated.</done>
</task>

---
*Created: 2026-04-29*
