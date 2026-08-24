"""Suite sintética E2E del HybridLLMRouter — BOT-BUILD-HYBRID-SYNTH-094.

Arnés determinista sin red ni credenciales que certifica:
  - Ruteo contextual R1-R7 (happy path MATRIZ 8 turnos + cierre).
  - Backstop doble (tool prematuro, desviación de orden, red determinista).
  - Fail-closed ante excepciones de ruteo.
  - Replay byte-idéntico de la traza live ce-272a446742f54cf0.
  - Logging ZSF sin PII.

COND-1: socket guard autouse para garantizar 0 llamadas de red.
"""
from __future__ import annotations

import json
import logging
import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from app.services.hybrid_llm_router import (
    CANONICAL_QUESTION,
    HybridLLMRouter,
    _ResponseShim,
)
from app.services.llm_client_service import DualProviderClient
from scripts.china_eval.fixtures.p3_ext_turns import (
    TURNS,
    build_user_turn_message,
    evaluate_profiling_matrix,
)


# ---------------------------------------------------------------------------
# COND-1: socket guard autouse
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _block_sockets():
    """Bloquea cualquier intento de socket real durante los tests."""
    original = socket.socket

    def _guard(*args, **kwargs):
        # COND-1: bloquear solo sockets de red reales; AF_UNIX lo usa asyncio.
        if args and args[0] in (socket.AF_INET, socket.AF_INET6):
            raise RuntimeError("SOCKET_BLOCKED: la suite sintética no debe usar red")
        return original(*args, **kwargs)

    socket.socket = _guard
    yield
    socket.socket = original


# ---------------------------------------------------------------------------
# Helpers de transporte mockeado
# ---------------------------------------------------------------------------
def _contents(text: str) -> list[dict[str, Any]]:
    """Formato de contents que _extract_text_from_contents parsea correctamente."""
    return [{"role": "user", "parts": [{"text": text}]}]


class ScriptedDeepSeekTransport:
    """Reemplaza DeepSeekOpenRouterClient; devuelve respuestas OpenAI-format en cola."""

    def __init__(self, script: list[dict[str, Any]]):
        self.script = script
        self.index = 0
        self.calls: list[dict[str, Any]] = []

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        if self.index >= len(self.script):
            raise IndexError(f"DeepSeek script exhausted after {self.index} calls")
        resp = self.script[self.index]
        self.index += 1
        self.calls.append(
            {
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
                "temperature": temperature,
                "response": resp,
            }
        )
        return resp

    async def achat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        return self.chat_completion(messages, tools, tool_choice, temperature)


class ScriptedGeminiModels:
    """Reemplaza dual.models; devuelve _ResponseShim en cola."""

    def __init__(self, script: list[_ResponseShim]):
        self.script = script
        self.index = 0
        self.calls: list[tuple[Any, Any, Any]] = []

    def generate_content(self, model: str, contents: Any, config: Any = None) -> _ResponseShim:
        if self.index >= len(self.script):
            raise IndexError(f"Gemini script exhausted after {self.index} calls")
        resp = self.script[self.index]
        self.index += 1
        self.calls.append((model, contents, config))
        return resp


class ScriptedGeminiAioModels:
    """Reemplaza dual.aio.models para tests async."""

    def __init__(self, script: list[_ResponseShim]):
        self.script = script
        self.index = 0
        self.calls: list[tuple[Any, Any, Any]] = []

    async def generate_content(self, model: str, contents: Any, config: Any = None) -> _ResponseShim:
        if self.index >= len(self.script):
            raise IndexError(f"Gemini async script exhausted after {self.index} calls")
        resp = self.script[self.index]
        self.index += 1
        self.calls.append((model, contents, config))
        return resp


def _make_router(deepseek_script: list[dict[str, Any]], gemini_script: list[_ResponseShim]) -> HybridLLMRouter:
    dual = DualProviderClient(gemini_sync=Mock(), role="agentic")
    router = HybridLLMRouter(
        dual_client=dual,
        deepseek_client=ScriptedDeepSeekTransport(deepseek_script),
        role="agentic",
    )
    router._dual.models = ScriptedGeminiModels(gemini_script)
    router._dual.aio.models = ScriptedGeminiAioModels(gemini_script)
    return router


