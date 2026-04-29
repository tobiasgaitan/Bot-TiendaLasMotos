---
task: 005
name: fix-test-regressions
description: Fix phone normalization test assertion and CC extraction syntax warning [BOT-BUGFIX-EVAL-005]
---

# Quick Task 005: Fix Test Regressions

## Objective
Resolve the remaining test failure in `scripts/test_phone_normalization.py` and the syntax warning in `app/tests/test_cc_extraction.py` to achieve a clean evaluation score.

## Tasks

<task type="auto">
  <name>Fix Phone Normalization Assertion</name>
  <files>
    <file>scripts/test_phone_normalization.py</file>
  </files>
  <action>Update the test cases in scripts/test_phone_normalization.py to align with the 12-digit international format (prefix 57) returned by PhoneNormalizer.normalize().</action>
  <verify>python3 scripts/test_phone_normalization.py</verify>
  <done>All assertions in scripts/test_phone_normalization.py pass.</done>
</task>

<task type="auto">
  <name>Fix CC Extraction Syntax Warning</name>
  <files>
    <file>app/tests/test_cc_extraction.py</file>
  </files>
  <action>Convert the docstring of _extract_cc_logic to a raw string (r""") to prevent invalid escape sequence warnings for \d.</action>
  <verify>pytest app/tests/test_cc_extraction.py</verify>
  <done>SyntaxWarning is no longer present when running the test.</done>
</task>

---
*Created: 2026-04-29*
