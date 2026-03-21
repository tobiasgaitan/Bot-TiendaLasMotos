import pytest
import asyncio
pytestmark = pytest.mark.skip(reason="Deprecado - Sprint 1 Zombie Purge (c4599e2)")
from unittest.mock import MagicMock
from app.services.ai_brain import CerebroIA

# Ensure vertexai is available otherwise model won't init
import vertexai
try:
    vertexai.init(project="tiendalasmotos", location="us-central1")
except Exception as e:
    print(f"Skipping vertex init (expected if already run or locally mocked): {e}")

import pytest
def test_intent_evaluator():
    print("🧪 Starting Intent Evaluator Test...\n")
    
    cerebro = CerebroIA()
    
    if not cerebro._model:
        print("⚠️ Warning: CerebroIA model failed to initialize. Ensure GOOGLE_APPLICATION_CREDENTIALS is set.")
        print("Test will evaluate the Fail-Closed fallback instead.")
    
    # Test 1: Positive match (Answering the survey)
    print("--- Test 1: Answering Survey ---")
    question1 = "¿A qué te dedicas, eres empleado, independiente o pensionado?"
    answer1 = "soy empleado fijo"
    result1 = cerebro.evaluate_survey_intent(answer1, question1)
    print(f"Result: {result1}")
    assert result1["is_answering_survey"] == True, "Failed Test 1: Should be True"
    
    # Test 2: Negative match (Context Switch)
    print("\n--- Test 2: Context Switch ---")
    question2 = "¿A qué te dedicas, eres empleado, independiente o pensionado?"
    answer2 = "¿Tienen disponibles motos NKD 125?"
    result2 = cerebro.evaluate_survey_intent(answer2, question2)
    print(f"Result: {result2}")
    if cerebro._model:
        assert result2["is_answering_survey"] == False, "Failed Test 2: Should be False"
    else:
         assert result2["is_answering_survey"] == True, "Fallback must be true"

    # Test 3: Vague Answer (Should still be part of survey, not a switch)
    print("\n--- Test 3: Vague Answer (True) ---")
    question3 = "¿Cuáles son tus ingresos comprobables al mes?"
    answer3 = "no se la verdad, como el minimo creo"
    result3 = cerebro.evaluate_survey_intent(answer3, question3)
    print(f"Result: {result3}")
    assert result3["is_answering_survey"] == True, "Failed Test 3: Should be True"
    
    # Test 4: Resilience (Simulating an exception)
    print("\n--- Test 4: Resilience (Force Exception) ---")
    # Temporarily break the model to force exception handling
    temp_model = cerebro._model
    cerebro._model = "malformed_model_object" 
    result4 = cerebro.evaluate_survey_intent("test", "test")
    print(f"Result: {result4}")
    assert result4["is_answering_survey"] == True, "Failed Test 4 (Resilience): Should default to True on error"
    
    # Restore model
    cerebro._model = temp_model

    print("\n🎉 All intent evaluator tests passed!")

if __name__ == "__main__":
    test_intent_evaluator()
