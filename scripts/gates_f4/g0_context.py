"""
G0-CONTEXT: gate de ventana de contexto y límite de salida contra Qwen (qwen-omni-turbo, rol multimodal).
Mecanismo certificado BOT-PLAN-GATES-OVERRIDE-080:
  - Patch local de app.services.llm_client_service.is_qwen_enabled para la llamada Qwen.
  - Retry ante ConnectError/ReadTimeout.
Objetivos:
  - Verificar retención de contexto real en chat multi-turno.
  - Verificar que max_output_tokens=2048 es respetado (uso ≤ 2048 tokens).
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import patch

from app.services.llm_client_service import (
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
    os.environ.setdefault("QWEN_AGENTIC_MODEL", "qwen-turbo")
    os.environ.setdefault("QWEN_MULTIMODAL_MODEL", "qwen-omni-turbo")
    os.environ.setdefault("QWEN_CALL_TIMEOUT_S", "60")


@dataclass
class ContextResult:
    case: str
    ok: bool = False
    error: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)


async def _run_case(name: str, runner, retries: int = 3) -> ContextResult:
    result = ContextResult(case=name)
    last_error: Optional[str] = None
    for attempt in range(retries):
        reset_shared_llm_clients()
        try:
            with patch("app.services.llm_client_service.is_qwen_enabled", lambda: True):
                return await runner()
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            result.error = last_error
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))
    result.ok = False
    return result


async def _case_context_recall() -> ContextResult:
    """Chat de 5 turnos; la pregunta final requiere recordar datos del primer turno."""
    facade = await get_shared_llm_client_async(role="multimodal")
    chat = facade.aio.chats.create(model=os.environ["QWEN_MULTIMODAL_MODEL"])

    conversation = [
        ("user", "Hola, soy Esteban Salazar de Armenia. Busco una moto doble propósito."),
        ("model", "Mucho gusto Esteban. ¿Qué uso le darías principalmente a la moto?"),
        ("user", "La usaré para campo y ciudad, y necesito que sea económica."),
        ("model", "Entendido. ¿Prefieres financiación o contado?"),
        ("user", "A crédito. También quiero saber si me piden papeles de vivienda."),
        ("model", "Revisamos eso en el perfil."),
        ("user", "Resumiendo, ¿cuál es mi nombre, ciudad y tipo de moto que busco?"),
    ]

    for role, text in conversation[:-1]:
        if role == "user":
            await chat.send_message(text)
        else:
            # Mensajes del modelo no tienen API directa en este chat; se simulan enviando como user con prefijo.
            # El objetivo es retención, no precisión de roles.
            await chat.send_message(f"[BOT] {text}")

    final_prompt = conversation[-1][1]
    response = await chat.send_message(final_prompt)
    answer = (response.text or "").lower()

    ok = all(
        token in answer
        for token in ["esteban", "armenia", "doble propósito"]
    )
    return ContextResult(
        case="context_recall_5turns",
        ok=ok,
        detail={
            "final_answer": response.text,
            "expected_tokens": ["esteban", "armenia", "doble propósito"],
        },
    )


async def _case_max_output_2048() -> ContextResult:
    """Solicita una respuesta larga con max_output_tokens=2048 y verifica uso."""
    from google.genai import types

    facade = await get_shared_llm_client_async(role="multimodal")
    response = await facade.aio.models.generate_content(
        model=os.environ["QWEN_MULTIMODAL_MODEL"],
        contents=(
            "Genera un resumen detallado de las ventajas de las motocicletas de bajo cilindraje "
            "para uso urbano en Colombia. Mínimo 500 palabras."
        ),
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=2048,
        ),
    )
    completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
    word_count = len((response.text or "").split())
    ok = completion_tokens <= 2048 and word_count >= 50
    return ContextResult(
        case="max_output_2048",
        ok=ok,
        detail={
            "completion_tokens": completion_tokens,
            "word_count": word_count,
            "max_output_tokens": 2048,
        },
    )


async def main() -> int:
    _bootstrap_env()
    print("=" * 60)
    print("G0-CONTEXT: contexto y max output Qwen (qwen-omni-turbo, rol multimodal)")
    print("=" * 60)

    results: List[Dict[str, Any]] = []
    failures = 0

    runners = [
        ("context_recall_5turns", _case_context_recall),
        ("max_output_2048", _case_max_output_2048),
    ]

    for name, runner in runners:
        print(f"\n[Caso] {name}")
        result = await _run_case(name, runner)
        print(f"  ok={result.ok} detail={result.detail} error={result.error}")
        results.append({"case": name, "ok": result.ok, "detail": result.detail, "error": result.error})
        if not result.ok:
            failures += 1
            print("  -> FAIL")
        else:
            print("  -> PASS")

    print("\n" + "=" * 60)
    status = "ROJO" if failures else "VERDE"
    print(f"RESULTADO: {status}")
    print(f"  Fallos: {failures}/{len(runners)}")
    print("=" * 60)

    with open("scripts/gates_f4/g0_context_report.json", "w", encoding="utf-8") as f:
        json.dump({"status": status, "failures": failures, "cases": results}, f, ensure_ascii=False, indent=2)
    print("Reporte guardado en scripts/gates_f4/g0_context_report.json")
    return 1 if status == "ROJO" else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
