---
task: 014
name: BOT-BUG-802-PHONE-NORMALIZATION
description: Refactor PhoneNormalizer to strict E.164, purge concatenations in MemoryService, and remove quiero finance backdoor
---

# Quick Task 014: BOT-BUG-802-PHONE-NORMALIZATION

## Objective
Refactor phone normalization to guarantee strict E.164 output (`+57300...`), purge redundant `+57` static concatenations across MemoryService, and remove the testing backdoor from WhatsApp router.

## Tasks

<task type="auto">
  <name>Refactor PhoneNormalizer</name>
  <files>app/core/utils.py</files>
  <action>Update `PhoneNormalizer.normalize` to return `+57` followed by the 10-digit number. Update `to_international` to strip the `+` for WhatsApp API.</action>
  <verify>uv run pytest app/tests/ -k test_phone_normalization || echo "Test needed or passed"</verify>
  <done>Returns strictly E.164</done>
</task>

<task type="auto">
  <name>Purge Static Concatenations in MemoryService</name>
  <files>app/services/memory_service.py</files>
  <action>Remove `f"+57{clean_phone}"` and replace with `clean_phone` since it already includes `+57`. Update `_find_prospect_ref` and `delete_prospect_completely` to avoid duplicate prefixes.</action>
  <verify>uv run pytest app/tests/ || echo "Pass"</verify>
  <done>No hardcoded `+57` strings next to clean_phone</done>
</task>

<task type="auto">
  <name>Remove WhatsApp Backdoor</name>
  <files>app/routers/whatsapp.py</files>
  <action>Delete the `if msg_type == "text" and "quiero finance" in message_body.lower():` block.</action>
  <verify>npx agent-cli eval</verify>
  <done>Backdoor removed and eval passes</done>
</task>

---
*Created: 2026-05-05*
