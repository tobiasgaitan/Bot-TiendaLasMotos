"""
Tests del Anclaje de Contexto FAQ vs. Embudo — [BOT-PLAN-HARDENING-EGRESS-FUNNEL-001] (Fase 3).

Triple capa certificada:
- Capa A: el function_response de query_faq/query_locations cierra con la
  pregunta pendiente VERBATIM (no el funnel_instruction genérico) cuando el
  turno es FAQ; rama COMPLETO → mandato de cierre de fase.
- Capa B: _compose_faq_brake_block saneado (sin referencia muerta
  <credit_matrix_rules>) y con rama COMPLETO (pending_question == "").
- Capa C: guard post-generación coercitivo — en PHASE_3, si el LLM cambia de
  tema y omite la pregunta de la matriz, se re-inyecta determinísticamente.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.ai_brain import CerebroIA
from app.services.credit_faq_taxonomy import TurnIntent
from tests.test_faq_and_location_tools import (
    _build_cerebro_with_scripted_chat,
    _make_fc_response,
    _make_text_response,
)

PRIVACY_LINK = "https://tiendalasmotos.com/politica-de-privacidad"

# Prospecto en PHASE_3 (habeas firmado + link en historial + nombre/ciudad),
# con la matriz a medias: ocupacion CAPTURADA, ingresos_mensuales PENDIENTE.
PHASE3_PROSPECT = {
    "exists": True,
    "nombre": "Carlos",
    "ciudad": "Bogotá",
    "moto_interest": "Raider 125",
    "forma_pago": "crédito",
    "habeas_data_accepted": True,
    "habeas_data_accepted_sent": True,
    "ocupacion": "Empleado",
}

PHASE3_HISTORY = [
    {"role": "model", "content": f"¿me autorizas el tratamiento de tus datos? (Política: {PRIVACY_LINK})"},
    {"role": "user", "content": "Sí, autorizo"},
]

PENDING_QUESTION = "¿Cuáles son tus ingresos mensuales?"


# ---------------------------------------------------------------------------
# Capa B — _compose_faq_brake_block
# ---------------------------------------------------------------------------

class TestCapaBBrakeBlock:
    def test_brake_quotes_pending_question_verbatim(self):
        cerebro = CerebroIA()
        block = cerebro._compose_faq_brake_block("¿necesito codeudor?", PENDING_QUESTION, TurnIntent.FAQ_ONLY)
        assert f'CIERRE OBLIGATORIO: Repite TEXTUALMENTE: "{PENDING_QUESTION}"' in block
        assert "[FRENO FAQ — MÁXIMA PRIORIDAD]" in block

    def test_brake_no_dead_credit_matrix_rules_reference(self):
        cerebro = CerebroIA()
        block = cerebro._compose_faq_brake_block("¿necesito codeudor?", PENDING_QUESTION, TurnIntent.FAQ_ONLY)
        assert "<credit_matrix_rules>" not in block
        assert "query_faq" in block

    def test_brake_completo_branch_emits_phase_close_mandate(self):
        cerebro = CerebroIA()
        block = cerebro._compose_faq_brake_block("¿necesito codeudor?", "", TurnIntent.FAQ_ONLY)
        assert 'Repite TEXTUALMENTE: ""' not in block
        assert "COMPLETA" in block
        assert "calculate_credit_score" in block

    def test_brake_mixed_keeps_simulation_instruction(self):
        cerebro = CerebroIA()
        block = cerebro._compose_faq_brake_block("¿y la inicial?", PENDING_QUESTION, TurnIntent.MIXED)
        assert "Simulación permitida" in block
        assert f'Repite TEXTUALMENTE: "{PENDING_QUESTION}"' in block


# ---------------------------------------------------------------------------
# Capa A — function_response con ancla verbatim
# ---------------------------------------------------------------------------

class TestCapaAFunctionResponseAnchor:
    @pytest.mark.asyncio
    async def test_faq_tool_response_carries_verbatim_pending_question(self):
        cerebro, sent_payloads = _build_cerebro_with_scripted_chat([
            _make_fc_response("query_faq", {"query": "codeudor crédito"}),
            _make_text_response(f"No en todos los casos. {PENDING_QUESTION}"),
        ])
        result = await cerebro.pensar_respuesta(
            texto="¿necesito codeudor para el crédito?",
            prospect_data=dict(PHASE3_PROSPECT),
            history=list(PHASE3_HISTORY),
        )
        assert len(sent_payloads) == 2
        payload = str(sent_payloads[1])
        assert "[ANCLA DE EMBUDO" in payload
        assert f'"{PENDING_QUESTION}"' in payload
        assert PENDING_QUESTION in result

    @pytest.mark.asyncio
    async def test_faq_tool_response_completo_emits_close_mandate(self):
        full_matrix = {
            **PHASE3_PROSPECT,
            "ingresos_mensuales": "2.000.000",
            "datacredito": "Al día",
            "gastos_mensuales": "1.000.000",
            "tiene_gas_natural": "Sí",
            "vivienda": "Propia",
            "plan_celular": "Sí",
        }
        cerebro, sent_payloads = _build_cerebro_with_scripted_chat([
            _make_fc_response("query_faq", {"query": "codeudor crédito"}),
            _make_text_response("No en todos los casos."),
        ])
        await cerebro.pensar_respuesta(
            texto="¿necesito codeudor para el crédito?",
            prospect_data=full_matrix,
            history=list(PHASE3_HISTORY),
        )
        payload = str(sent_payloads[1])
        assert "[ANCLA DE EMBUDO" in payload
        assert "COMPLETA" in payload
        assert "calculate_credit_score" in payload


# ---------------------------------------------------------------------------
# Capa C — re-inyección coercitiva post-generación (PHASE_3)
# ---------------------------------------------------------------------------

class TestCapaCCoerciveReinjection:
    @pytest.mark.asyncio
    async def test_missing_pending_question_is_appended_deterministically(self):
        """El LLM responde la FAQ pero CAMBIA DE TEMA (omite la pregunta de la
        matriz): Capa C la re-inyecta al final, violando la deriva temática."""
        cerebro, _ = _build_cerebro_with_scripted_chat([
            _make_fc_response("query_faq", {"query": "codeudor crédito"}),
            _make_text_response("No necesitas codeudor en todos los casos, tranquilo."),
        ])
        result = await cerebro.pensar_respuesta(
            texto="¿necesito codeudor para el crédito?",
            prospect_data=dict(PHASE3_PROSPECT),
            history=list(PHASE3_HISTORY),
        )
        assert result.endswith(PENDING_QUESTION)
        assert "No necesitas codeudor" in result

    @pytest.mark.asyncio
    async def test_present_pending_question_is_not_duplicated(self):
        cerebro, _ = _build_cerebro_with_scripted_chat([
            _make_fc_response("query_faq", {"query": "codeudor crédito"}),
            _make_text_response(f"No en todos los casos. Volviendo a lo nuestro, {PENDING_QUESTION}"),
        ])
        result = await cerebro.pensar_respuesta(
            texto="¿necesito codeudor para el crédito?",
            prospect_data=dict(PHASE3_PROSPECT),
            history=list(PHASE3_HISTORY),
        )
        assert result.count(PENDING_QUESTION) == 1

    @pytest.mark.asyncio
    async def test_capa_c_does_not_fire_outside_phase3(self):
        """Alcance PHASE_3: en PHASE_1 la pregunta pendiente genérica NO se
        re-inyecta coercitivamente (el cierre queda gobernado por el freno, Capa B)."""
        cerebro, _ = _build_cerebro_with_scripted_chat([
            _make_fc_response("query_faq", {"query": "requisitos reportados"}),
            _make_text_response("Para reportados: Cédula + 10% de inicial."),
        ])
        result = await cerebro.pensar_respuesta(
            texto="¿qué requisitos piden si estoy reportado?",
            prospect_data={"exists": True, "nombre": "Carlos", "ciudad": "Bogotá",
                           "moto_interest": "Raider 125", "forma_pago": "crédito"},
            history=[],
        )
        assert result == "Para reportados: Cédula + 10% de inicial."
        assert "¿En qué más puedo ayudarte?" not in result
