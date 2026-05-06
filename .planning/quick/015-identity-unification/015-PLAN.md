---
task: 015
name: Identity Unification
description: Eliminar concatenación manual f'+57{normalized_phone}' en admin.py y survey_service.py y forzar PhoneNormalizer
---

# Quick Task 015: Identity Unification

## Objective
Unificar la normalización de números de teléfono en todo el sistema utilizando `PhoneNormalizer.normalize()` y eliminar duplicidad de `mark_as_read`.

## Tasks

<task type="auto">
  <name>Refactor Phone Normalization</name>
  <files>app/routers/admin.py, app/services/survey_service.py</files>
  <action>Remove hardcoded `+57` prefixes and strictly use `PhoneNormalizer.normalize()` for document IDs and phone fields.</action>
  <verify>uv run pytest</verify>
  <done>All hardcoded prefixes removed and tests pass.</done>
</task>

<task type="auto">
  <name>Remove mark_as_read Redundancy</name>
  <files>app/routers/whatsapp.py</files>
  <action>Eliminate the duplicated `_mark_message_as_read` function and calls since it's now handled globally at the start of the webhook.</action>
  <verify>uv run pytest</verify>
  <done>Function and specific local calls deleted, tests pass.</done>
</task>

---
*Created: 2026-05-06*
