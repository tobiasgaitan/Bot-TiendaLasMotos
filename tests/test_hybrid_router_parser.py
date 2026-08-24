"""Regresión para BOT-BUILD-LLMROUTER-FIX-092.

Pines:
- Parser usa último bloque <estado_perfilamiento> (no acumula histórico).
- Secuencia captured_count exacta [0, 2, 3, 4, 5, 6, 7, 8] en P3-EXT.
- Ruteo: DeepSeek×6, Gemini(turno 7 frontera), Gemini(turno 8 cierre).
- Backstop: tool-call prematuro y desviación de orden detectados.
- Red determinista final: pregunta canónica sintetizada.
"""
from __future__ import annotations

import pytest

from app.services.hybrid_llm_router import (
    CANONICAL_QUESTION,
    _ResponseShim,
    _build_deterministic_shim,
    _extract_last_checklist,
    _parse_profiling_state,
    _response_to_shim,
    _should_backstop,
    route_by_context,
)


def _make_checklist(captured: set[str], siguiente: str) -> str:
    fields = [
        ("Ocupación", "Ocupación" in captured),
        ("Contrato", "Contrato" in captured),
        ("Ingresos", "Ingresos" in captured),
        ("Reportes Datacrédito", "Reportes Datacrédito" in captured),
        ("Gastos mensuales", "Gastos mensuales" in captured),
        ("Gas natural (Brilla)", "Gas natural (Brilla)" in captured),
        ("Vivienda", "Vivienda" in captured),
        ("Plan celular", "Plan celular" in captured),
    ]
    lines = ['<estado_perfilamiento>']
    for label, ok in fields:
        if ok:
            lines.append(f'  <item nombre="{label}" estado="CAPTURADO">valor</item>')
        else:
            lines.append(f'  <item nombre="{label}" estado="PENDIENTE"/>')
    lines.append(f"  <siguiente_pendiente>{siguiente}</siguiente_pendiente>")
    lines.append("</estado_perfilamiento>")
    return "\n".join(lines)


def _make_content(checklist: str) -> list[dict]:
    return [{"role": "user", "parts": [{"text": f"<fase_actual>PHASE_3_CREDIT_PROFILING</fase_actual>\n{checklist}\nSí."}]}]


class TestParserLastBlock:
    def test_extract_last_checklist_ignores_older_blocks(self) -> None:
        old = _make_checklist({"Ocupación"}, "Contrato")
        new = _make_checklist({"Ocupación", "Contrato", "Ingresos"}, "Reportes Datacrédito")
        text = f"{old}\n{new}"
        latest = _extract_last_checklist(text)
        assert latest == new
        state = _parse_profiling_state(_make_content(f"{old}\n{new}"))
        assert state.captured_count == 3
        assert state.siguiente_pendiente == "Reportes Datacrédito"

    def test_cumulative_history_does_not_inflate_count(self) -> None:
        # Simula los 8 bloques acumulados en el historial del eval.
        expected = [
            (set(), "Ocupación", 0),
            ({"Ocupación", "Contrato"}, "Ingresos", 2),
            ({"Ocupación", "Contrato", "Ingresos"}, "Reportes Datacrédito", 3),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito"}, "Gastos mensuales", 4),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito", "Gastos mensuales"}, "Gas natural (Brilla)", 5),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito", "Gastos mensuales", "Gas natural (Brilla)"}, "Vivienda", 6),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito", "Gastos mensuales", "Gas natural (Brilla)", "Vivienda"}, "Plan celular", 7),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito", "Gastos mensuales", "Gas natural (Brilla)", "Vivienda", "Plan celular"}, "COMPLETO", 8),
        ]
        blocks = [_make_checklist(captured, siguiente) for captured, siguiente, _ in expected]
        full_history = "\n".join(blocks)

        for i, (captured, exp_siguiente, exp_count) in enumerate(expected):
            current_block = _make_checklist(captured, exp_siguiente)
            text = f"<fase_actual>PHASE_3_CREDIT_PROFILING</fase_actual>\n{full_history}\n{current_block}"
            state = _parse_profiling_state(_make_content(text))
            assert state.captured_count == exp_count, f"turno {i+1}: count={state.captured_count} != {exp_count}"
            assert state.siguiente_pendiente == exp_siguiente, f"turno {i+1}: siguiente={state.siguiente_pendiente} != {exp_siguiente}"


