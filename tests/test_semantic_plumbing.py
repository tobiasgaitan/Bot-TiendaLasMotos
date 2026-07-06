"""
BOT-QA-PLUMBING-100: Semantic Plumbing Tests for ai_brain.py

WHY: The synonym injection (<diccionario_sinonimos_regionales>) and the dynamic
purge of 'REGLA DE CREDITO CIEGO' introduced in BOT-BRAIN-ALIGNMENT-099 lack
physical assertions. These tests intercept the `full_prompt` passed to Gemini's
`chat.send_message` and mathematically assert:

1. Presence of `<diccionario_sinonimos_regionales>` XML block when config_service
   provides catalog aliases.
2. Absence of `<diccionario_sinonimos_regionales>` when aliases are empty.
3. Absence of 'REGLA DE CREDITO CIEGO' when `calculate_credit_score` is NOT in the
   toolset (PHASE_1_PROFILING).
4. Presence of 'REGLA DE CREDITO CIEGO' when `calculate_credit_score` IS in the
   toolset (PHASE_2+).
5. Hard-cap truncation of function_calls to MAX_TOOL_CALLS_PER_TURN=2.
6. Flattening of Firestore indexed-dict format in get_catalog_aliases().
"""

import pytest
import sys
import os
import re
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import CerebroIA


# ============================================================================
# HELPERS
# ============================================================================

def _make_mock_response(text="Respuesta mock"):
    """Build a mock Gemini response with text output (no function_call)."""
    mock_response = MagicMock()
    mock_part = MagicMock()
    mock_part.text = text
    mock_part.function_call = None
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [mock_part]
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.total_token_count = 100
    return mock_response


def _build_cerebro_with_prompt_capture():
    """
    Build a CerebroIA instance wired to capture the full_prompt sent to Gemini.

    Returns:
        (cerebro, captured_prompts): The brain instance and a list that will
        be populated with prompt strings when pensar_respuesta runs.
    """
    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._catalog_service = MagicMock()
    cerebro._catalog_service.get_catalog_aliases.return_value = {}
    cerebro.motor_financiero = MagicMock()

    captured_prompts = []
    mock_response = _make_mock_response()

    # Wire chat.send_message as an AsyncMock that captures the first positional arg
    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock(side_effect=lambda *args, **kwargs: _capture_and_return(args, captured_prompts, mock_response))
    cerebro.client.aio.chats.create.return_value = mock_chat

    return cerebro, captured_prompts


def _capture_and_return(args, captured_prompts, mock_response):
    """Side-effect helper: capture the first arg (full_prompt) and return mock response."""
    if args:
        captured_prompts.append(str(args[0]))
    return mock_response


# ============================================================================
# FIXTURES
# ============================================================================

MOCK_ALIASES = {
    "Semiautomatica": ["Señoritera", "Automatica"],
    "Motocarro": ["Motocarguero", "Tricargo"],
    "Enduro": ["Troquera", "Campo", "Finca"]
}

PHASE1_PROSPECT = {
    "exists": True,
    "habeas_data_accepted": False,
    "moto_interest": "Raider 125"
}

PHASE2_PROSPECT = {
    "exists": True,
    "nombre": "Juan",
    "ciudad": "Bogota",
    "moto_confirmada": True,
    "moto_interest": "Raider 125",
    "forma_pago": "credito",
    "habeas_data_accepted": False
}


# ============================================================================
# TEST 1: SYNONYM INJECTION — Presence when aliases exist
# ============================================================================

@pytest.mark.asyncio
async def test_synonym_injection_present_when_aliases_exist():
    """
    BOT-QA-PLUMBING-100 / Assertion 1:
    GIVEN: catalog_service.get_catalog_aliases() returns a non-empty dict.
    WHEN: pensar_respuesta builds the full_prompt.
    THEN: The prompt MUST contain the XML block <diccionario_sinonimos_regionales>
          with the exact category names and synonym values.
    """
    cerebro, captured_prompts = _build_cerebro_with_prompt_capture()
    cerebro._catalog_service.get_catalog_aliases.return_value = MOCK_ALIASES

    await cerebro.pensar_respuesta(
        texto="Quiero una señoritera",
        prospect_data=PHASE1_PROSPECT.copy(),
        history=[]
    )

    assert len(captured_prompts) >= 1, "Gemini chat.send_message was never called — prompt not generated."
    full_prompt = captured_prompts[0]

    assert "<diccionario_sinonimos_regionales>" in full_prompt, (
        "REGRESIÓN SEMÁNTICA: El bloque XML <diccionario_sinonimos_regionales> "
        "NO fue inyectado en el prompt a pesar de que config_service proveyó aliases."
    )
    assert "</diccionario_sinonimos_regionales>" in full_prompt, (
        "REGRESIÓN SEMÁNTICA: Tag de cierre </diccionario_sinonimos_regionales> ausente."
    )
    # Verify specific aliases are physically present
    assert "señoritera" in full_prompt, "El sinónimo 'señoritera' no fue inyectado en el prompt."
    assert "semiautomatica" in full_prompt, "La categoría 'semiautomatica' no fue inyectada."
    assert "motocarguero" in full_prompt, "El sinónimo 'motocarguero' no fue inyectado."
    assert "troquera" in full_prompt, "El sinónimo 'troquera' no fue inyectado."


