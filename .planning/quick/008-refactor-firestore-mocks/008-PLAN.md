---
task: 008
name: Refactor Firestore Mocks
description: Refactor Firestore stream mocks to use AsyncStreamMock and fix Pydantic warnings.
---

# Quick Task 008: Refactor Firestore Mocks

## Objective
Standardize Firestore stream mocks using a dedicated `AsyncStreamMock` class and resolve Pydantic deprecation warnings in the admin router.

## Tasks

<task type="auto">
  <name>Implement AsyncStreamMock</name>
  <files>tests/conftest.py</files>
  <action>Add AsyncStreamMock class to support async iteration (__aiter__, __anext__).</action>
  <verify>grep "class AsyncStreamMock" tests/conftest.py</verify>
  <done>Class exists and implements __aiter__.</done>
</task>

<task type="auto">
  <name>Refactor Tests to use AsyncStreamMock</name>
  <files>tests/test_memory_stream_coverage.py, tests/test_campaign_admin.py</files>
  <action>Replace ad-hoc generators with AsyncStreamMock.</action>
  <verify>PATH=".venv/bin:$PATH" pytest tests/test_memory_stream_coverage.py tests/test_campaign_admin.py</verify>
  <done>Tests pass with 100% success.</done>
</task>

<task type="auto">
  <name>Fix Pydantic Warnings</name>
  <files>app/routers/admin.py</files>
  <action>Migrate class Config to ConfigDict.</action>
  <verify>PATH=".venv/bin:$PATH" pytest app/routers/admin.py --collect-only</verify>
  <done>No deprecation warnings in output.</done>
</task>

---
*Created: 2026-04-30*
