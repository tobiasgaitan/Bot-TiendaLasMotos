---
task: 016
name: CORS & Identity Enforcement
description: Fix CORS 403 illegal config in main.py, purge to_international from utils.py, inline strip in whatsapp_service.py
---

# Quick Task 016: CORS & Identity Enforcement

## Objective
Fix illegal CORS wildcard-with-credentials configuration and purge the redundant `to_international()` method, consolidating phone format logic into `normalize()` (E.164) with inline strip for Meta API transport.

## Tasks

<task type="auto">
  <name>Fix CORS Origins</name>
  <files>app/main.py</files>
  <action>Replace allow_origins=["*"] with explicit list: ['https://tiendalasmotos-beta.web.app', 'https://tiendalasmotos.com', 'http://localhost:3000']</action>
  <verify>grep -n "allow_origins" app/main.py</verify>
  <done>CORS configured with explicit origins and updated comments</done>
</task>

<task type="auto">
  <name>Purge to_international & Fix Callers</name>
  <files>app/core/utils.py, app/services/whatsapp_service.py</files>
  <action>1. Delete to_international() from PhoneNormalizer. 2. In whatsapp_service.py replace all 3 calls to PhoneNormalizer.to_international(x) with PhoneNormalizer.normalize(x).lstrip("+") — Meta API requires digits-only format without the + prefix.</action>
  <verify>grep -rn "to_international" app/ && python3 -c "from app.core.utils import PhoneNormalizer; print(PhoneNormalizer.normalize('3192564288'))"</verify>
  <done>to_international purged. whatsapp_service uses normalize().lstrip("+"). normalize() returns E.164 (+573...)</done>
</task>

<task type="auto">
  <name>Update utils.py Docstrings</name>
  <files>app/core/utils.py</files>
  <action>Update class docstring to reflect E.164 contract. Remove references to "10-digit national" format.</action>
  <verify>cat app/core/utils.py</verify>
  <done>Docstrings reflect E.164 (+57XXXXXXXXXX) as the single output format</done>
</task>

---
*Created: 2026-05-06*