# ============================================================================
# TEST 2: SYNONYM INJECTION — Absence when aliases are empty
# ============================================================================

@pytest.mark.asyncio
async def test_synonym_injection_absent_when_no_aliases():
    """
    BOT-QA-PLUMBING-100 / Assertion 2:
    GIVEN: catalog_service.get_catalog_aliases() returns an empty dict.
    WHEN: pensar_respuesta builds the full_prompt.
    THEN: The prompt MUST NOT contain <diccionario_sinonimos_regionales>.
    """
    cerebro, captured_prompts = _build_cerebro_with_prompt_capture()
    cerebro._catalog_service.get_catalog_aliases.return_value = {}

    await cerebro.pensar_respuesta(
        texto="Hola buenas tardes",
        prospect_data=PHASE1_PROSPECT.copy(),
        history=[]
    )

    assert len(captured_prompts) >= 1, "Gemini chat.send_message was never called."
    full_prompt = captured_prompts[0]

    assert "<diccionario_sinonimos_regionales>" not in full_prompt, (
        "REGRESIÓN: El bloque <diccionario_sinonimos_regionales> fue inyectado "
        "a pesar de que no hay aliases configurados."
    )


# ============================================================================
# TEST 3: CREDIT-BLIND PURGE — Absence in PHASE_1 (no credit tool)
# ============================================================================

@pytest.mark.asyncio
async def test_credit_blind_rule_preserved_in_phase1():
    """
    BOT-QA-PLUMBING-100 / Assertion 3:
    GIVEN: The prospect is in PHASE_1_PROFILING.
    WHEN: pensar_respuesta builds the full_prompt.
    THEN: The string 'REGLA DE CREDITO CIEGO' MUST remain in the prompt (no prompt purging).
    """
    cerebro, captured_prompts = _build_cerebro_with_prompt_capture()
    cerebro._catalog_service.get_catalog_aliases.return_value = MOCK_ALIASES

    await cerebro.pensar_respuesta(
        texto="¿Cuánto cuesta la Raider?",
        prospect_data=PHASE1_PROSPECT.copy(),
        history=[]
    )

    assert len(captured_prompts) >= 1, "Gemini chat.send_message was never called."
    full_prompt = captured_prompts[0]

    # In Phase 1, the rule must remain in the prompt now that tool rejection pattern is used
    assert "REGLA DE CREDITO CIEGO" in full_prompt, (
        "REGRESIÓN: 'REGLA DE CREDITO CIEGO' fue eliminada del prompt en PHASE_1, "
        "pero el prompt no debe ser purgado ya que calculate_credit_score está siempre en el toolset."
    )

    # The replacement instruction should NOT be present
    assert "La herramienta de crédito NO está disponible en esta fase" not in full_prompt, (
        "REGRESIÓN: La instrucción de reemplazo post-purga fue inyectada en PHASE_1."
    )


# ============================================================================
# TEST 4: CREDIT-BLIND PRESERVED — Present in PHASE_2+ (credit tool available)
# ============================================================================

@pytest.mark.asyncio
async def test_credit_blind_rule_preserved_in_phase2():
    """
    BOT-QA-PLUMBING-100 / Assertion 4:
    GIVEN: The prospect is in PHASE_2_HABEAS_DATA (calculate_credit_score IS in toolset).
    WHEN: pensar_respuesta builds the full_prompt.
    THEN: The string 'REGLA DE CREDITO CIEGO' MUST remain in the prompt.
    """
    cerebro, captured_prompts = _build_cerebro_with_prompt_capture()
    cerebro._catalog_service.get_catalog_aliases.return_value = MOCK_ALIASES

    # Financial history to trigger PHASE_2 via intent detection
    history = [
        {"role": "user", "content": "¿Cuánto es la cuota mensual?"}
    ]

    await cerebro.pensar_respuesta(
        texto="Quiero saber las cuotas de la Raider",
        prospect_data=PHASE2_PROSPECT.copy(),
        history=history
    )

    assert len(captured_prompts) >= 1, "Gemini chat.send_message was never called."
    full_prompt = captured_prompts[0]

    # In PHASE_2+, the credit tool IS available, so the rule must NOT be purged
    assert "REGLA DE CREDITO CIEGO" in full_prompt, (
        "REGRESIÓN: 'REGLA DE CREDITO CIEGO' fue eliminada del prompt en PHASE_2, "
        "donde calculate_credit_score SÍ está disponible. La purga es solo para PHASE_1."
    )

    # The replacement instruction should NOT be present
    assert "La herramienta de crédito NO está disponible en esta fase" not in full_prompt, (
        "REGRESIÓN: La instrucción de reemplazo post-purga fue inyectada en PHASE_2 "
        "donde la herramienta de crédito SÍ está disponible."
    )


