---
task: 019
name: Dockerfile README Fix
description: Fix Cloud Build failure 'OSError: Readme file does not exist: README.md' by including README.md in the initial COPY step.
---

# Quick Task 019: Dockerfile README Fix

## Objective
Ensure `uv sync` has access to the `README.md` file required by the build backend as specified in `pyproject.toml`.

## Tasks

<task type="auto">
  <name>Modify Dockerfile</name>
  <files>Dockerfile</files>
  <action>Update the COPY instruction to include README.md before the first uv sync.</action>
  <verify>grep "README.md" Dockerfile</verify>
  <done>Dockerfile updated correctly.</done>
</task>

---
*Created: 2026-05-07*
