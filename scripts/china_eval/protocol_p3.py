"""Protocolo P3: multi-turn MATRIZ 8 turnos."""
from __future__ import annotations

import json
from dataclasses import asdict

import httpx

from scripts.china_eval.common.clients import get_client, preflight_models
from scripts.china_eval.common.logging import log_event, new_trace_id
from scripts.china_eval.common.report import ProtocolResult, VariantResult
from scripts.china_eval.common.retry import retry_network
from scripts.china_eval.fixtures.tools import calculate_credit_score_tool


TURNS = [
    ("Ocupación", "Soy empleado"),
    ("Contrato", "Tengo contrato indefinido"),
    ("Ingresos", "Gano dos salarios mínimos"),
    ("Datacrédito", "Mi datacrédito es bueno"),
    ("Gastos", "Mis gastos son un salario mínimo"),
    ("Gas", "Sí tengo gas natural"),
    ("Vivienda", "Mi vivienda es propia"),
    ("Plan Celular", "Sí tengo plan celular"),
]


def run(provider: str) -> ProtocolResult:
    trace_id = new_trace_id()
    client = get_client(provider)
    preflight_models(provider, client)
    system_prompt = (
        "Eres el asesor Juan Pablo de Tienda Las Motos. "
        "Recopila los 8 datos de perfilamiento crediticio y luego invoca calculate_credit_score. "
        "No pidas todos los datos a la vez; avanza uno por turno. "
        "Al final invoca calculate_credit_score con entidad Brilla de Gases."
    )
    tool = calculate_credit_score_tool()
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    variants: list[VariantResult] = []
    tool_call_count = 0
    total_turns = len(TURNS)

    for idx, (field, user_text) in enumerate(TURNS, start=1):
        estado = f"<estado_perfilamiento> {field}: pendiente </estado_perfilamiento>"
        siguiente = f"<siguiente_pendiente> {field} </siguiente_pendiente>"
        prompt = f"{estado}\n{siguiente}"
        messages.append({"role": "user", "content": f"{prompt}\n{user_text}"})
        request_summary = {"turn": idx, "field": field, "user_text": user_text}
        response_summary: dict = {}
        verdict = "FAIL"
        reason = ""
        try:
            resp = retry_network(lambda: client.chat_completion(messages, tools=[tool]))
            response_summary = {
                "content": resp.content,
                "tool_calls": [
                    {"name": tc.get("function", {}).get("name"), "arguments": tc.get("function", {}).get("arguments")}
                    for tc in resp.tool_calls
                ],
            }
            if resp.tool_calls and resp.tool_calls[0].get("function", {}).get("name") == "calculate_credit_score":
                tool_call_count += 1
                verdict = "PASS"
                reason = "Invocó calculate_credit_score"
            elif resp.content:
                verdict = "PASS"
                reason = "Respuesta textual en turno intermedio"
            else:
                reason = "Sin content ni tool_calls"
        except httpx.HTTPError as exc:
            reason = f"HTTPError {exc.__class__.__name__}: {exc}"
        except Exception as exc:
            reason = f"Exception {exc.__class__.__name__}: {exc}"

        v = VariantResult(variant=idx, verdict=verdict, reason=reason, request_summary=request_summary, response_summary=response_summary)
        variants.append(v)
        log_event(trace_id, "P3", idx, provider, verdict, reason, request_summary, response_summary)

    rate = tool_call_count / total_turns
    protocol_verdict = "PASS" if rate >= 0.4 else "FAIL"
    return ProtocolResult(
        protocol="P3",
        provider=provider,
        verdict=protocol_verdict,
        reason=f"tool-call rate={rate:.2f} ({tool_call_count}/{total_turns})",
        trace_id=trace_id,
        variants=variants,
    )


if __name__ == "__main__":
    import sys

    prov = sys.argv[1] if len(sys.argv) > 1 else "deepseek"
    print(json.dumps(asdict(run(prov)), ensure_ascii=False, indent=2))
