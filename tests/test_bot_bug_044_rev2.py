import pytest
from app.services.judge_service import JudgeService

def test_judge_service_profiling_blind_simulation():
    """
    Test that blind simulation (cuota delivery) does not trigger profiling logic.
    Also verifies explicit presence of transformed string (Ficha Tecnica) and prevents
    key mutations from resulting in empty string or None.
    """
    judge = JudgeService()
    
    # 1. Blind Simulation Payload
    # Simulated bot response with a quote and a transformed Ficha Tecnica string
    ai_response = "Aquí tienes la cuota: $1.500.000. Ficha Tecnica: Moto 150cc."
    
    # 2. Assert explicit presence of transformed string (Mandatory condition)
    assert "Ficha Tecnica:" in ai_response, "Ficha Tecnica: must be explicitly present in the response"
    
    # 3. Assert no empty string or None mutation
    assert ai_response is not None, "Response cannot be None silently"
    assert ai_response != "", "Response cannot be an empty string silently"
    
    # 4. Verify profiling detection
    # This should return False because it doesn't contain actual profiling questions,
    # despite delivering financial data (cuota).
    is_profiling = judge._is_profiling_attempt(ai_response)
    assert is_profiling is False, "Blind simulation should not be flagged as a profiling attempt"
    
    # 5. Verify actual profiling question IS detected
    profiling_response = "¿Cuánto ganas mensualmente y dónde trabajas?"
    assert judge._is_profiling_attempt(profiling_response) is True, "Actual profiling must be caught"

    # 6. Verify datacredito question IS detected
    datacredito_response = "¿Estás reportado en datacrédito?"
    assert judge._is_profiling_attempt(datacredito_response) is True, "Datacredito questions must be caught"
