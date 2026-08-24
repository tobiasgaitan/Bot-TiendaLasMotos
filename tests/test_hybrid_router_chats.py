"""Tests de la superficie async de chat del HybridLLMRouter — BOT-BUILD-HYBRID-CHATS-FIX-096.

Certifica:
  - aio.chats.create expone send_message awaitable (+ alias send_message_async).
  - El extractor de texto maneja str y types.Part sueltos.
  - route_by_context funciona sobre el full_prompt string de ai_brain.
  - Ruteo MATRIZ completo (8 turnos) vía chat.send_message.
  - Backstop de tool prematuro en ruta async.
  - Historial completo viaja a DeepSeek en turnos siguientes.
  - Logs ZSF con provider/reason/captured_count/siguiente/fase.

COND-1: socket guard autouse (la suite no usa red).
"""
from __future__ import annotations

import inspect
import logging
import socket
from typing import Any

import pytest

from app.services.hybrid_llm_router import (
    CANONICAL_QUESTION,
    HybridAioChat,
    HybridLLMRouter,
    _ResponseShim,
    _extract_text_from_contents,
    route_by_context,
)
from scripts.china_eval.fixtures.p3_ext_turns import (
    TURNS,
    build_user_turn_message,
)
from tests.test_hybrid_router_e2e_synth import (
    _happy_path_scripts,
    _initial_prospect,
    _make_credit_score_shim,
    _make_router,
)


# ---------------------------------------------------------------------------
# COND-1: socket guard autouse
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _block_sockets():
    """Bloquea cualquier intento de socket de red real durante los tests."""
    original = socket.socket

    def _guard(*args, **kwargs):
        if args and args[0] in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("SOCKET_BLOCKED: la suite sintetica no debe usar red")
        return original(*args, **kwargs)

    socket.socket = _guard
    yield
    socket.socket = original


class TestHybridAioChatSurface:
    def test_aio_chats_create_exposes_send_message(self) -> None:
        deepseek_script, gemini_script = _happy_path_scripts()
        router = _make_router(deepseek_script, gemini_script)

        chat = router.aio.chats.create(model="any-model")

        assert isinstance(chat, HybridAioChat)
        assert inspect.iscoroutinefunction(chat.send_message)
        assert inspect.iscoroutinefunction(chat.send_message_async)

    def test_extract_text_and_route_on_string_contents(self) -> None:
        text = build_user_turn_message(_initial_prospect(), "Hola")

        extracted = _extract_text_from_contents(text)
        assert "<fase_actual>PHASE_3_CREDIT_PROFILING</fase_actual>" in extracted
        assert "<estado_perfilamiento>" in extracted

        decision = route_by_context(text, config=None)
        assert decision.provider == "deepseek"
        assert decision.reason == "turno_1_profiling"
        assert decision.fase == "PHASE_3_CREDIT_PROFILING"


class TestHybridAioChatRouting:
    @pytest.mark.asyncio
    async def test_matrix_sequence_by_chat(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, gemini_script = _happy_path_scripts()
        router = _make_router(deepseek_script, gemini_script)
        chat = router.aio.chats.create(model="any-model")

        prospect = dict(_initial_prospect())
        shims: list[_ResponseShim] = []
        for turn in TURNS:
            msg = build_user_turn_message(prospect, turn["user_text"])
            shim = await chat.send_message(msg)
            shims.append(shim)
            prospect.update(turn.get("captures", {}))

        assert router._deepseek.index == 6
        assert router._dual.aio.models.index == 2

        route_records = [r for r in caplog.records if "[HYBRID ROUTE ASYNC]" in r.getMessage()]
        assert len(route_records) == 8
        providers = [r.args[0] for r in route_records]
        assert providers == ["deepseek"] * 6 + ["gemini"] * 2

    @pytest.mark.asyncio
    async def test_backstop_premature_tool_by_chat(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, _ = _happy_path_scripts()
        # Turno 3 (Reportes Datacredito) devuelve calculate_credit_score prematuro.
        deepseek_script[2] = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {"name": "calculate_credit_score", "arguments": "{}"},
                            }
                        ],
                    },
                    "index": 0,
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "model": "deepseek/deepseek-v4-flash-0731",
        }
        gemini_script = [
            _ResponseShim(
                text=CANONICAL_QUESTION["Reportes Datacrédito"],
                parts=[{"type": "text", "text": CANONICAL_QUESTION["Reportes Datacrédito"]}],
            ),
            _ResponseShim(
                text=CANONICAL_QUESTION["Plan celular"],
                parts=[{"type": "text", "text": CANONICAL_QUESTION["Plan celular"]}],
            ),
            _make_credit_score_shim(),
        ]
        router = _make_router(deepseek_script, gemini_script)
        chat = router.aio.chats.create(model="any-model")

        prospect = dict(_initial_prospect())
        shims: list[_ResponseShim] = []
        for turn in TURNS:
            msg = build_user_turn_message(prospect, turn["user_text"])
            shim = await chat.send_message(msg)
            shims.append(shim)
            prospect.update(turn.get("captures", {}))

        assert any("tool_prematuro interceptado" in r.getMessage() for r in caplog.records)
        # El turno interceptado se resuelve con pregunta canonica (sin tool-call).
        intercepted_shim = shims[2]
        assert intercepted_shim._tool_calls == []
        assert CANONICAL_QUESTION["Reportes Datacrédito"] in (intercepted_shim.text or "")

    @pytest.mark.asyncio
    async def test_history_carried_to_deepseek(self) -> None:
        deepseek_script = [
            {
                "choices": [
                    {"message": {"content": "Pregunta A"}, "index": 0, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
                "model": "deepseek/deepseek-v4-flash-0731",
            },
            {
                "choices": [
                    {"message": {"content": "Pregunta B"}, "index": 0, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
                "model": "deepseek/deepseek-v4-flash-0731",
            },
        ]
        router = _make_router(deepseek_script, [])
        chat = router.aio.chats.create(model="any-model")

        msg1 = build_user_turn_message(_initial_prospect(), "Hola")
        await chat.send_message(msg1)

        prospect2 = dict(_initial_prospect())
        prospect2.update({"ocupacion": "Empleado"})
        msg2 = build_user_turn_message(prospect2, "Soy empleado")
        await chat.send_message(msg2)

        calls = router._deepseek.calls
        assert len(calls) == 2
        second_messages = calls[1]["messages"]
        assert any(
            m.get("role") == "assistant" and m.get("content") == "Pregunta A"
            for m in second_messages
        )

    @pytest.mark.asyncio
    async def test_zsf_log_fields_present(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, gemini_script = _happy_path_scripts()
        router = _make_router(deepseek_script, gemini_script)
        chat = router.aio.chats.create(model="any-model")

        msg = build_user_turn_message(_initial_prospect(), "Hola")
        await chat.send_message(msg)

        record = next(r for r in caplog.records if "[HYBRID ROUTE ASYNC]" in r.getMessage())
        # args: provider, reason, captured_count, siguiente, fase
        assert record.args[0] == "deepseek"
        assert record.args[1] == "turno_1_profiling"
        assert record.args[2] == 0
        assert record.args[3] == "Ocupación"
        assert record.args[4] == "PHASE_3_CREDIT_PROFILING"
