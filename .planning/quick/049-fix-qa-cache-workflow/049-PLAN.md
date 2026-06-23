---
task: 049
name: fix-qa-cache-workflow
description: Fallo en qa-pipeline.yml debido a la ausencia de package-lock.json y npm ci.
---

# Quick Task 049: fix-qa-cache-workflow

## Objective
Remove npm cache configuration from actions/setup-node in qa-pipeline.yml workflow, change npm ci to npm install, and add playwright dependency to package.json since package-lock.json is not tracked, avoiding workflow failures.

## Tasks

<task type="auto">
  <name>Remove npm cache, use npm install, and add playwright dependency</name>
  <files>.github/workflows/qa-pipeline.yml package.json</files>
  <action>Remove the 'cache: npm' line from setup-node step, change npm ci to npm install in qa-pipeline.yml, and add playwright to package.json devDependencies</action>
  <verify>git diff .github/workflows/qa-pipeline.yml package.json</verify>
  <done>The cache parameter is removed, npm ci is replaced with npm install, and playwright dependency is present in package.json</done>
</task>
