"""
[BOT-BUILD-COHERENCE-WAVE07-01-PROMPT-TOOLS-001]
Tests for the backend knowledge tools `query_faq` / `query_locations` and their
data container app/services/faq_service.py.

WHY: The <KNOWLEDGE_BASE> block (<credit_matrix_rules> + <locations>) was
migrated out of the system prompt into deterministic backend functions exposed
to the LLM via function-calling. These tests pin:

1. get_faq_answer — per-topic matching + full-matrix fallback.
2. get_location_info — per-branch/city matching + all-branches fallback.
3. Tool registration — CerebroIA._create_tools() always exposes both tools.
4. Dispatcher integration — an LLM function_call reaches faq_service and the
   deterministic payload is sent back to Gemini as a function response part.
"""
import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.faq_service import (
    FAQ_RULES,
    LOCATIONS,
    get_faq_answer,
    get_location_info,
)


# ============================================================================
# 1. UNIT — get_faq_answer (credit_matrix_rules migrada)
# ============================================================================

class TestGetFaqAnswer:
    """Pins de paridad contra el <credit_matrix_rules> original del prompt."""

    def test_empleados_query(self):
        res = get_faq_answer("¿Qué requisitos piden si soy empleado?")
        assert "Empleados: Requieren Cédula, email, celular." in res
        assert "150%" in res

    def test_reportados_query(self):
        res = get_faq_answer("estoy reportado en datacredito, qué piden?")
        assert "Reportados: Requieren Cédula + 10% de inicial OBLIGATORIA." in res

    def test_extranjeros_query_with_accent(self):
        res = get_faq_answer("Soy extranjero con PPT, ¿qué documentos necesito?")
        assert "Extranjeros: Requieren PPT/PEP + Pasaporte + Dirección física." in res

    def test_brilla_query(self):
        res = get_faq_answer("¿Puedo sacarlo por Brilla con los recibos del gas?")
        assert "Brilla: Requieren Cédula + 2 últimos recibos de gas pagados." in res

    def test_generic_query_returns_full_matrix(self):
        """Consultas abstractas (codeudor/fiador/requisitos) reciben la matriz
        completa para que el LLM no alucine una regla inexistente."""
        res = get_faq_answer("¿necesito codeudor para el crédito?")
        for entry in FAQ_RULES.values():
            assert str(entry["answer"]) in res

    def test_empty_query_returns_full_matrix(self):
        res = get_faq_answer("")
        for entry in FAQ_RULES.values():
            assert str(entry["answer"]) in res

    def test_case_and_accent_insensitivity(self):
        res = get_faq_answer("REPORTADO")
        assert "Reportados:" in res


# ============================================================================
# 2. UNIT — get_location_info (locations migradas)
# ============================================================================

class TestGetLocationInfo:
    """Pins de paridad contra el <locations> original del prompt."""

    def test_santa_marta_city_returns_its_three_branches(self):
        res = get_location_info("¿Tienen tiendas en Santa Marta?")
        assert res.count("https://maps.app.goo.gl/") == 3
        assert "Santa Marta (11 Noviembre): Calle 30 # 79-85." in res
        assert "Santa Marta (Piragua): Sector 1 Mz I Casa 4 L 4." in res
        assert "Santa Marta (Gaira): Carrera 4 # 20-45." in res
        assert "Riohacha" not in res

    def test_specific_neighborhood_gaira(self):
        res = get_location_info("¿dónde queda la sede de Gaira?")
        assert "Santa Marta (Gaira): Carrera 4 # 20-45." in res
        assert "https://maps.app.goo.gl/FG6jFQKm1J1httLZ6" in res

    def test_riohacha(self):
        res = get_location_info("¿hay sede en Riohacha?")
        assert "Riohacha: Calle 15 # 11A-12." in res
        assert "https://maps.app.goo.gl/8fp1D2c2due6UHMo9" in res
        assert "Santa Marta" not in res

    def test_zona_bananera_orihueca(self):
        res = get_location_info("¿tienen punto en la Zona Bananera?")
        assert "Zona Bananera (Orihueca): Calle 5 # 2-135." in res
        assert "https://maps.app.goo.gl/1savLzhGmEfB3qDT6" in res

    def test_generic_query_returns_all_locations(self):
        res = get_location_info("¿dónde están ubicados?")
        assert res.count("https://maps.app.goo.gl/") == len(LOCATIONS) == 5

    def test_empty_query_returns_all_locations(self):
        res = get_location_info("")
        assert res.count("https://maps.app.goo.gl/") == len(LOCATIONS)


# ============================================================================
# 3. REGISTRATION — query_faq / query_locations en el toolset del LLM
# ============================================================================

class TestKnowledgeToolRegistration:
    """[WAVE07-01] Las dos herramientas deben estar SIEMPRE en el toolset,
    con o sin calculate_credit_score (omit_credit)."""

    @staticmethod
    def _tool_names(omit_credit: bool = False):
        import app.services.ai_brain as brain_module

        with patch.object(brain_module, "SDK_AVAILABLE", True):
            cerebro = brain_module.CerebroIA()
            cerebro._determine_funnel_phase = MagicMock(return_value="PHASE_1_PROFILING")
            tools = cerebro._create_tools(omit_credit=omit_credit)
        assert tools, "El toolset no debe ser None/vacío."
        return [
            fd.name
            for tool in tools
            for fd in tool.function_declarations
        ]

    def test_query_faq_and_locations_registered(self):
        names = self._tool_names(omit_credit=False)
        assert "query_faq" in names
        assert "query_locations" in names
        assert "calculate_credit_score" in names

    def test_knowledge_tools_survive_omit_credit(self):
        names = self._tool_names(omit_credit=True)
        assert "query_faq" in names
        assert "query_locations" in names
        assert "calculate_credit_score" not in names