def _initial_prospect() -> dict[str, Any]:
    return {
        "nombre": "Carlos",
        "ciudad": "Santa Marta",
        "forma_pago": "Crédito",
        "habeas_data_accepted": True,
        "habeas_data_accepted_sent": True,
        "moto_interest": "Bajaj Boxer 150",
    }


def _matrix_fields() -> list[str]:
    return [
        "Ocupación",
        "Ingresos",
        "Reportes Datacrédito",
        "Gastos mensuales",
        "Gas natural (Brilla)",
        "Vivienda",
    ]


def _happy_path_scripts() -> tuple[list[dict[str, Any]], list[_ResponseShim]]:
    deepseek_script: list[dict[str, Any]] = []
    for field in _matrix_fields():
        deepseek_script.append(
            {
                "choices": [
                    {
                        "message": {"content": CANONICAL_QUESTION[field]},
                        "index": 0,
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
                "model": "deepseek/deepseek-v4-flash-0731",
            }
        )

    gemini_script: list[_ResponseShim] = [
        _ResponseShim(
            text=CANONICAL_QUESTION["Plan celular"],
            parts=[{"type": "text", "text": CANONICAL_QUESTION["Plan celular"]}],
        ),
        _make_credit_score_shim(),
    ]
    return deepseek_script, gemini_script


def _make_credit_score_shim() -> _ResponseShim:
    args = {
        "entidad": "Brilla de Gases",
        "ocupacion_y_contrato": "Empleado",
        "ingresos_demostrables": "2 SMLV",
        "historial_datacredito": "Bueno",
        "gastos": "1 SMLV",
        "gas_natural": "Sí",
        "vivienda": "Propia",
        "plan_celular": "Sí",
        "reportes": "No",
    }
    return _ResponseShim(
        text=None,
        parts=[
            {
                "type": "function_call",
                "_function_call": {"name": "calculate_credit_score", "args": args},
            }
        ],
        tool_calls=[{"name": "calculate_credit_score", "args": args}],
    )


def _drive_matrix_loop(router: HybridLLMRouter) -> list[_ResponseShim]:
    prospect = _initial_prospect()
    shims: list[_ResponseShim] = []
    for turn in TURNS:
        msg = build_user_turn_message(prospect, turn["user_text"])
        shim = router.models.generate_content(model="any-model", contents=_contents(msg), config=None)
        shims.append(shim)
        prospect.update(turn.get("captures", {}))
    return shims


def _hybrid_route_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "[HYBRID ROUTE]" in r.getMessage()]


def _hybrid_backstop_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if "[HYBRID BACKSTOP]" in r.getMessage()]


