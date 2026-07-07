---
task: 132
name: Bot Audit Competition Cache
description: Resolve the cache bypass and decouple the competitor brands array to load dynamically from Firestore.
---

# Quick Task 132: Bot Audit Competition Cache

## Objective
Decouple competitor brands to Firestore configuration and ensure competitor warning is applied post-cache.

## Tasks

<task type="auto">
  <name>Modify config loader and catalog service</name>
  <files>app/core/config_loader.py,app/services/catalog_service.py,app/services/ai_brain.py</files>
  <action>Add competitor_brands to config loader default, change catalog service search_catalog to run check post-cache and load brands dynamically, and update ai_brain.py to load them dynamically.</action>
  <verify>.venv/bin/pytest tests/test_competitor_protocol.py</verify>
  <done>All edits applied and test passes.</done>
</task>

<task type="auto">
  <name>Create unit tests for competitor cache and config</name>
  <files>tests/test_competitor_cache.py</files>
  <action>Create a new test file tests/test_competitor_cache.py validating semantic cache hits with competitor brands, dynamic updates, prevention of duplication, and torito/motocarro bajaj matches.</action>
  <verify>.venv/bin/pytest tests/test_competitor_cache.py</verify>
  <done>New tests pass successfully with rigid assertions for presence of system tag, control of duplication, and hot-mutated brands.</done>
</task>
