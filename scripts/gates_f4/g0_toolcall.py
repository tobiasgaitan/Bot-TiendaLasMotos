"""
G0-TOOLCALL: gate funcional de tool-calling contra Qwen (qwen-omni-turbo, Rama A nativa).
Mecanismo certificado BOT-PLAN-GATES-OVERRIDE-080:
  - Patch local de app.services.llm_client_service.is_qwen_enabled para la llamada Qwen.
  - Baseline Gemini usa el flag real de Firestore (false → Gemini).
  - Retry ante ConnectError/ReadTimeout (C5-108).
  - URL $QWEN_BASE_URL/chat/completions verbatim (sin reescritura).
Reglas:
  - Rama A (native) debe coincidir con baseline Gemini en tool+args.
  - Si diverge, se prueba Rama B (emulated).
  - Si Rama B también diverge → STOP ROJO.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from unittest.mock import patch

from google.genai import types

from app.services.llm_client_service import (
    _gemini_model,
    get_shared_llm_client_async,
    reset_shared_llm_clients,
)


def _load_secret(name: str) -> str:
    return subprocess.check_output(
        ["gcloud", "secrets", "versions", "access", "latest", "--secret", name, "--project=tiendalasmotos"],
        text=True,
    ).strip()


def _bootstrap_env() -> None:
    os.environ.setdefault("QWEN_OMNI_API_KEY", _load_secret("QWEN_OMNI_API_KEY"))
    os.environ.setdefault("QWEN_TURBO_API_KEY", _load_secret("QWEN_TURBO_API_KEY"))
    os.environ.setdefault("QWEN_BASE_URL", _load_secret("QWEN_BASE_URL"))
    os.environ.setdefault("QWEN_PRIMARY_MODEL", "qwen-omni-turbo")
    os.environ.setdefault("QWEN_CALL_TIMEOUT_S", "60")


@dataclass
class ToolCallResult:
    provider: str
    mode: str
    prompt: str
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    text: Optional[str] = None
    raw_parts: List[Dict[str, Any]] = field(default_factory=list)
    ok: bool = False
    error: Optional[str] = None


SEARCH_CATALOG = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_catalog",
            description="Busca motos en el catálogo por nombre, cilindraje o estilo.",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Término de búsqueda"}},
                "required": ["query"],
            },
        )
    ]
)

CALCULATE_CREDIT_SCORE = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="calculate_credit_score",
            description="Calcula capacidad de endeudamiento y score crediticio.",
            parameters={
                "type": "object",
                "properties": {
                    "ingresos_mensuales": {"type": "string"},
                    "gastos_mensuales": {"type": "string"},
                    "ocupacion": {"type": "string"},
                },
                "required": ["ingresos_mensuales", "gastos_mensuales"],
            },
        )
    ]
)


@dataclass
class Case:
    prompt: str
    tools: List[types.Tool]
    expected_tool: Optional[str]
    required_args: Set[str]


CASES: List[Case] = [
    Case("Busco una Apache 160", [SEARCH_CATALOG], "search_catalog", {"query"}),
    Case("Quiero ver motos deportivas", [SEARCH_CATALOG], "search_catalog", {"query"}),
    Case("¿Tienen NKD 125?", [SEARCH_CATALOG], "search_catalog", {"query"}),
    Case("Dame opciones de moto doble propósito", [SEARCH_CATALOG], "search_catalog", {"query"}),
    Case("Moto para ciudad 150cc", [SEARCH_CATALOG], "search_catalog", {"query"}),
    Case(
        "Gano 2 millones, gasto 800 mil, soy empleado. ¿Cuánto me prestan?",
        [CALCULATE_CREDIT_SCORE],
        "calculate_credit_score",
        {"ingresos_mensuales", "gastos_mensuales"},
    ),
    Case(
        "Mis ingresos son 3 mínimos y gastos 1 mínimo. Quiero crédito.",
        [CALCULATE_CREDIT_SCORE],
        "calculate_credit_score",
        {"ingresos_mensuales", "gastos_mensuales"},
    ),
    Case(
        "Gano 5 palos y gasto 2 palos, independiente. Score crediticio?",
        [CALCULATE_CREDIT_SCORE],
        "calculate_credit_score",
        {"ingresos_mensuales", "gastos_mensuales"},
    ),
    Case(
        "Busco una moto para trabajo y quiero saber si me dan crédito. Gano 2.5 millones, gasto 1 millón.",
        [SEARCH_CATALOG, CALCULATE_CREDIT_SCORE],
        "calculate_credit_score",
        {"ingresos_mensuales", "gastos_mensuales"},
    ),
    Case(
        "Necesito una moto 125 para delivery y cuota mensual baja. Gano 1.8 millones.",
        [SEARCH_CATALOG, CALCULATE_CREDIT_SCORE],
        "search_catalog",
        {"query"},
    ),
]


async def _call_provider(
    prompt: str, tools: List[types.Tool], provider: str, mode: str, retries: int = 3
) -> ToolCallResult:
    """Llama al provider. Para Qwen aplica patch local de is_qwen_enabled."""
    result = ToolCallResult(provider=provider, mode=mode, prompt=prompt)
    last_error: Optional[str] = None

    for attempt in range(retries):
        reset_shared_llm_clients()
        try:
            facade = await get_shared_llm_client_async()
            model = os.environ["QWEN_PRIMARY_MODEL"] if provider == "qwen" else _gemini_model()

            config = types.GenerateContentConfig(temperature=0.2, tools=tools)

            if provider == "qwen":
                # Mecanismo (b) certificado: inyectar el lector de flag solo para esta llamada.
                os.environ["QWEN_TOOLCALL_MODE"] = mode
                with patch("app.services.llm_client_service.is_qwen_enabled", lambda: True):
                    response = await facade.aio.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config,
                    )
            else:
                response = await facade.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )

            result.text = response.text
            parts = []
            for part in response.candidates[0].content.parts:
                p: Dict[str, Any] = {"text": part.text}
                if part.function_call is not None:
                    p["function_call"] = {"name": part.function_call.name, "args": part.function_call.args}
                    result.tool_name = part.function_call.name
                    result.tool_args = part.function_call.args or {}
                parts.append(p)
            result.raw_parts = parts
            result.ok = True
            return result
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            result.error = last_error
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))

    result.ok = False
    result.error = last_error
    return result


def _same_tool_call(a: ToolCallResult, b: ToolCallResult) -> bool:
    return a.tool_name == b.tool_name and set(a.tool_args.keys()) == set(b.tool_args.keys())


async def main() -> int:
    _bootstrap_env()
    print("=" * 60)
    print("G0-TOOLCALL: tool-calling Qwen (qwen-omni-turbo) vs Gemini")
    print("=" * 60)

    results: List[Dict[str, Any]] = []
    divergences_a = 0
    divergences_b = 0
    stop = False

    for idx, case in enumerate(CASES, 1):
        print(f"\n[Caso {idx:02d}] {case.prompt[:60]}...")
        baseline = await _call_provider(case.prompt, case.tools, "gemini", "native")
        qwen_a = await _call_provider(case.prompt, case.tools, "qwen", "native")

        print(f"  Baseline Gemini -> tool={baseline.tool_name} args={baseline.tool_args} ok={baseline.ok}")
        print(f"  Qwen Rama A     -> tool={qwen_a.tool_name} args={qwen_a.tool_args} ok={qwen_a.ok} error={qwen_a.error}")

        case_result: Dict[str, Any] = {
            "case": idx,
            "prompt": case.prompt,
            "baseline": {"tool": baseline.tool_name, "args": baseline.tool_args, "ok": baseline.ok},
            "rama_a": {"tool": qwen_a.tool_name, "args": qwen_a.tool_args, "ok": qwen_a.ok},
        }

        if not baseline.ok or not qwen_a.ok:
            case_result["verdict"] = "ERROR"
            results.append(case_result)
            stop = True
            continue

        if _same_tool_call(baseline, qwen_a):
            case_result["verdict"] = "RAMA_A_PASS"
            print("  -> RAMA A OK")
        else:
            divergences_a += 1
            print("  -> DIVERGENCIA Rama A; probando Rama B emulada...")
            qwen_b = await _call_provider(case.prompt, case.tools, "qwen", "emulated")
            print(f"  Qwen Rama B     -> tool={qwen_b.tool_name} args={qwen_b.tool_args} ok={qwen_b.ok}")
            case_result["rama_b"] = {"tool": qwen_b.tool_name, "args": qwen_b.tool_args, "ok": qwen_b.ok}
            if qwen_b.ok and _same_tool_call(baseline, qwen_b):
                case_result["verdict"] = "RAMA_B_PASS"
                print("  -> RAMA B OK")
            else:
                divergences_b += 1
                case_result["verdict"] = "FAIL"
                print("  -> STOP: divergencia también en Rama B")
                stop = True

        results.append(case_result)

    print("\n" + "=" * 60)
    status = "ROJO" if stop or divergences_b > 0 else "VERDE"
    print(f"RESULTADO: {status}")
    print(f"  Rama A divergences: {divergences_a}")
    print(f"  Rama B divergences: {divergences_b}")
    print(f"  Total cases: {len(CASES)}")
    print("=" * 60)

    with open("scripts/gates_f4/g0_toolcall_report.json", "w", encoding="utf-8") as f:
        json.dump({"status": status, "divergences_a": divergences_a, "divergences_b": divergences_b, "cases": results}, f, ensure_ascii=False, indent=2)
    print("Reporte guardado en scripts/gates_f4/g0_toolcall_report.json")
    return 1 if status == "ROJO" else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