# ---------------------------------------------------------------------------
# E — Happy path E2E
# ---------------------------------------------------------------------------
class TestHappyPath:
    def test_sync_routing_sequence_and_cierre(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, gemini_script = _happy_path_scripts()
        router = _make_router(deepseek_script, gemini_script)

        shims = _drive_matrix_loop(router)

        # Transporte: 6 llamadas DeepSeek (R3) + 2 Gemini (R2 frontera + R1 cierre)
        assert router._deepseek.index == 6
        assert router._dual.models.index == 2

        # Secuencia de ruteo
        route_records = _hybrid_route_records(caplog)
        assert len(route_records) == 8
        providers = [r.args[0] for r in route_records]
        reasons = [r.args[1] for r in route_records]
        captured_counts = [r.args[2] for r in route_records]

        assert providers == ["deepseek"] * 6 + ["gemini"] * 2
        # El campo Ocupación captura también Contrato, por eso el turno 2 inicia con 2 CAPTURADO.
        assert reasons[:6] == [
            "turno_1_profiling",
            "turno_3_profiling",
            "turno_4_profiling",
            "turno_5_profiling",
            "turno_6_profiling",
            "turno_7_profiling",
        ]
        assert reasons[6] == "frontera_turno_7_matriz"
        assert reasons[7] == "cierre_fase_completo"
        assert captured_counts == [0, 2, 3, 4, 5, 6, 7, 8]

        # Cero backstops en happy path
        assert _hybrid_backstop_records(caplog) == []

        # Una sola pregunta por turno 1-7; turno 8 invoca calculate_credit_score
        for i, shim in enumerate(shims[:-1], start=1):
            assert shim.text is not None
            assert shim.text.count("?") == 1, f"turno {i} no tiene exactamente una pregunta"
            assert shim._tool_calls == []

        final_shim = shims[-1]
        assert final_shim.text is None or final_shim.text.strip() == ""
        assert len(final_shim._tool_calls) == 1
        assert final_shim._tool_calls[0]["name"] == "calculate_credit_score"
        args = final_shim._tool_calls[0]["args"]
        required_keys = {
            "entidad",
            "ocupacion_y_contrato",
            "ingresos_demostrables",
            "historial_datacredito",
            "gastos",
            "gas_natural",
            "vivienda",
            "plan_celular",
        }
        assert required_keys.issubset(set(args.keys()))

    @pytest.mark.asyncio
    async def test_async_routing_sequence_and_cierre(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, gemini_script = _happy_path_scripts()
        router = _make_router(deepseek_script, gemini_script)

        prospect = _initial_prospect()
        shims: list[_ResponseShim] = []
        for turn in TURNS:
            msg = build_user_turn_message(prospect, turn["user_text"])
            shim = await router.aio.models.generate_content(
                model="any-model", contents=_contents(msg), config=None
            )
            shims.append(shim)
            prospect.update(turn.get("captures", {}))

        assert router._deepseek.index == 6
        assert router._dual.aio.models.index == 2

        route_records = [r for r in caplog.records if "[HYBRID ROUTE ASYNC]" in r.getMessage()]
        assert len(route_records) == 8
        assert [r.args[0] for r in route_records] == ["deepseek"] * 6 + ["gemini"] * 2

        assert shims[-1]._tool_calls[0]["name"] == "calculate_credit_score"


# ---------------------------------------------------------------------------
# F — Fault injection
# ---------------------------------------------------------------------------
class TestFaultInjection:
    def test_tool_prematuro_sync_interceptado_y_reenrutado(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, _ = _happy_path_scripts()
        # Turno 3 (índice 2, campo Reportes Datacrédito) emite calculate_credit_score prematuro.
        deepseek_script[2] = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "calculate_credit_score",
                                    "arguments": "{}",
                                },
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
            # Re-enrute del turno 3: Gemini responde correctamente.
            _ResponseShim(
                text=CANONICAL_QUESTION["Reportes Datacrédito"],
                parts=[{"type": "text", "text": CANONICAL_QUESTION["Reportes Datacrédito"]}],
            ),
            # Turnos 7 y 8 normales.
            _ResponseShim(
                text=CANONICAL_QUESTION["Plan celular"],
                parts=[{"type": "text", "text": CANONICAL_QUESTION["Plan celular"]}],
            ),
            _make_credit_score_shim(),
        ]

        router = _make_router(deepseek_script, gemini_script)
        shims = _drive_matrix_loop(router)

        # 6 DeepSeek (incluido el prematuro) + 3 Gemini (re-enrute + frontera + cierre)
        assert router._deepseek.index == 6
        assert router._dual.models.index == 3

        backstop_records = _hybrid_backstop_records(caplog)
        assert len([r for r in backstop_records if "tool_prematuro interceptado" in r.getMessage()]) == 1
        assert any("fallback=gemini" in r.getMessage() for r in caplog.records)

        # Turno 3 final no tiene tool_calls
        assert shims[2]._tool_calls == []
        assert CANONICAL_QUESTION["Reportes Datacrédito"] in shims[2].text

        # Cierre sigue siendo correcto
        assert shims[-1]._tool_calls[0]["name"] == "calculate_credit_score"

    @pytest.mark.asyncio
    async def test_tool_prematuro_async_interceptado_y_reenrutado(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, _ = _happy_path_scripts()
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

        prospect = _initial_prospect()
        shims: list[_ResponseShim] = []
        for turn in TURNS:
            msg = build_user_turn_message(prospect, turn["user_text"])
            shim = await router.aio.models.generate_content(
                model="any-model", contents=_contents(msg), config=None
            )
            shims.append(shim)
            prospect.update(turn.get("captures", {}))

        assert router._deepseek.index == 6
        assert router._dual.aio.models.index == 3
        assert any("tool_prematuro interceptado" in r.getMessage() for r in caplog.records)
        assert shims[2]._tool_calls == []

    def test_doble_fallo_tool_prematuro_red_determinista(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, _ = _happy_path_scripts()
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
        # Gemini también falla: responde con tool prematuro y texto vacío.
        gemini_script = [
            _ResponseShim(
                text=None,
                parts=[
                    {
                        "type": "function_call",
                        "_function_call": {"name": "calculate_credit_score", "args": {}},
                    }
                ],
                tool_calls=[{"name": "calculate_credit_score", "args": {}}],
            ),
            _ResponseShim(
                text=CANONICAL_QUESTION["Plan celular"],
                parts=[{"type": "text", "text": CANONICAL_QUESTION["Plan celular"]}],
            ),
            _make_credit_score_shim(),
        ]

        router = _make_router(deepseek_script, gemini_script)
        shims = _drive_matrix_loop(router)

        # Solo 1 re-enrute permitido; luego red determinista.
        assert router._dual.models.index == 3
        assert shims[2]._tool_calls == []
        assert shims[2].text == CANONICAL_QUESTION["Reportes Datacrédito"]

    def test_desviacion_orden_reenrutada_a_gemini(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, _ = _happy_path_scripts()
        # Turno 5 (índice 4, campo Gas natural): pregunta desviada.
        deepseek_script[4] = {
            "choices": [
                {
                    "message": {"content": "¿Cuál es la cuota inicial?"},
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "model": "deepseek/deepseek-v4-flash-0731",
        }
        gemini_script = [
            # Re-enrute turno 5: pregunta canónica del campo correcto.
            _ResponseShim(
                text=CANONICAL_QUESTION["Gas natural (Brilla)"],
                parts=[{"type": "text", "text": CANONICAL_QUESTION["Gas natural (Brilla)"]}],
            ),
            # Turnos 7 y 8.
            _ResponseShim(
                text=CANONICAL_QUESTION["Plan celular"],
                parts=[{"type": "text", "text": CANONICAL_QUESTION["Plan celular"]}],
            ),
            _make_credit_score_shim(),
        ]

        router = _make_router(deepseek_script, gemini_script)
        shims = _drive_matrix_loop(router)

        assert any(
            "backstop_desviacion_orden" in r.getMessage() for r in _hybrid_backstop_records(caplog)
        )
        assert router._dual.models.index == 3
        assert "gas natural" in (shims[4].text or "").lower()
        assert shims[4]._tool_calls == []

    def test_excepcion_parser_falla_cerrada_a_gemini(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        import app.services.hybrid_llm_router as hybrid_mod

        original_parse = hybrid_mod._parse_profiling_state

        def _broken_parse(contents: Any):
            raise RuntimeError("parser forced failure")

        gemini_script = [
            _ResponseShim(
                text="Entendido.",
                parts=[{"type": "text", "text": "Entendido."}],
            ),
        ]

        try:
            hybrid_mod._parse_profiling_state = _broken_parse
            router = _make_router([], gemini_script)
            shim = router.models.generate_content(
                model="any-model",
                contents=_contents("texto irrelevante"),
                config=None,
            )
        finally:
            hybrid_mod._parse_profiling_state = original_parse

        assert shim.text == "Entendido."
        assert any(
            "route_fallback_gemini" in (r.args[1] if r.args else "")
            for r in _hybrid_route_records(caplog)
        )
        assert any("Error en route_by_context" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# R — Replay determinista de traza live 2026-08-24
# ---------------------------------------------------------------------------
class TestReplay:
    def test_replay_p3ext_trace_ce_272a446742f54cf0(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        fixture_path = Path(__file__).parent / "fixtures" / "hybrid_replay_p3ext_20260824.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        assert fixture["trace_id"] == "ce-272a446742f54cf0"

        deepseek_script: list[dict[str, Any]] = []
        gemini_script: list[_ResponseShim] = []
        expected_providers: list[str] = []

        for turn in fixture["turns"]:
            rows, next_pending = evaluate_profiling_matrix(turn["prospect_data_snapshot"])
            captured_count = sum(1 for _, v in rows if v)
            if captured_count >= 7 or next_pending is None:
                provider = "gemini"
            else:
                provider = "deepseek"
            expected_providers.append(provider)

            content = turn["content"]
            tool_calls = turn.get("tool_calls", [])
            # Para reproducir el backstop live del turno 7, alimentamos a Gemini
            # con el tool prematuro subyacente (texto vacío) para que la red
            # determinista inyecte la pregunta canónica igual que en producción.
            if provider == "gemini" and not tool_calls and content == CANONICAL_QUESTION["Plan celular"]:
                gemini_script.append(
                    _ResponseShim(
                        text=None,
                        parts=[
                            {
                                "type": "function_call",
                                "_function_call": {"name": "calculate_credit_score", "args": {}},
                            }
                        ],
                        tool_calls=[{"name": "calculate_credit_score", "args": {}}],
                    )
                )
            elif provider == "gemini" and tool_calls:
                parts = []
                stored = []
                for tc in tool_calls:
                    args = json.loads(tc.get("arguments", "{}"))
                    parts.append(
                        {
                            "type": "function_call",
                            "_function_call": {"name": tc["name"], "args": args},
                        }
                    )
                    stored.append({"name": tc["name"], "args": args})
                gemini_script.append(_ResponseShim(text=None, parts=parts, tool_calls=stored))
            elif provider == "gemini":
                gemini_script.append(
                    _ResponseShim(text=content, parts=[{"type": "text", "text": content}])
                )
            else:
                deepseek_script.append(
                    {
                        "choices": [
                            {
                                "message": {"content": content},
                                "index": 0,
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
                        "model": "deepseek/deepseek-v4-flash-0731",
                    }
                )

        router = _make_router(deepseek_script, gemini_script)
        prospect: dict[str, Any] = _initial_prospect()
        final_shims: list[_ResponseShim] = []
        for idx, turn in enumerate(fixture["turns"]):
            msg = build_user_turn_message(prospect, turn["user_text"])
            final_shims.append(
                router.models.generate_content(model="any-model", contents=_contents(msg), config=None)
            )
            # Avanzamos la matriz con las capturas canónicas de P3-EXT (igual que happy path).
            prospect.update(TURNS[idx].get("captures", {}))

        route_records = _hybrid_route_records(caplog)
        actual_providers = [r.args[0] for r in route_records]
        assert actual_providers == expected_providers
        assert expected_providers == ["deepseek"] * 6 + ["gemini"] * 2

        # Turno 7: backstop live reproducido, salida canónica byte-idéntica.
        assert final_shims[6].text == CANONICAL_QUESTION["Plan celular"]
        assert final_shims[6]._tool_calls == []

        # Turno 8: cierre con calculate_credit_score.
        assert final_shims[7]._tool_calls[0]["name"] == "calculate_credit_score"
        recorded_args = json.loads(fixture["turns"][7]["tool_calls"][0]["arguments"])
        assert final_shims[7]._tool_calls[0]["args"] == recorded_args


# ---------------------------------------------------------------------------
# L — Logging ZSF
# ---------------------------------------------------------------------------
class TestLoggingZsf:
    def test_hybrid_route_fields_present(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, gemini_script = _happy_path_scripts()
        router = _make_router(deepseek_script, gemini_script)
        _drive_matrix_loop(router)

        for r in _hybrid_route_records(caplog):
            provider, reason, captured_count, siguiente, fase = r.args
            assert provider in {"deepseek", "gemini"}
            assert isinstance(reason, str) and reason
            assert isinstance(captured_count, int)
            assert isinstance(siguiente, str)
            assert fase == "PHASE_3_CREDIT_PROFILING"

    def test_backstop_logs_sin_pii(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.INFO, logger="app.services.hybrid_llm_router")
        deepseek_script, _ = _happy_path_scripts()
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
        _drive_matrix_loop(router)

        # Marcador de args redactados presente
        assert any("args_redacted=true" in r.getMessage() for r in caplog.records)

        forbidden_pii_phrases = [
            "Carlos",
            "Santa Marta",
            "Soy empleado.",
            "Gano dos salarios mínimos.",
            "Mi datacrédito es bueno.",
            "Mis gastos mensuales son un salario mínimo.",
            "Sí tengo gas natural.",
            "Mi vivienda es propia.",
            "Sí tengo plan celular a mi nombre.",
            "Bajaj Boxer 150",
        ]
        for r in caplog.records:
            message = r.getMessage()
            args_repr = repr(r.args)
            for phrase in forbidden_pii_phrases:
                assert phrase not in message, f"PII '{phrase}' en mensaje log: {message}"
                assert phrase not in args_repr, f"PII '{phrase}' en args log: {args_repr}"
