---
task: 010
name: Fix CI/CD Env Vars Error
description: Fix parsing failure in CI/CD pipeline caused by unsupported --set-env-vars flag
---

# Quick Task 010: Fix CI/CD Env Vars Error

## Objective
Update `.github/workflows/deploy.yml` to replace the unsupported `--set-env-vars` flag with `--update-env-vars` to fix the `google-agents-cli v0.1.2` deployment error.

## Tasks

<task type="auto">
  <name>Update CLI flag in deploy.yml</name>
  <files>.github/workflows/deploy.yml</files>
  <action>Replace `--set-env-vars` with `--update-env-vars` on line 32, preserving secrets syntax.</action>
  <verify>grep -- "--update-env-vars" .github/workflows/deploy.yml</verify>
  <done>Flag is updated to `--update-env-vars`</done>
</task>

---
*Created: 2026-05-02*
