---
task: 178
name: Orchestrator Hardware Alignment
description: Propagation of moto_cc and category to payment helper in all four blind simulation calls
---

# Quick Task 178: Orchestrator Hardware Alignment

## Objective
Extract and propagate the hardware variables `moto_cc` and `category` from `first_match` of the catalog search to `self._calculate_payment_helper` in all four blind simulation scenarios in `app/services/ai_brain.py`.

## Tasks

<task type="auto">
  <name>Refactor app/services/ai_brain.py to extract and pass hardware variables</name>
  <files>app/services/ai_brain.py</files>
  <action>Surgically modify the four blind calculation points in app/services/ai_brain.py to extract and pass moto_cc and category</action>
  <verify>pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>The tests pass successfully and verify the correct parameters are propagated</done>
</task>
