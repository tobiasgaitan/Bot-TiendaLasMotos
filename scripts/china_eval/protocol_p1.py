"""Protocolo P1: search_catalog single-turn."""
from __future__ import annotations

import json
from dataclasses import asdict

import httpx

from scripts.china_eval.common.clients import get_client, preflight_models
from scripts.china_eval.common.logging import log_event, new_trace_id
from scripts.china_eval.common.report import ProtocolResult, VariantResult
from scripts.china_eval.common.retry import retry_network
from scripts.china_eval.fixtures.tools import search_catalog_tool


VARIANTS = [
    {
        "input": "Quiero una moto deportiva",
        "expected_name": "search_catalog",
        "expected_args_keys": {"estilo": "Deportiva"},
    },
    {
        "input": "Tienen CR4 150?",
        "expected_name": "search_catalog",
        "expected_args_keys": {"modelo": "CR4 150"},
    },
    {
        "input": "Venden NKD 125?",
        "expected_name": "search_catalog",
        "expected_args_keys": {"modelo": "NKD 125"},
    },
    {
        "input": "Quiero una deportiva a crédito",
        "expected_name": "search_catalog",
        "expected_args_keys": {"estilo": "Deportiva"},
    },
    {
        "input": "Quiero una moto",
        "expected_name": "search_catalog",
        "expected_args_keys": {"searchBy": "moto"},
    },
]


def _validate(tool_calls: list[dict], expected_name: str, expected_args_keys: dict) -> tuple[str, str]:
    if not tool_calls:
        return "FAIL", "No tool_calls presentes"
    tc = tool_calls[0]
    name = tc.get("function", {}).get("name")
    if name != expected_name:
        return "FAIL", f"Nombre de tool incorrecto: {name}"
    try:
        args = json.loads(tc.get("function", {}).get("arguments", "{}"))
    except json.JSONDecodeError:
        return "FAIL", "arguments no es JSON válido"
    for key, value in expected_args_keys.items():
        if args.get(key) != value:
            return "FAIL", f"arg {key}={args.get(key)!r} != esperado {value!r}"
    return "PASS", "tool_call correcto"


def run(provider: str) -> ProtocolResult:
    trace_id = new_trace_id()
    client = get_client(provider)
    preflight_models(provider, client)
    system_prompt = (
        "Eres el asesor Juan Pablo de Tienda Las Motos. "
        "Cuando el usuario pregunte por una moto, DEBES usar la función search_catalog."
    )
    tool = search_catalog_tool()
    variants: list[VariantResult] = []
    passes = 0

    for idx, variant in enumerate(VARIANTS, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": variant["input"]},
        ]
        request_summary = {"provider": provider, "model": client.model, "input": variant["input"]}
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
            verdict, reason = _validate(resp.tool_calls, variant["expected_name"], variant["expected_args_keys"])
            if verdict == "PASS":
                passes += 1
        except httpx.HTTPError as exc:
            reason = f"HTTPError {exc.__class__.__name__}: {exc}"
        except Exception as exc:
            reason = f"Exception {exc.__class__.__name__}: {exc}"

        v = VariantResult(variant=idx, verdict=verdict, reason=reason, request_summary=request_summary, response_summary=response_summary)
        variants.append(v)
        log_event(trace_id, "P1", idx, provider, verdict, reason, request_summary, response_summary)

    protocol_verdict = "PASS" if passes >= 4 else "FAIL"
    return ProtocolResult(
        protocol="P1",
        provider=provider,
        verdict=protocol_verdict,
        reason=f"{passes}/{len(VARIANTS)} variantes PASS",
        trace_id=trace_id,
        variants=variants,
    )


if __name__ == "__main__":
    import sys

    prov = sys.argv[1] if len(sys.argv) > 1 else "deepseek"
    print(json.dumps(asdict(run(prov)), ensure_ascii=False, indent=2))
