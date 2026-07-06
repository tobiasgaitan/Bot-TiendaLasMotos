---
task: 093
name: hotfix-tool-loop-exit
description: "El bucle robusto de ejecución de herramientas agénticas agota sus turnos (max_turns=3) al interceptar la consulta semántica de la categoría expandida, provocando una salida prematura sin asignación de la variable de texto final y forzando el retorno del método _fallback_response."
---

# Quick Task 093: hotfix-tool-loop-exit

## Objective
Prevent the robust tool execution loop in `app/services/ai_brain.py` from falling back to generic responses on catalog query success, and unify the catalog results, credit simulation, and Habeas Data script into a single synchronous response by raising `HabeasDataBypassInterrupt` when Habeas Data is not yet accepted.

## Tasks

<task type="auto">
  <name>Surgical Interception and Fallback Handling in ai_brain.py</name>
  <files>[ai_brain.py](file:///Users/tobiasgaitangallego/Bot-TiendaLasMotos/app/services/ai_brain.py)</files>
  <action>
    - Initialize `last_catalog_response = ""` and `last_catalog_matches = []` at the beginning of the `ROBUST TOOL EXECUTION LOOP`.
    - In `search_catalog` tool handling, set these variables when results are found.
    - If results are found and Habeas Data has not been accepted (`not (prospect_data or {}).get("habeas_data_accepted")`), compute the 10% down payment/monthly credit installment simulation for the first matching motorcycle, format it, append to the catalog response, add the Habeas Data consent text, and immediately raise `HabeasDataBypassInterrupt(unified_response)`.
    - In case the tool execution loop finishes (exhausts turns) or has an empty AI text response but `catalog_returned_results` is True, format the final response using `last_catalog_response` directly instead of returning the fallback response.
  </action>
  <verify>uv run pytest tests/test_agentic_loop_async.py && npx agent-cli eval</verify>
  <done>Suite of tests passing and coherence score of 1.000 verified.</done>
</task>

---
*Created: 2026-07-02*