# ============================================================================
# 4. DISPATCHER INTEGRATION — function_call -> faq_service -> function response
# ============================================================================

def _make_fc_response(tool_name: str, tool_args: dict):
    """Mock Gemini response carrying a single function_call part."""
    mock_response = MagicMock()
    mock_part = MagicMock()
    mock_part.text = None
    fc = MagicMock()
    fc.name = tool_name
    fc.args = tool_args
    mock_part.function_call = fc
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [mock_part]
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.total_token_count = 100
    return mock_response


def _make_text_response(text: str):
    mock_response = MagicMock()
    mock_part = MagicMock()
    mock_part.text = text
    mock_part.function_call = None
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [mock_part]
    mock_response.usage_metadata = MagicMock()
    mock_response.usage_metadata.total_token_count = 100
    return mock_response


def _build_cerebro_with_scripted_chat(script: list):
    """CerebroIA wired to a mock chat that pops scripted responses in order.
    Returns (cerebro, sent_payloads) where sent_payloads collects every arg
    passed to chat.send_message."""
    from app.services.ai_brain import CerebroIA

    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._catalog_service = MagicMock()
    cerebro._catalog_service.get_catalog_aliases.return_value = {}
    cerebro.motor_financiero = MagicMock()

    sent_payloads = []
    responses = list(script)

    async def _send(*args, **kwargs):
        if args:
            sent_payloads.append(args[0])
        return responses.pop(0)

    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock(side_effect=_send)
    cerebro.client.aio.chats.create.return_value = mock_chat
    return cerebro, sent_payloads


@pytest.mark.asyncio
async def test_dispatcher_query_faq_returns_credit_matrix_to_llm():
    """GIVEN el LLM invoca query_faq('reportados'),
    WHEN el dispatcher ejecuta la herramienta,
    THEN la regla determinista viaja de vuelta a Gemini en el function response."""
    cerebro, sent_payloads = _build_cerebro_with_scripted_chat([
        _make_fc_response("query_faq", {"query": "requisitos para reportados"}),
        _make_text_response("Para reportados: Cédula + 10% de inicial. ¿Desde qué ciudad nos escribes?"),
    ])

    result = await cerebro.pensar_respuesta(
        texto="¿qué requisitos piden si estoy reportado?",
        prospect_data={"exists": True, "nombre": "Carlos", "ciudad": "Bogotá",
                       "moto_interest": "Raider 125", "forma_pago": "crédito"},
        history=[],
    )

    assert result == "Para reportados: Cédula + 10% de inicial. ¿Desde qué ciudad nos escribes?"
    assert len(sent_payloads) == 2, "Debe haber turno de tool-response tras la llamada."
    tool_turn_payload = str(sent_payloads[1])
    assert "Reportados: Requieren Cédula + 10% de inicial OBLIGATORIA." in tool_turn_payload


@pytest.mark.asyncio
async def test_dispatcher_query_locations_returns_branch_to_llm():
    """GIVEN el LLM invoca query_locations('Riohacha'),
    WHEN el dispatcher ejecuta la herramienta,
    THEN la dirección determinista viaja de vuelta a Gemini."""
    cerebro, sent_payloads = _build_cerebro_with_scripted_chat([
        _make_fc_response("query_locations", {"query": "Riohacha"}),
        _make_text_response("Nuestra sede en Riohacha queda en la Calle 15 # 11A-12."),
    ])

    result = await cerebro.pensar_respuesta(
        texto="¿tienen sede en Riohacha?",
        prospect_data={"exists": True, "nombre": "Carlos", "ciudad": "Riohacha",
                       "moto_interest": "Raider 125", "forma_pago": "crédito"},
        history=[],
    )

    assert result == "Nuestra sede en Riohacha queda en la Calle 15 # 11A-12."
    assert len(sent_payloads) == 2
    tool_turn_payload = str(sent_payloads[1])
    assert "Riohacha: Calle 15 # 11A-12. https://maps.app.goo.gl/8fp1D2c2due6UHMo9" in tool_turn_payload


@pytest.mark.asyncio
async def test_dispatcher_knowledge_tool_failure_degrades_with_log(caplog):
    """Zero-Silent-Failures: si faq_service explota, el dispatcher loguea
    logger.exception y devuelve un degradado controlado al LLM (sin re-raise)."""
    cerebro, sent_payloads = _build_cerebro_with_scripted_chat([
        _make_fc_response("query_faq", {"query": "boom"}),
        _make_text_response("Un asesor confirmará el dato. ¿Desde qué ciudad nos escribes?"),
    ])

    with patch("app.services.ai_brain.get_faq_answer", side_effect=RuntimeError("boom")):
        result = await cerebro.pensar_respuesta(
            texto="¿qué requisitos piden?",
            prospect_data={"exists": True, "nombre": "Carlos", "ciudad": "Bogotá",
                           "moto_interest": "Raider 125", "forma_pago": "crédito"},
            history=[],
        )

    assert result == "Un asesor confirmará el dato. ¿Desde qué ciudad nos escribes?"
    assert len(sent_payloads) == 2
    assert "Error temporal consultando la base de conocimiento" in str(sent_payloads[1])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
