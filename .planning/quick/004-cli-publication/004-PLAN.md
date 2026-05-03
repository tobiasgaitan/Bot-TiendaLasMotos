---
task: 004
name: CLI Publication to GitHub Packages
description: Publish @tiendalasmotos/agent-cli to GitHub Packages and verify installation.
---

# Quick Task 004: CLI Publication

## Objective
Restore the remote CLI environment by publishing the scoped package to GitHub Packages, fixing the 404 error and enabling GSD guardrails.

## Tasks

<task type="auto">
  <name>Verify NPM_TOKEN and Publish</name>
  <files>package.json, bin/agent-cli.js</files>
  <action>Confirm NPM_TOKEN is set, then execute npm publish --access=restricted.</action>
  <verify>npm view @tiendalasmotos/agent-cli version</verify>
  <done>Package is visible in the registry.</done>
</task>

<task type="auto">
  <name>Install and Link Binary</name>
  <files>node_modules/</files>
  <action>npm install @tiendalasmotos/agent-cli to force binary linking in .bin.</action>
  <verify>ls -F node_modules/.bin/agent-cli</verify>
  <done>Binary exists in node_modules/.bin.</done>
</task>

<task type="auto">
  <name>Final Verification (Eval)</name>
  <files>n/a</files>
  <action>Run npx @tiendalasmotos/agent-cli eval to verify execution.</action>
  <verify>npx @tiendalasmotos/agent-cli eval</verify>
  <done>CLI executes successfully and passes coherence check (or fails logically but executes).</done>
</task>

---
*Created: 2026-04-29*