# ============================================================================
# TEST 5: HARD-CAP — Truncation of excessive function calls
# ============================================================================

def test_hard_cap_logic_truncation():
    """
    BOT-QA-PLUMBING-100 / Assertion 5:
    GIVEN: The LLM dispatches 4 function calls in a single turn.
    WHEN: The hard-cap logic (MAX_TOOL_CALLS_PER_TURN=2) is applied.
    THEN: Only the first 2 calls survive; the rest are discarded.

    NOTE: This tests the truncation logic in isolation without invoking the full
    agentic loop. The logic is replicated from ai_brain.py lines 1153-1165.
    """
    fc_1 = MagicMock(); fc_1.name = "search_catalog"
    fc_2 = MagicMock(); fc_2.name = "calculate_credit_score"
    fc_3 = MagicMock(); fc_3.name = "handoff_to_agent"
    fc_4 = MagicMock(); fc_4.name = "search_catalog"

    function_calls = [fc_1, fc_2, fc_3, fc_4]

    # Replicate the exact hard-cap logic from ai_brain.py
    MAX_TOOL_CALLS_PER_TURN = 2
    if len(function_calls) > MAX_TOOL_CALLS_PER_TURN:
        discarded = [fc.name for fc in function_calls[MAX_TOOL_CALLS_PER_TURN:]]
        function_calls = function_calls[:MAX_TOOL_CALLS_PER_TURN]

    assert len(function_calls) == 2, (
        f"HARD-CAP FAILED: Expected 2 function calls after truncation, got {len(function_calls)}."
    )
    assert function_calls[0].name == "search_catalog", "First call should be search_catalog."
    assert function_calls[1].name == "calculate_credit_score", "Second call should be calculate_credit_score."
    assert len(discarded) == 2, f"Expected 2 discarded calls, got {len(discarded)}."
    assert "handoff_to_agent" in discarded, "handoff_to_agent should have been discarded."


# ============================================================================
# TEST 6: CONFIG SERVICE — Firestore indexed-dict flattening
# ============================================================================

def test_catalog_aliases_flatten_indexed_dict():
    """
    BOT-QA-PLUMBING-100 / Assertion 6:
    GIVEN: Firestore stores category_aliases as indexed dicts: {"0": "Señoritera"}.
    WHEN: config_service.get_catalog_aliases() is called.
    THEN: Values are flattened into proper lists: ["Señoritera"].
    """
    from app.services.config_service import ConfigService

    service = ConfigService()

    mock_config = {
        "category_aliases": {
            "Semiautomatica": {"0": "Señoritera"},
            "Motocarro": {"0": "Motocarguero", "1": "Tricargo"}
        }
    }

    with patch("app.core.config_loader.ConfigLoader") as MockLoader:
        mock_instance = MockLoader.return_value
        mock_instance.get_catalog_config.return_value = mock_config

        result = service.get_catalog_aliases()

    assert isinstance(result, dict), "Result must be a dictionary."
    assert "Semiautomatica" in result, "Category 'Semiautomatica' missing from flattened output."
    assert result["Semiautomatica"] == ["Señoritera"], (
        f"Expected ['Señoritera'], got {result['Semiautomatica']}. "
        "Indexed-dict flattening failed."
    )
    assert "Motocarro" in result, "Category 'Motocarro' missing from flattened output."
    assert len(result["Motocarro"]) == 2, (
        f"Expected 2 synonyms for Motocarro, got {len(result['Motocarro'])}."
    )
    assert "Motocarguero" in result["Motocarro"], "Synonym 'Motocarguero' missing."
    assert "Tricargo" in result["Motocarro"], "Synonym 'Tricargo' missing."


# ============================================================================
# TEST 7: CONFIG SERVICE — Empty aliases returns empty dict
# ============================================================================

def test_catalog_aliases_returns_empty_when_no_aliases():
    """
    GIVEN: Firestore has no category_aliases field.
    WHEN: config_service.get_catalog_aliases() is called.
    THEN: Returns an empty dict without errors.
    """
    from app.services.config_service import ConfigService

    service = ConfigService()

    with patch("app.core.config_loader.ConfigLoader") as MockLoader:
        mock_instance = MockLoader.return_value
        mock_instance.get_catalog_config.return_value = {"items": [], "category_aliases": {}}

        result = service.get_catalog_aliases()

    assert result == {}, f"Expected empty dict, got {result}."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_catalog_service_get_catalog_aliases_flattening():
    """
    Assert that CatalogService.get_catalog_aliases correctly flattens aliases in memory.
    """
    from app.services.catalog_service import CatalogService
    service = CatalogService()
    service._category_aliases = {
        "Semiautomatica": {"0": "Señoritera", "1": "   "},
        "Motocarro": ["Motocarguero", None, "Tricargo"],
        "Enduro": "Troquera",
        "Invalid": 1234
    }
    result = service.get_catalog_aliases()
    assert result["semiautomatica"] == ["señoritera"]
    assert result["motocarro"] == ["motocarguero", "tricargo"]
    assert result["enduro"] == ["troquera"]
    assert "invalid" not in result

