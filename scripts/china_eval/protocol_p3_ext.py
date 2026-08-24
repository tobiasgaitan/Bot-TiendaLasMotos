"""Protocolo P3-EXT: MATRIZ 8 turnos con prompt completo de Juan Pablo.

Objetivo: determinar si el FAIL original de P3 (tool-call rate 0.12) era
artefacto de protocolo (prompt mínimo + métrica errónea) o fallo real de
multi-turn fidelity, usando el system instruction real, inyección verbatim de
<estado_perfilamiento> + mandatos, y criterios recalibrados.

Inmutabilidad: CERO toques a app/core/ai_brain.py, app/core/prompts.py,
app/core/personality.json, app/core/juan_pablo_personality.docx.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import httpx

from scripts.china_eval.common.clients import OpenRouterClient, get_client, preflight_models
from scripts.china_eval.common.hybrid_router import HybridEvalRouter
from scripts.china_eval.common.logging import log_event, new_trace_id
from scripts.china_eval.common.report import (
    EvalReport,
    ProtocolResult,
    VariantResult,
    save_report,
)
from scripts.china_eval.common.retry import retry_network
from scripts.china_eval.fixtures.p3_ext_turns import (
    JUAN_PABLO_SYSTEM_INSTRUCTION,
    TURNS,
    build_user_turn_message,
    evaluate_profiling_matrix,
)
from scripts.china_eval.fixtures.tools import calculate_credit_score_tool


# Keywords para detectar a qué campo de la MATRIZ apunta la pregunta final.
FIELD_KEYWORDS: dict[str, list[str]] = {
    "Ocupación": [
        "ocupación",
        "ocupacion",
        "trabajas",
        "dedicas",
        "empleo",
        "trabajo",
        "a qué te dedicas",
        "a que te dedicas",
    ],
    "Contrato": [
        "contrato",
        "tipo de contrato",
        "vinculación",
        "vinculacion",
        "vínculo",
        "vinculo",
    ],
    "Ingresos": [
        "ingresos",
        "ingreso",
        "gana",
        "ganas",
        "salario",
        "devenga",
        "mensuales",
        "cuánto ganas",
        "cuanto ganas",
    ],
    "Reportes Datacrédito": [
        "datacrédito",
        "datacredito",
        "reportes",
        "reportado",
        "historial crediticio",
        "reporte",
        "datacrédit",
    ],
    "Gastos mensuales": [
        "gastos",
        "gasto",
        "egresos",
        "egreso",
        "cuánto gastas",
        "cuanto gastas",
    ],
    "Gas natural (Brilla)": [
        "gas",
        "brilla",
        "natural",
        "servicio de gas",
    ],
    "Vivienda": [
        "vivienda",
        "casa",
        "vives",
        "hogar",
        "tipo de vivienda",
        "en qué vives",
    ],
    "Plan celular": [
        "celular",
        "plan",
        "móvil",
        "movil",
        "plan celular",
        "tienes celular",
    ],
}


def _count_questions(content: str | None) -> int:
    """Cuenta signos de interrogación de cierre."""
    if not content:
        return 0
    return content.count("?")


def _matches_expected_field(content: str | None, expected_field: str) -> bool:
    """Verifica si la pregunta apunta al campo esperado (case-insensitive)."""
    if not content:
        return False
    text = content.lower()
    return any(kw.lower() in text for kw in FIELD_KEYWORDS.get(expected_field, []))


def _classify_turn(
    variant: int,
    expected_field: str,
    content: str | None,
    tool_calls: list[dict[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    """Clasifica un turno y retorna (verdict, reason, metrics).

    Razones estructuradas según el ticket:
    - orden_correcto
    - pregunta_fuera_de_matriz
    - pregunta_repetida
    - tool_prematuro
    - lista_de_preguntas
    - sin_pregunta
    - cierre_correcto
    - cierre_faltante
    - tool_incorrecto_en_cierre
    """
    tool_names = [tc.get("function", {}).get("name") for tc in tool_calls]
    q_count = _count_questions(content)
    metrics: dict[str, Any] = {
        "variant": variant,
        "expected_field": expected_field,
        "question_count": q_count,
        "tool_call_names": tool_names,
    }

    # Turno 8: la matriz está COMPLETA; debe invocar calculate_credit_score.
    if expected_field == "COMPLETO":
        if tool_names == ["calculate_credit_score"]:
            return "PASS", "cierre_correcto", metrics
        if tool_names:
            return "FAIL", "tool_incorrecto_en_cierre", metrics
        return "FAIL", "cierre_faltante", metrics

    # Turnos 1-7: cualquier tool_call es prematuro.
    if tool_names:
        return "FAIL", "tool_prematuro", metrics

    if q_count == 0:
        return "FAIL", "sin_pregunta", metrics
    if q_count > 1:
        return "FAIL", "lista_de_preguntas", metrics

    if _matches_expected_field(content, expected_field):
        return "PASS", "orden_correcto", metrics

    # Determinar si repitió un campo ya capturado o se desvió de la matriz.
    for field, keywords in FIELD_KEYWORDS.items():
        if field == expected_field:
            continue
        if any(kw.lower() in (content or "").lower() for kw in keywords):
            return "FAIL", "pregunta_repetida", metrics

    return "FAIL", "pregunta_fuera_de_matriz", metrics


def _score_turn(
    expected_field: str,
    reason: str,
    q_count: int,
) -> tuple[int, int, int, int]:
    """Actualiza contadores (fidelity, closure, single_question, zero_tool).

    Retorna deltas para sumar a los acumuladores.
    """
    fidelity = 0
    closure = 0
    single_question = 0
    zero_tool = 0

    if expected_field == "COMPLETO":
        if reason == "cierre_correcto":
            closure = 1
            zero_tool = 1
        # UNA_PREGUNTA en turno 8: no debe haber preguntas.
        if q_count == 0:
            single_question = 1
    else:
        if reason == "orden_correcto":
            fidelity = 1
        # UNA_PREGUNTA en turnos 1-7: exactamente una pregunta.
        if q_count == 1:
            single_question = 1
        # CERO_TOOL_PREMATURO en turnos 1-7: sin tool_calls.
        if reason != "tool_prematuro":
            zero_tool = 1

    return fidelity, closure, single_question, zero_tool


def run(
    provider: str,
    router: str = "direct",
    gemini_provider: str = "glm52",
    provider_label: str | None = None,
) -> ProtocolResult:
    """Ejecuta P3-EXT contra el proveedor indicado.

    Args:
        provider: proveedor primario (deepseek, glm52).
        router: 'direct' usa el proveedor directamente; 'hybrid' activa el
            HybridEvalRouter con DeepSeek para turnos 1-6 y Gemini fallback.
        gemini_provider: proveedor a usar como fallback 'Gemini' en modo híbrido.
        provider_label: etiqueta para el reporte (ej. 'hybrid-deepseek').
    """
    trace_id = new_trace_id()
    label = provider_label or provider
    if router == "hybrid":
        client: OpenRouterClient | HybridEvalRouter = HybridEvalRouter(
            deepseek_provider=provider,
            gemini_provider=gemini_provider,
        )
        preflight_models(provider, client.deepseek_client)
        preflight_models(gemini_provider, client.gemini_client)
    else:
        client = get_client(provider)
        preflight_models(provider, client)

    system_prompt = JUAN_PABLO_SYSTEM_INSTRUCTION
    tool = calculate_credit_score_tool()

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    variants: list[VariantResult] = []
    prospect_data: dict[str, Any] = {
        "nombre": "Carlos",
        "ciudad": "Santa Marta",
        "forma_pago": "Crédito",
        "habeas_data_accepted": True,
        "habeas_data_accepted_sent": True,
        "moto_interest": "Bajaj Boxer 150",
    }

    fidelity_hits = 0
    closure_hit = 0
    single_question_hits = 0
    zero_tool_hits = 0

    for turn in TURNS:
        variant = turn["variant"]
        user_text = turn["user_text"]

        # El campo esperado se calcula al INICIO del turno desde el checklist.
        _, next_pending = evaluate_profiling_matrix(prospect_data)
        expected_field = next_pending or "COMPLETO"

        user_content = build_user_turn_message(prospect_data, user_text)
        messages.append({"role": "user", "content": user_content})

        request_summary = {
            "turn": variant,
            "expected_field": expected_field,
            "user_text": user_text,
            "prospect_data_snapshot": {
                k: v for k, v in prospect_data.items()
                if k not in {"habeas_data_accepted", "habeas_data_accepted_sent"}
            },
        }
        response_summary: dict[str, Any] = {}
        verdict = "FAIL"
        reason = ""

        try:
            resp = retry_network(lambda: client.chat_completion(messages, tools=[tool]))
            response_summary = {
                "content": resp.content,
                "tool_calls": [
                    {
                        "name": tc.get("function", {}).get("name"),
                        "arguments": tc.get("function", {}).get("arguments"),
                    }
                    for tc in resp.tool_calls
                ],
            }
            verdict, reason, metrics = _classify_turn(
                variant, expected_field, resp.content, resp.tool_calls
            )
            response_summary["metrics"] = metrics

            fidelity_hits += _score_turn(expected_field, reason, metrics["question_count"])[0]
            closure_hit += _score_turn(expected_field, reason, metrics["question_count"])[1]
            single_question_hits += _score_turn(expected_field, reason, metrics["question_count"])[2]
            zero_tool_hits += _score_turn(expected_field, reason, metrics["question_count"])[3]

            # Reconstruir mensaje assistant para mantener contexto multi-turn.
            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if resp.content:
                assistant_msg["content"] = resp.content
            if resp.tool_calls:
                assistant_msg["tool_calls"] = resp.tool_calls
            messages.append(assistant_msg)

        except httpx.HTTPError as exc:
            reason = f"HTTPError {exc.__class__.__name__}: {exc}"
            response_summary = {"error": reason}
        except Exception as exc:
            reason = f"Exception {exc.__class__.__name__}: {exc}"
            response_summary = {"error": reason}

        variant_result = VariantResult(
            variant=variant,
            verdict=verdict,
            reason=reason,
            request_summary=request_summary,
            response_summary=response_summary,
        )
        variants.append(variant_result)
        log_event(
            trace_id=trace_id,
            protocol="P3-EXT",
            variant=variant,
            provider=provider,
            verdict=verdict,
            reason=reason,
            request=request_summary,
            response=response_summary,
        )

        # Actualizar prospect_data con lo capturado en este turno.
        prospect_data.update(turn.get("captures", {}))

    # Criterios recalibrados.
    fidelity_score = f"{fidelity_hits}/7"
    fidelity_pass = fidelity_hits >= 6

    closure_score = f"{closure_hit}/1"
    closure_pass = closure_hit == 1

    single_question_score = f"{single_question_hits}/8"
    single_question_pass = single_question_hits >= 7

    zero_tool_score = f"{zero_tool_hits}/8"
    zero_tool_pass = zero_tool_hits == 8

    all_pass = fidelity_pass and closure_pass and single_question_pass and zero_tool_pass
    protocol_verdict = "PASS" if all_pass else "FAIL"

    reason_parts = [
        f"FIDELIDAD_ORDEN={fidelity_score}({'PASS' if fidelity_pass else 'FAIL'})",
        f"CIERRE={closure_score}({'PASS' if closure_pass else 'FAIL'})",
        f"UNA_PREGUNTA={single_question_score}({'PASS' if single_question_pass else 'FAIL'})",
        f"CERO_TOOL_PREMATURO={zero_tool_score}({'PASS' if zero_tool_pass else 'FAIL'})",
    ]
    reason = "; ".join(reason_parts)

    if all_pass:
        reason += (
            " | FAIL original de P3 reclasificado como ARTEFACTO DE PROTOCOLO "
            "(prompt mínimo + métrica rate>=0.4 errónea)."
        )
    else:
        reason += (
            " | FAIL confirmado como FALLO DE MULTI-TURN FIDELITY; "
            "desviaciones a pesar de tags inyectados."
        )

    return ProtocolResult(
        protocol="P3-EXT",
        provider=label,
        verdict=protocol_verdict,
        reason=reason,
        trace_id=trace_id,
        variants=variants,
    )


def main() -> None:
    """Ejecuta P3-EXT para DeepSeek y GLM-5.2 y escribe china_eval_report.json.

    Si OPENROUTER_API_KEY no está configurada, fail-fast etiquetado sin intentar
    llamadas de red.
    """
    parser = argparse.ArgumentParser(description="P3-EXT: MATRIZ 8 turnos con prompt completo.")
    parser.add_argument(
        "--router",
        choices=["direct", "hybrid"],
        default="direct",
        help="Modo de ruteo: directo o híbrido DeepSeek/Gemini.",
    )
    parser.add_argument(
        "--gemini-provider",
        default="glm52",
        help="Proveedor OpenRouter a usar como fallback 'Gemini' en modo híbrido.",
    )
    args = parser.parse_args()

    if args.router == "hybrid":
        runs = [("hybrid-deepseek", "deepseek", args.gemini_provider)]
    else:
        runs = [("deepseek", "deepseek", args.gemini_provider), ("glm52", "glm52", args.gemini_provider)]

    reports: list[EvalReport] = []
    for provider_label, llm_provider, gemini_provider in runs:
        try:
            result = run(
                llm_provider,
                router=args.router,
                gemini_provider=gemini_provider,
                provider_label=provider_label,
            )
        except ValueError as exc:
            if "OPENROUTER_API_KEY" in str(exc):
                result = ProtocolResult(
                    protocol="P3-EXT",
                    provider=provider_label,
                    verdict="FAIL",
                    reason="CREDENCIALES_AUSENTES_EN_ENTORNO_BUILDER: OPENROUTER_API_KEY no configurada",
                    trace_id=new_trace_id(),
                    variants=[],
                )
            else:
                raise
        report = EvalReport(provider=provider_label, protocols=[result])
        report.compute_go_no_go()
        reports.append(report)

    report_path = save_report(reports)
    print(json.dumps([r.to_dict() for r in reports], ensure_ascii=False, indent=2))
    print(f"\nReporte guardado en: {report_path}")


if __name__ == "__main__":
    main()
