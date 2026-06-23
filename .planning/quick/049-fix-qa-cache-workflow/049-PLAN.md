---
task: 049
name: fix-qa-cache-workflow
description: Fallo en qa-pipeline.yml debido a la ausencia de package-lock.json requerido por el flag de caché en actions/setup-node y consecuente fallo de npm ci.
---

# Quick Task 049: fix-qa-cache-workflow

## Objective
Remove npm cache configuration from actions/setup-node in qa-pipeline.yml workflow and change npm ci to npm install since package-lock.json is not tracked, avoiding workflow failures due to missing lockfile.

## Tasks

<task type="auto">
  <name>Remove npm cache from setup-node step and use npm install</name>
  <files>.github/workflows/qa-pipeline.yml</files>
  <action>Remove the 'cache: npm' line from the setup-node step and change npm ci to npm install in .github/workflows/qa-pipeline.yml</action>
  <verify>git diff .github/workflows/qa-pipeline.yml</verify>
  <done>The 'cache: npm' parameter is removed and npm ci is replaced with npm install in the workflow file</done>
</task>
