"""
[BOT-BUILD-COHERENCE-WAVE07-02-BLIND-CREDIT-001]
Tests for the deterministic Blind Credit (Crédito Ciego) fallback injected in
the `calculate_credit_score` tool handler (app/services/ai_brain.py).

WHY: The blind-credit defaults (Brilla de Gases / Empleado / SMLV /
Sin experiencia / plan Sí / sin reportes / inicial 10%) must be injected by
INFRASTRUCTURE when the LLM omits parameters — never assumed by the prompt.
Resolution priority is preserved: f_args (+aliases) > prospect_data (CRM) > default.

Coverage:
1. Unit — _apply_blind_credit_defaults (empty/null/blank payload, alias
   respect, CRM respect, immutability of input, fail-open + logger.exception).
2. Integration — dispatcher path: empty tool payload reaches the financial
   motor with all defaults; LLM-provided values survive injection.
"""
import logging
import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_brain import (
    BLIND_CREDIT_DEFAULTS,
    _apply_blind_credit_defaults,
)

EXPECTED_DEFAULTS = {
    "entidad": "Brilla de Gases",
    "ocupacion_y_contrato": "Empleado",
    "ingresos_demostrables": "SMLV",
    "historial_datacredito": "Sin experiencia",
    "plan_celular": "Sí",
    "reportes": "No",
    "inicial": "10%",
}


# ============================================================================
# 0. CONTRACT — defaults dict parity with the ticket spec
# ============================================================================

def test_blind_credit_defaults_match_ticket_spec():
    assert BLIND_CREDIT_DEFAULTS == EXPECTED_DEFAULTS


# ============================================================================
# 1. UNIT — _apply_blind_credit_defaults
# ============================================================================

class TestApplyBlindCreditDefaults:
    def test_empty_payload_injects_all_defaults(self):
        result = _apply_blind_credit_defaults({}, {"exists": True})
        for key, default in EXPECTED_DEFAULTS.items():
            assert result[key] == default, f"Default no inyectado para '{key}'."

    def test_none_payload_injects_all_defaults(self):
        result = _apply_blind_credit_defaults(None, None)
        for key, default in EXPECTED_DEFAULTS.items():
            assert result[key] == default

    @pytest.mark.parametrize("missing", [None, "", "   "])
    def test_null_and_blank_values_are_treated_as_missing(self, missing):
        result = _apply_blind_credit_defaults(
            {"entidad": missing, "plan_celular": missing}, None
        )
        assert result["entidad"] == "Brilla de Gases"
        assert result["plan_celular"] == "Sí"

    def test_llm_values_are_preserved(self):
        payload = {
            "ocupacion_y_contrato": "Independiente",
            "historial_datacredito": "Reportado",
            "plan_celular": "No",
        }
        result = _apply_blind_credit_defaults(payload, None)
        assert result["ocupacion_y_contrato"] == "Independiente"
        assert result["historial_datacredito"] == "Reportado"
        assert result["plan_celular"] == "No"
        # Solo los omitidos se inyectan
        assert result["ingresos_demostrables"] == "SMLV"
        assert result["entidad"] == "Brilla de Gases"

    def test_alias_keys_prevent_injection(self):
        """Variantes del LLM ('ocupacion', 'datacredito') cuentan como provistas."""
        result = _apply_blind_credit_defaults(
            {"ocupacion": "Independiente", "datacredito": "Al día"}, None
        )
        assert "ocupacion_y_contrato" not in result
        assert "historial_datacredito" not in result

    def test_crm_values_prevent_injection(self):
        """El CRM (prospect_data) tiene prioridad sobre el default."""
        prospect = {
            "ocupacion": "Pensionado",
            "datacredito": "Castigado",
            "plan_celular": "No",
        }
        result = _apply_blind_credit_defaults({}, prospect)
        assert "ocupacion_y_contrato" not in result
        assert "historial_datacredito" not in result
        assert "plan_celular" not in result
        # Los no presentes en CRM sí se inyectan
        assert result["ingresos_demostrables"] == "SMLV"

    def test_input_payload_is_not_mutated(self):
        payload = {"plan_celular": "No"}
        _apply_blind_credit_defaults(payload, None)
        assert payload == {"plan_celular": "No"}, "El helper mutó el dict original."

    def test_injection_failure_returns_original_and_logs_exception(self, caplog):
        """Zero-Silent-Failures: si la conversión de args explota, se loguea
        logger.exception y se devuelven los args originales (fail-open)."""
        class ExplodingArgs:
            def __bool__(self):
                return True

            def keys(self):
                raise RuntimeError("boom-args")

        broken = ExplodingArgs()
        with caplog.at_level(logging.ERROR, logger="app.services.ai_brain"):
            result = _apply_blind_credit_defaults(broken, None)
        assert result is broken, "Fail-open: debió devolver los args originales."
        assert "Fallo inyectando defaults de Crédito Ciego" in caplog.text


