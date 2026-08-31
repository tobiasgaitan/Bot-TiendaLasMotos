"""
Pines para BOT-BUILD-HYBRID-PROBE-BUG-101.

Bug A: histograma de paso2_cuota con entradas crudas de Cloud Logging provocaba
KeyError 'provider' en render_markdown.

Bug B: verify_paso2_session exigía score_resultado (que no persiste en PASO 2
simulación ciega) en lugar de verificar la cuota en el egreso.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ai_brain import CerebroIA
from app.services.memory_service import MemoryService
from scripts.f4_5_traffic.run_matriz_hybrid import (
    assert_habeas_accepted_sent,
    assert_script_presented,
    render_markdown,
    script_presented_in_history,
    verify_paso2_session,
    verify_session_routes,
)


def _make_report(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "run_id": "test",
        "generated_at": "2026-08-25T00:00:00+00:00",
        "dry_run": False,
        "preclean": True,
        "flag_check": "OK",
        "global_verdict": "VERDE",
        "global_errors": [],
        "global_warnings": [],
        "sessions": sessions,
        "raw_sessions": [],
    }


def _make_route_entry(text: str, ts: str) -> Dict[str, Any]:
    return {"textPayload": text, "timestamp": ts}


class TestRenderMarkdownResilience:
    def test_event_without_provider_does_not_raise(self) -> None:
        report = _make_report([
            {
                "session_idx": 1,
                "scenario_id": "paso2_cuota",
                "phone": "57377009901",
                "errors": [],
                "warnings": [],
                "verdict": "VERDE",
                "histogram": [
                    {
                        "reason": "default_conservador",
                        "captured_count": 0,
                        "timestamp": "2026-08-25T00:00:00Z",
                    }
                ],
            }
        ])
        md = render_markdown(report)
        assert "unknown" in md
        assert "Advertencias de histograma" in md

    def test_normal_event_renders_unchanged(self) -> None:
        report = _make_report([
            {
                "session_idx": 1,
                "scenario_id": "paso2_cuota",
                "phone": "57377009901",
                "errors": [],
                "warnings": [],
                "verdict": "VERDE",
                "histogram": [
                    {
                        "provider": "gemini",
                        "reason": "default_conservador",
                        "captured_count": 0,
                        "siguiente": None,
                        "fase": "PHASE_1_PROFILING",
                        "timestamp": "2026-08-25T00:00:00Z",
                    }
                ],
            }
        ])
        md = render_markdown(report)
        assert "gemini" in md
        assert "default_conservador" in md
        assert "unknown" not in md


class TestVerifyPaso2Session:
    @staticmethod
    def _patch(
        monkeypatch: pytest.MonkeyPatch,
        phone_texts: List[str],
        backstop_texts: List[str],
        prospect_doc: Dict[str, Any] | None = None,
    ) -> None:
        def fake_query(
            service_name: str,
            project: str,
            start: datetime,
            end: datetime,
            substring: str,
            limit: int = 100,
        ) -> List[Dict[str, Any]]:
            if substring == "[HYBRID BACKSTOP ASYNC]":
                return [{"textPayload": t} for t in backstop_texts]
            if "57377009901" in substring:
                return [{"textPayload": t} for t in phone_texts]
            return []

        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid.query_cloud_logging",
            fake_query,
        )
        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid._read_prospect_doc",
            lambda phone, project: prospect_doc or {},
        )

    def test_verde_with_cuota_and_zero_backstops(self, monkeypatch: pytest.MonkeyPatch) -> None:
        route_text = (
            "[HYBRID ROUTE] provider=gemini reason=default_conservador "
            "captured_count=0 siguiente=None fase=PHASE_1_PROFILING"
        )
        all_route = [_make_route_entry(route_text, "2026-08-25T00:01:00Z")]
        self._patch(
            monkeypatch,
            phone_texts=["Cuota mensual de $250.000 a 24 meses"],
            backstop_texts=[],
        )
        start = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 25, 1, 0, 0, tzinfo=timezone.utc)

        report = verify_paso2_session(
            1, all_route, start, end, "57377009901", "tiendalasmotos", "bot-tiendalasmotos-beta"
        )

        assert report["verdict"] == "VERDE"
        assert len(report["histogram"]) == 1
        assert report["histogram"][0].get("provider") == "gemini"
        assert report["errors"] == []
        assert any("score_resultado" in w for w in report["warnings"])

    def test_histogram_is_parsed_not_raw(self, monkeypatch: pytest.MonkeyPatch) -> None:
        route_text = (
            "[HYBRID ROUTE] provider=deepseek reason=tarea_faq_contexto "
            "captured_count=0 siguiente=None fase=None"
        )
        all_route = [{"textPayload": route_text, "timestamp": "2026-08-25T00:01:00Z"}]
        self._patch(
            monkeypatch,
            phone_texts=["Cuota de $250.000 mensuales"],
            backstop_texts=[],
        )
        start = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 25, 1, 0, 0, tzinfo=timezone.utc)

        report = verify_paso2_session(
            1, all_route, start, end, "57377009901", "tiendalasmotos", "bot-tiendalasmotos-beta"
        )

        hist = report["histogram"]
        assert len(hist) == 1
        assert set(hist[0].keys()) == {
            "provider",
            "reason",
            "captured_count",
            "siguiente",
            "fase",
            "timestamp",
        }

    def test_rojo_canonical_question(self, monkeypatch: pytest.MonkeyPatch) -> None:
        route_text = (
            "[HYBRID ROUTE] provider=gemini reason=default_conservador "
            "captured_count=0 siguiente=None fase=PHASE_1_PROFILING"
        )
        all_route = [_make_route_entry(route_text, "2026-08-25T00:01:00Z")]
        self._patch(
            monkeypatch,
            phone_texts=["Ficha Tecnica: ... \\n\\n¿Me confirmas el dato que falta?"],
            backstop_texts=[],
        )
        start = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 25, 1, 0, 0, tzinfo=timezone.utc)

        report = verify_paso2_session(
            1, all_route, start, end, "57377009901", "tiendalasmotos", "bot-tiendalasmotos-beta"
        )

        assert report["verdict"] == "ROJO"
        assert any("pregunta canónica" in e for e in report["errors"])

    def test_rojo_backstop_prematuro_captured_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        route_text = (
            "[HYBRID ROUTE] provider=gemini reason=default_conservador "
            "captured_count=0 siguiente=None fase=PHASE_1_PROFILING"
        )
        all_route = [_make_route_entry(route_text, "2026-08-25T00:01:00Z")]
        self._patch(
            monkeypatch,
            phone_texts=["Cuota de $250.000 mensuales"],
            backstop_texts=[
                "[HYBRID BACKSTOP ASYNC] reason=backstop_tool_prematuro captured_count=0 siguiente=None depth=0"
            ],
        )
        start = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 25, 1, 0, 0, tzinfo=timezone.utc)

        report = verify_paso2_session(
            1, all_route, start, end, "57377009901", "tiendalasmotos", "bot-tiendalasmotos-beta"
        )

        assert report["verdict"] == "ROJO"
        assert any("backstop_tool_prematuro" in e for e in report["errors"])

    def test_rojo_cuota_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        route_text = (
            "[HYBRID ROUTE] provider=gemini reason=default_conservador "
            "captured_count=0 siguiente=None fase=PHASE_1_PROFILING"
        )
        all_route = [_make_route_entry(route_text, "2026-08-25T00:01:00Z")]
        # Solo ficha con precio; no cuota/meses/enganche/inicial/financi.
        self._patch(
            monkeypatch,
            phone_texts=["Ficha Tecnica: TVS APACHE 160 · Precio: $10.509.999"],
            backstop_texts=[],
        )
        start = datetime(2026, 8, 25, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 8, 25, 1, 0, 0, tzinfo=timezone.utc)

        report = verify_paso2_session(
            1, all_route, start, end, "57377009901", "tiendalasmotos", "bot-tiendalasmotos-beta"
        )

        assert report["verdict"] == "ROJO"
        assert any("no contiene cuota" in e for e in report["errors"])


class TestScriptPresentedInHistory:
    def test_true_when_model_contains_privacy_link(self) -> None:
        history = [
            {"role": "user", "content": "¿Me compartes el link de la política de datos?"},
            {"role": "model", "content": "Claro, aquí está: https://tiendalasmotos.com/politica-de-privacidad"},
        ]
        assert script_presented_in_history(history) is True

    def test_false_when_model_lacks_link(self) -> None:
        history = [
            {"role": "user", "content": "¿Me compartes el link de la política de datos?"},
            {"role": "model", "content": "Claro, autoriza el tratamiento de datos."},
        ]
        assert script_presented_in_history(history) is False

    def test_false_when_only_user_has_link(self) -> None:
        history = [
            {"role": "user", "content": "https://tiendalasmotos.com/politica-de-privacidad"},
        ]
        assert script_presented_in_history(history) is False


class TestAssertScriptPresented:
    def test_passes_when_link_in_history(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid._read_chat_history",
            lambda phone, project, limit=20: [
                {"role": "model", "content": "Política: https://tiendalasmotos.com/politica-de-privacidad"}
            ],
        )
        # No debe levantar.
        assert_script_presented("57377009901", "tiendalasmotos", "matriz_empleado_alto", timeout=0.1)

    def test_aborts_rojo_no_script_presented(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid._read_chat_history",
            lambda phone, project, limit=20: [
                {"role": "model", "content": "Solo confirma con un sí."}
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            assert_script_presented("57377009901", "tiendalasmotos", "matriz_empleado_alto", timeout=0.1)
        assert "ROJO_NO_SCRIPT_PRESENTED" in str(exc_info.value)
        assert "https://tiendalasmotos.com/politica-de-privacidad" in str(exc_info.value)


class TestAssertHabeasAcceptedSentRetry:
    def test_immediate_fail_when_no_link_no_latch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid._read_prospect_doc",
            lambda phone, project: {"habeas_data_accepted_sent": False},
        )
        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid._read_chat_history",
            lambda phone, project, limit=20: [],
        )
        with pytest.raises(SystemExit) as exc_info:
            assert_habeas_accepted_sent("57377009901", "tiendalasmotos", "matriz_empleado_alto")
        assert "script legal no emitido (E1)" in str(exc_info.value)
        assert "habeas_data_accepted_sent=False" in str(exc_info.value)

    def test_defensive_retry_when_link_present_but_latch_pending(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: List[Dict[str, Any]] = []

        def fake_read_prospect_doc(phone: str, project: str) -> Dict[str, Any]:
            calls.append({"source": "doc"})
            # El latch se cierra en el segundo intento.
            if len([c for c in calls if c["source"] == "doc"]) < 2:
                return {"habeas_data_accepted_sent": False}
            return {"habeas_data_accepted_sent": True}

        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid._read_prospect_doc",
            fake_read_prospect_doc,
        )
        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid._read_chat_history",
            lambda phone, project, limit=20: [
                {"role": "model", "content": "https://tiendalasmotos.com/politica-de-privacidad"}
            ],
        )
        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid.time.sleep",
            lambda s: None,
        )
        assert_habeas_accepted_sent("57377009901", "tiendalasmotos", "matriz_empleado_alto")
        doc_calls = [c for c in calls if c["source"] == "doc"]
        assert len(doc_calls) >= 2

    def test_retry_stops_if_link_evidence_disappears(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid._read_prospect_doc",
            lambda phone, project: {"habeas_data_accepted_sent": False},
        )
        monkeypatch.setattr(
            "scripts.f4_5_traffic.run_matriz_hybrid._read_chat_history",
            lambda phone, project, limit=20: [],
        )
        with pytest.raises(SystemExit):
            assert_habeas_accepted_sent("57377009901", "tiendalasmotos", "matriz_empleado_alto")


# ===========================================================================
# Pines BOT-BUILD-E2-FIX-107 (P1-P6)
# ===========================================================================


def _make_json_response(payload: dict) -> Any:
    mock_response = MagicMock()
    mock_response.text = json.dumps(payload, ensure_ascii=False)
    mock_response.usage_metadata = MagicMock(
        total_token_count=10, prompt_token_count=8, candidates_token_count=2
    )
    return mock_response


def _build_cerebro_for_extraction(script_response: Any) -> CerebroIA:
    cerebro = CerebroIA()
    cerebro.client = MagicMock()

    async def _fake_call(*args: Any, **kwargs: Any) -> Any:
        return script_response

    cerebro._call_gemini_with_retry_async = _fake_call
    return cerebro


@pytest.mark.asyncio
async def test_p1_generate_summary_timeout_logs_type_and_repr(caplog: pytest.LogCaptureFixture) -> None:
    """P1: TimeoutError (str()=="") debe loguear type=TimeoutError y repr."""
    cerebro = CerebroIA()
    cerebro.client = MagicMock()

    async def _fake_call(*args: Any, **kwargs: Any) -> Any:
        raise TimeoutError()

    cerebro._call_gemini_with_retry_async = _fake_call

    with caplog.at_level("ERROR"):
        result = await cerebro.generate_summary(
            "Bot: ¿Tienes plan celular a tu nombre?\nUser: Sí",
            last_bot_question="¿Tienes plan celular a tu nombre?",
            session_id="test-p1",
        )

    assert result["extraction_failed"] is True
    assert result["extracted"].get("plan_celular") == "Sí"
    assert any("type=TimeoutError" in rec.message for rec in caplog.records)
    assert any("repr=TimeoutError()" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_p2_matrix_guard_plan_celular() -> None:
    """P2: LLM devuelve extracted vacío pero la pregunta+respuesta son inequívocas → plan_celular forzado."""
    cerebro = _build_cerebro_for_extraction(
        _make_json_response({"summary": "s", "extracted": {}})
    )
    history = "Bot: ¿Tienes plan celular a tu nombre?\nUser: Sí, tengo plan celular a mi nombre."

    result = await cerebro.generate_summary(
        history,
        last_bot_question="¿Tienes plan celular a tu nombre?",
        session_id="test-p2",
    )

    assert result["extracted"]["plan_celular"] == "Sí"


@pytest.mark.asyncio
async def test_p2_negative_affirmation_to_wrong_question_does_not_force_plan_celular() -> None:
    """P2-NEG: un 'Sí' a otra pregunta canónica NO fuerza plan_celular."""
    cerebro = _build_cerebro_for_extraction(
        _make_json_response({"summary": "s", "extracted": {}})
    )
    history = "Bot: ¿A qué te dedicas actualmente?\nUser: Sí, soy empleado."

    result = await cerebro.generate_summary(
        history,
        last_bot_question="¿A qué te dedicas actualmente?",
        session_id="test-p2-neg",
    )

    assert "plan_celular" not in result["extracted"]


@pytest.mark.asyncio
async def test_p3_matrix_guard_gas_natural_and_vivienda() -> None:
    """P3: guards para tiene_gas_natural (afirmación) y vivienda (keyword)."""
    cerebro = _build_cerebro_for_extraction(
        _make_json_response({"summary": "s", "extracted": {}})
    )

    gas_history = "Bot: ¿Cuentas con servicio de gas natural domiciliario?\nUser: Sí, a mi nombre."
    gas_result = await cerebro.generate_summary(
        gas_history,
        last_bot_question="¿Cuentas con servicio de gas natural domiciliario?",
        session_id="test-p3-gas",
    )
    assert gas_result["extracted"]["tiene_gas_natural"] == "Sí"

    vivienda_history = "Bot: ¿Cuál es tu tipo de vivienda?\nUser: Vivo en casa propia."
    vivienda_result = await cerebro.generate_summary(
        vivienda_history,
        last_bot_question="¿Cuál es tu tipo de vivienda?",
        session_id="test-p3-vivienda",
    )
    assert vivienda_result["extracted"]["vivienda"] == "Propia"


@pytest.mark.asyncio
async def test_p4_generate_and_update_summary_warns_on_extraction_failed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """P4: extraction_failed=True + extracted vacío → warning ZSF, NO 'Successfully updated' limpio."""
    from unittest.mock import AsyncMock, MagicMock

    from app.services.memory_service import MemoryService

    db_mock = MagicMock()
    ms = MemoryService(db_mock)
    monkeypatch.setattr(ms, "get_prospect_data", AsyncMock(return_value={}))
    update_calls: List[Dict[str, Any]] = []

    async def fake_update(phone: str, summary: str, extracted: Dict[str, Any], **kwargs: Any) -> None:
        update_calls.append(kwargs)

    monkeypatch.setattr(ms, "update_prospect_summary", fake_update)

    class FakeBrain:
        async def generate_summary(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
            # Payload real post-fix: extracted={} porque el LLM falló (timeout);
            # habeas_data_accepted_sent NO se inyecta en ruta de fallo.
            return {"summary": "s", "extracted": {}, "extraction_failed": True}

    with caplog.at_level("INFO"):
        await ms.generate_and_update_summary(
            "+57377009901",
            "historial",
            FakeBrain(),
        )

    assert len(update_calls) == 1
    assert update_calls[0]["extraction_failed"] is True
    assert not any("✅ Successfully updated prospect summary" in rec.message for rec in caplog.records)
    assert any("'Successfully updated' NO aplica" in rec.message for rec in caplog.records)


def test_p5_verify_session_routes_counts_summary_timeout_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """P5: el probe cuenta 'Error generating summary' con mensaje vacío o type=."""
    import scripts.f4_5_traffic.run_matriz_hybrid as rmh

    monkeypatch.setattr(rmh, "_read_prospect_doc", lambda _phone, _project: {"resumen_crediticio": {"captured_count": 7}})

    entries = [
        {"textPayload": "2026-08-26 03:00:41 - app.services.ai_brain - ERROR - ❌ Error generating summary for session +57377009901: ", "timestamp": "2026-08-26T03:00:41Z"},
        {"textPayload": "2026-08-26 03:02:11 - app.services.ai_brain - ERROR - ❌ Error generating summary for session +57377009901: type=TimeoutError repr=TimeoutError()", "timestamp": "2026-08-26T03:02:11Z"},
        {"textPayload": "[HYBRID ROUTE] provider=gemini reason=cierre_fase_completo captured_count=8 siguiente=COMPLETO fase=PHASE_3_CREDIT_PROFILING", "timestamp": "2026-08-26T03:05:00Z"},
    ]

    report = rmh.verify_session_routes(
        1, entries,
        datetime(2026, 8, 26, 0, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 8, 26, 23, 59, 59, tzinfo=timezone.utc),
        "57377009901",
        "tiendalasmotos",
    )

    assert report["summary_timeout_errors"] == 2
    assert any("summary con mensaje vacio/TimeoutError: 2" in w for w in report["warnings"])


@pytest.mark.asyncio
async def test_p6_timeout_on_plan_celular_turn_still_extracts_via_guard(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """P6: aunque el LLM falle por timeout en el turno de plan celular, el guard
    fuerza plan_celular='Sí' y el embudo puede cerrar."""
    cerebro = CerebroIA()
    cerebro.client = MagicMock()

    async def _fake_call(*args: Any, **kwargs: Any) -> Any:
        raise TimeoutError()

    cerebro._call_gemini_with_retry_async = _fake_call

    history = "Bot: ¿Tienes plan celular a tu nombre?\nUser: Sí, tengo plan celular a mi nombre."

    result = await cerebro.generate_summary(
        history,
        last_bot_question="¿Tienes plan celular a tu nombre?",
        session_id="test-p6",
    )

    assert result["extraction_failed"] is True
    assert result["extracted"]["plan_celular"] == "Sí"
