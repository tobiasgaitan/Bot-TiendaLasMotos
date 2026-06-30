---
task: 081
name: hotfix-anonymous-quota
description: Hotfix for anonymous quota simulation and orchestrator bypass
---

# Quick Task 081: hotfix-anonymous-quota

## Objective
Fix the orchestrator to respond smoothly estimating the base mathematical quota when PermissionError is raised due to missing Habeas Data, and anonymize the commercial entity default "Brilla de Gases" from the returned simulation response.

## Tasks

<task type="auto">
  <name>Anonymize default financial entity in simulation response</name>
  <files>app/services/financial_service.py</files>
  <action>Remove explicit mention of entidad_default from the Markdown returned by _generate_full_simulation_response, ensuring only the formatted numeric values of the payments are shown.</action>
  <verify>pytest tests/test_financial_fallback.py</verify>
  <done>Explicit mention of Brilla de Gases is removed from the returned markdown text.</done>
</task>

<task type="auto">
  <name>Handle Habeas Data PermissionError with direct simulation bypass</name>
  <files>app/services/ai_brain.py</files>
  <action>Add a specific catch block for PermissionError under calculate_credit_score. Resolve the interested moto's price, and bypass Firestore profiling by calling financial_service.calculate_payment directly with hardcoded simulation parameters (24 months, 0 initial, standard entity), returning an anonymous response with the estimated quota.</action>
  <verify>pytest tests/test_perf_45.py</verify>
  <done>PermissionError is caught, a mathematical quota estimate is retrieved, and no Firestore profiling is performed.</done>
</task>

<task type="auto">
  <name>Update tests to match new blind simulation behavior</name>
  <files>tests/test_pcc_ficha_tecnica.py</files>
  <action>Update test_habeas_data_gate_before_credit_score to mock and expect calculate_payment to be called and return the simulated quota when Habeas Data is not signed, asserting the returned text contains pricing information ($250,000) and no provider watermarks.</action>
  <verify>pytest tests/test_pcc_ficha_tecnica.py</verify>
  <done>The test passes verifying the new anonymous simulation bypass behavior.</done>
</task>

---
*Created: 2026-06-30*
