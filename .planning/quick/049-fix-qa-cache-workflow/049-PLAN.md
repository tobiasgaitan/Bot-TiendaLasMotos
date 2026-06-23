---
task: 049
name: fix-qa-cache-workflow
description: Fallo en qa-pipeline.yml debido a la ausencia de package-lock.json requerido por el flag de caché en actions/setup-node.
---

# Quick Task 049: fix-qa-cache-workflow

## Objective
Remove npm cache configuration from actions/setup-node in qa-pipeline.yml workflow since package-lock.json is not tracked, avoiding workflow failures due to missing lockfile.

## Tasks

<task type="auto">
  <name>Remove npm cache from setup-node step</name>
  <files>.github/workflows/qa-pipeline.yml</files>
  <action>Remove the 'cache: npm' line from the setup-node step in .github/workflows/qa-pipeline.yml</action>
  <verify>git diff .github/workflows/qa-pipeline.yml</verify>
  <done>The 'cache: npm' parameter is removed from the setup-node step in the workflow file</done>
</task>
