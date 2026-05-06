---
task: 017
name: Infrastructure Pipeline Retrigger
description: Force redeploy to kill zombie containers and sync infrastructure fixes.
---

# Quick Task 017: Infrastructure Pipeline Retrigger

## Objective
Force a clean redeploy to GCP Cloud Run by pushing local infrastructure and documentation fixes to the `beta` branch, resolving the "zombie revision" desynchronization.

## Tasks

<task type="auto">
  <name>Stage and Commit Infrastructure Fixes</name>
  <files>.github/workflows/deploy-beta.yml, Dockerfile, .planning/ROADMAP.md</files>
  <action>Stage all local changes and commit with the mandatory message: 'chore(infra): force redeploy to kill zombie containers'</action>
  <verify>git status && git log -n 1</verify>
  <done>Local fixes staged and committed with the requested message.</done>
</task>

<task type="auto">
  <name>Pre-push Evaluation</name>
  <files>all</files>
  <action>Execute the mandatory evaluation to ensure system coherence before push.</action>
  <verify>npx agent-cli eval</verify>
  <done>Evaluation score >= 0.9 achieved.</done>
</task>

<task type="auto">
  <name>Push to Beta Branch</name>
  <files>None</files>
  <action>Push the commit to the remote origin/beta to trigger GitHub Actions.</action>
  <verify>git push origin beta</verify>
  <done>Commit pushed to remote beta branch.</done>
</task>

---
*Created: 2026-05-06*
