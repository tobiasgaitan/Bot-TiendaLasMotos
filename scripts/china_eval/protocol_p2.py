"""Protocolo P2: calculate_credit_score single-turn."""
from __future__ import annotations

import json
from dataclasses import asdict

import httpx

from scripts.china_eval.common.clients import get_client
from scripts.china_eval.common.logging import log_event, new_trace_id
from scripts.china_eval.common.report import ProtocolResult, VariantResult
from scripts.china_eval.common.retry import retry_network
from scripts.china_eval.fixtures.tools import calculate_credit_score_tool


VARIANTS = [
    {
        "name": "PASO2_ciego_brilla",
        "input": "Calcula mi crédito con Brilla de Gases. Soy empleado, gano un salario mínimo, sin datacrédito, sí tengo plan celular, sin reportes, inicial 10%.",
        "expected_required": {"entidad": "Brilla de Gases", "ocupacion_y_contrato": "Empleado", "ingresos_demostrables": "SMLV"},
        "guard_check": None,
    },
    {
        "name": "CIERRE_8_datos",
        "input": (
            "Tengo ocupación Empleado, contrato Indefinido, ingresos 2 SMLV, "
            "datacrédito Bueno, gastos 1 SMLV, gas natural Sí, vivienda Propia, plan celular Sí. Calcula crédito."
        ),
        "expected_required": {"entidad": "Brilla de Gases"},
        "guard_check": None,
    },
    {
        "name": "CIERRE_4_datos_parciales",
        "input": "Soy empleado, ingresos 1.5 mínimos, sin datacrédito, plan celular sí. Calcula crédito.",
        "expected_required": {"entidad": "Brilla de Gases"},
        "guard_check": None,
    },
    {
        "name": "ingresos_coloquiales",
        "input": "Me gano un salario mínimo. Calcula crédito como empleado sin datacrédito, plan celular sí, sin reportes, inicial 10%.",
        "expected_required": {"ingresos_demostrables": "SMLV"},
        "guard_check": None,
    },
    {
        "name": "guard_numerico",
        "input": "Calcula crédito con ingresos 'el mínimo'.",
        "expected_required": {},
        "guard_check": "reject_or_clarify",
    },
]


def _validate(tool_calls: list[dict], variant: dict) -> tuple[str, str]:
    if not tool_calls:
        if variant["guard_check"] == "reject_or_clarify":
            return "PASS", "No invocó tool ante input numéricamente ambiguo (guard esperado)"
        return "FAIL", "No tool_calls presentes"
    tc = tool_calls[0]
    name = tc.get("function", {}).get("name")
    if name != "calculate_credit_score":
        return "FAIL", f"Nombre de tool incorrecto: {name}"
    try:
        args = json.loads(tc.get("function", {}).get("arguments", "{}"))
    except json.JSONDecodeError:
        return "FAIL", "arguments no es JSON válido"
    for key, value in variant["expected_required"].items():
        if args.get(key) != value:
            return "FAIL", f"arg {key}={args.get(key)!r} != esperado {value!r}"
    if variant["guard_check"] == "reject_or_clarify" and "ingresos_demostrables" in args:
        if args["ingresos_demostrables"] in {"el mínimo"}:
            return "FAIL", "Guard numérico no activó: aceptó monto no normalizado"
    return "PASS", "tool_call correcto"


def run(provider: str) -> ProtocolResult:
    trace_id = new_trace_id()
    client = get_client(provider)
    system_prompt = (
        "Eres el asesor Juan Pablo de Tienda Las Motos. "
        "Para calcular crédito usa calculate_credit_score con entidad Brilla de Gases. "
        "Si los ingresos no son un monto absoluto o SMLV explícito, pide clarificación."
    )
    tool = calculate_credit_score_tool()
    variants: list[VariantResult] = []
    passes = 0

    for idx, variant in enumerate(VARIANTS, start=1):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": variant["input"]},
        ]
        request_summary = {"provider": provider, "model": client.model, "variant": variant["name"], "input": variant["input"]}
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
            verdict, reason = _validate(resp.tool_calls, variant)
            if verdict == "PASS":
                passes += 1
        except httpx.HTTPError as exc:
            reason = f"HTTPError {exc.__class__.__name__}: {exc}"
        except Exception as exc:
            reason = f"Exception {exc.__class__.__name__}: {exc}"

        v = VariantResult(variant=idx, verdict=verdict, reason=reason, request_summary=request_summary, response_summary=response_summary)
        variants.append(v)
        log_event(trace_id, "P2", idx, provider, verdict, reason, request_summary, response_summary)

    protocol_verdict = "PASS" if passes >= 4 else "FAIL"
    return ProtocolResult(
        protocol="P2",
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
