---
task: 079
name: hotfix-ci-uv-cache
description: Fix 'Post Setup uv' exit code 2 issue by disabling cache in GitHub Actions runner.
---

# Quick Task 079: hotfix-ci-uv-cache

## Objective
Fix the `Post Setup uv` cleanup step crash in GitHub Actions by injecting `enable-cache: false` into the `Setup uv` step configuration in `.github/workflows/qa-pipeline.yml`.

## Tasks

<task type="auto">
  <name>hotfix-ci-uv-cache</name>
  <files>.github/workflows/qa-pipeline.yml</files>
  <action>Inject `enable-cache: false` under the `with:` directive in the `Setup uv` step.</action>
  <verify>git status && gh run list --branch fix/pipeline-qa-gate-073</verify>
  <done>Pipeline completes correctly with green status.</done>
</task>

---
*Created: 2026-06-27*
