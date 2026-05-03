---
task: 010
name: Fix Hatchling Build & Sync
description: Fix build failure in uv sync by mapping app/ directory and migrate dev-dependencies.
---

# Quick Task 010: Fix Hatchling Build & Sync

## Objective
Fix the build failure in `uv sync` by explicitly mapping the `app/` directory to the project in `pyproject.toml` and resolving the deprecated `dev-dependencies` warning.

## Tasks

<task type="auto">
  <name>Update pyproject.toml mapping and dependency-groups</name>
  <files>pyproject.toml</files>
  <action>Add [tool.hatch.build.targets.wheel] with packages = ["app"] and rename [tool.uv.dev-dependencies] to [dependency-groups].dev</action>
  <verify>uv sync</verify>
  <done>uv sync completes successfully without build backend errors or depreciation warnings.</done>
</task>

<task type="auto">
  <name>Sync STATE.md for Build Failure Awareness</name>
  <files>.planning/STATE.md</files>
  <action>Update Score to 0.000 PENDING to reflect the current environment state.</action>
  <verify>cat .planning/STATE.md | grep "SCORE ACTUAL: 0.000"</verify>
  <done>STATE.md reflects the real state of the environment.</done>
</task>

<task type="auto">
  <name>Final Evaluation Verification</name>
  <files>none</files>
  <action>Run agent-cli eval to capture the real score after build fix.</action>
  <verify>./bin/agent-cli.js eval</verify>
  <done>Evaluation executes physically and reports the current test results.</done>
</task>

---
*Created: 2026-05-02*