class TestRoutingSequence:
    def test_p3_ext_routing_sequence(self) -> None:
        fixtures = [
            (set(), "Ocupación", 0, "deepseek", "turno_1_profiling"),
            ({"Ocupación", "Contrato"}, "Ingresos", 2, "deepseek", "turno_3_profiling"),
            ({"Ocupación", "Contrato", "Ingresos"}, "Reportes Datacrédito", 3, "deepseek", "turno_4_profiling"),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito"}, "Gastos mensuales", 4, "deepseek", "turno_5_profiling"),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito", "Gastos mensuales"}, "Gas natural (Brilla)", 5, "deepseek", "turno_6_profiling"),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito", "Gastos mensuales", "Gas natural (Brilla)"}, "Vivienda", 6, "deepseek", "turno_7_profiling"),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito", "Gastos mensuales", "Gas natural (Brilla)", "Vivienda"}, "Plan celular", 7, "gemini", "frontera_turno_7_matriz"),
            ({"Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito", "Gastos mensuales", "Gas natural (Brilla)", "Vivienda", "Plan celular"}, "COMPLETO", 8, "gemini", "cierre_fase_completo"),
        ]
        for i, (captured, siguiente, exp_count, exp_provider, exp_reason) in enumerate(fixtures):
            checklist = _make_checklist(captured, siguiente)
            contents = _make_content(checklist)
            decision = route_by_context(contents, config=None)
            assert decision.provider == exp_provider, f"turno {i+1}: provider={decision.provider}"
            assert decision.reason == exp_reason, f"turno {i+1}: reason={decision.reason}"
            assert decision.captured_count == exp_count, f"turno {i+1}: count={decision.captured_count}"


class TestBackstopDetection:
    def test_tool_prematuro_detected(self) -> None:
        decision = route_by_context(
            _make_content(_make_checklist({"Ocupación", "Contrato"}, "Ingresos")),
            config=None,
        )
        shim = _ResponseShim(
            text="Entendido.",
            parts=[{"type": "text", "text": "Entendido."}],
            tool_calls=[{"name": "calculate_credit_score", "args": {"entidad": "Brilla"}}],
        )
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is True
        assert reason == "backstop_tool_prematuro"

    def test_tool_legitimo_en_cierre_no_backstop(self) -> None:
        decision = route_by_context(
            _make_content(_make_checklist({"Ocupación", "Contrato", "Ingresos",
                                            "Reportes Datacrédito", "Gastos mensuales",
                                            "Gas natural (Brilla)", "Vivienda", "Plan celular"}, "COMPLETO")),
            config=None,
        )
        shim = _ResponseShim(
            text=None,
            parts=[{"type": "function_call", "_function_call": {"name": "calculate_credit_score", "args": {}}}],
            tool_calls=[{"name": "calculate_credit_score", "args": {}}],
        )
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is False

    def test_desviacion_orden_detected(self) -> None:
        decision = route_by_context(
            _make_content(_make_checklist({"Ocupación", "Contrato"}, "Ingresos")),
            config=None,
        )
        shim = _ResponseShim(
            text="¿Cuál es la cuota inicial?",
            parts=[{"type": "text", "text": "¿Cuál es la cuota inicial?"}],
            tool_calls=[],
        )
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is True
        assert reason == "backstop_desviacion_orden"

    def test_orden_correcto_no_backstop(self) -> None:
        decision = route_by_context(
            _make_content(_make_checklist({"Ocupación", "Contrato"}, "Ingresos")),
            config=None,
        )
        shim = _ResponseShim(
            text="¿Cuáles son tus ingresos mensuales?",
            parts=[{"type": "text", "text": "¿Cuáles son tus ingresos mensuales?"}],
            tool_calls=[],
        )
        backstop, reason = _should_backstop(decision, shim)
        assert backstop is False


class TestDeterministicNet:
    def test_deterministic_shim_strips_tools_and_injects_question(self) -> None:
        shim = _ResponseShim(
            text="",
            parts=[{"type": "function_call", "_function_call": {"name": "calculate_credit_score", "args": {}}}],
            tool_calls=[{"name": "calculate_credit_score", "args": {}}],
        )
        result = _build_deterministic_shim(shim, "Plan celular")
        assert result._tool_calls == []
        assert result.text == CANONICAL_QUESTION["Plan celular"]
        assert "¿Tienes plan celular a tu nombre?" in result.text

    def test_response_to_shim_preserves_text(self) -> None:
        shim = _ResponseShim(text="Hola", parts=[{"type": "text", "text": "Hola"}], tool_calls=[])
        assert _response_to_shim(shim) is shim


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