# ============================================================================
# 2. INTEGRATION — dispatcher calculate_credit_score con inyección
# ============================================================================

def _make_fc_response(tool_args: dict):
    mock_response = MagicMock()
    mock_part = MagicMock()
    mock_part.text = None
    fc = MagicMock()
    fc.name = "calculate_credit_score"
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


def _build_cerebro_with_motor(script: list):
    """CerebroIA con motor financiero legacy (evaluate_profile) y chat scriptado."""
    from app.services.ai_brain import CerebroIA

    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._catalog_service = MagicMock()
    cerebro._catalog_service.get_catalog_aliases.return_value = {}
    cerebro._catalog_service.search_items.return_value = [
        {
            "name": "TVS Raider 125",
            "price": "$ 6.500.000",
            "raw_price": 6500000.0,
            "cc": 125,
            "category": "Sport",
        }
    ]

    motor = MagicMock()
    motor.evaluate_profile.return_value = {
        "score": 800,
        "strategy": "Banco",
        "entity": "Banco de Bogotá",
        "link_url": "https://banco.link",
        "requires_aval": False,
    }
    motor.calculate_payment.return_value = {"cuota_mensual": 250000}
    cerebro.motor_financiero = motor

    responses = list(script)

    async def _send(*args, **kwargs):
        return responses.pop(0)

    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock(side_effect=_send)
    cerebro.client.aio.chats.create.return_value = mock_chat
    return cerebro, motor


PROSPECT_WITH_CONSENT = {
    "exists": True,
    "nombre": "Carlos",
    "ciudad": "Bogotá",
    "forma_pago": "crédito",
    "habeas_data_accepted": True,
    "moto_interest": "TVS Raider 125",
}


@pytest.mark.asyncio
async def test_dispatcher_empty_payload_reaches_motor_with_all_defaults():
    """GIVEN el LLM invoca calculate_credit_score con payload VACÍO,
    WHEN el handler inyecta los defaults de Crédito Ciego,
    THEN el motor financiero recibe los 7 valores por defecto del ticket."""
    cerebro, motor = _build_cerebro_with_motor([
        _make_fc_response({}),
        _make_text_response("Tu crédito fue pre-aprobado. ¿Te confirmo la cuota?"),
    ])

    result = await cerebro.pensar_respuesta(
        texto="quiero solicitar mi crédito",
        prospect_data=PROSPECT_WITH_CONSENT.copy(),
        history=[],
    )

    assert result == "Tu crédito fue pre-aprobado. ¿Te confirmo la cuota?"
    motor.evaluate_profile.assert_called_once()
    kwargs = motor.evaluate_profile.call_args.kwargs
    assert kwargs["ocupacion_y_contrato"] == "Empleado"
    assert kwargs["ingresos_demostrables"] == "SMLV"
    assert kwargs["historial_datacredito"] == "Sin experiencia"
    assert kwargs["plan_celular"] == "Sí"
    assert kwargs["entidad"] == "Brilla de Gases"
    assert kwargs["reportes"] == "No"


@pytest.mark.asyncio
async def test_dispatcher_preserves_llm_values_and_fills_only_missing():
    """GIVEN el LLM provee ocupación real pero omite el resto,
    WHEN el handler inyecta defaults,
    THEN el valor del LLM se preserva y solo los omitidos se completan."""
    cerebro, motor = _build_cerebro_with_motor([
        _make_fc_response({"ocupacion_y_contrato": "Independiente"}),
        _make_text_response("Listo, simulación lista. ¿Avanzamos con el estudio?"),
    ])

    result = await cerebro.pensar_respuesta(
        texto="soy independiente, quiero mi crédito",
        prospect_data=PROSPECT_WITH_CONSENT.copy(),
        history=[],
    )

    assert result == "Listo, simulación lista. ¿Avanzamos con el estudio?"
    kwargs = motor.evaluate_profile.call_args.kwargs
    assert kwargs["ocupacion_y_contrato"] == "Independiente", "El valor del LLM fue pisado."
    assert kwargs["ingresos_demostrables"] == "SMLV"
    assert kwargs["historial_datacredito"] == "Sin experiencia"
    assert kwargs["entidad"] == "Brilla de Gases"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
