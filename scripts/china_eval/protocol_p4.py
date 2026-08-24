"""Protocolo P4: PASO 1 output format."""
from __future__ import annotations

import json
import re
from dataclasses import asdict

import httpx

from scripts.china_eval.common.clients import get_client, preflight_models
from scripts.china_eval.common.logging import log_event, new_trace_id
from scripts.china_eval.common.report import ProtocolResult, VariantResult
from scripts.china_eval.common.retry import retry_network


VARIANTS = [
    {
        "name": "primer_contacto",
        "system_suffix": "Incluye saludo cálido de Juan Pablo.",
        "skip_greeting": False,
    },
    {
        "name": "contacto_en_curso",
        "system_suffix": "NO incluyas saludo; el usuario ya fue saludado.",
        "skip_greeting": True,
    },
    {
        "name": "salvage_fallback",
        "system_suffix": "El catálogo no devolvió candidates. Reconstruye el caption canónico desde el Top Result stashado.",
        "skip_greeting": False,
    },
]


def _validate(content: str | None, variant: dict) -> tuple[str, str]:
    if not content:
        return "FAIL", "content vacío"
    text = content.strip()
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if len(lines) > 4:
        return "FAIL", f"{len(lines)} líneas > 4"
    if len(text) > 350:
        return "FAIL", f"{len(text)} chars > 350"
    if "Ficha Tecnica:" not in text:
        return "FAIL", "Falta prefijo 'Ficha Tecnica:'"
    if "$" not in text:
        return "FAIL", "Falta '$'"
    if not re.search(r"!\[.*?\]\(.*?\)", text):
        return "FAIL", "Falta imagen Markdown"
    if variant["name"] == "primer_contacto" and "Hola" not in text:
        return "FAIL", "Falta saludo cálido"
    if variant["name"] == "contacto_en_curso" and "Hola" in text:
        return "FAIL", "Incluye saludo no deseado"
    return "PASS", "Formato PASO 1 correcto"


def run(provider: str) -> ProtocolResult:
    trace_id = new_trace_id()
    client = get_client(provider)
    preflight_models(provider, client)
    base_prompt = (
        "Eres Juan Pablo de Tienda Las Motos. "
        "Genera el PASO 1 para una moto deportiva. "
        "El formato debe incluir: prefijo 'Ficha Tecnica:', precio con '$', imagen Markdown, "
        "máximo 4 líneas y máximo 350 caracteres. "
    )
    variants: list[VariantResult] = []
    passes = 0

    for idx, variant in enumerate(VARIANTS, start=1):
        system_prompt = base_prompt + variant["system_suffix"]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Muéstrame la moto deportiva"},
        ]
        request_summary = {"provider": provider, "model": client.model, "variant": variant["name"]}
        response_summary: dict = {}
        verdict = "FAIL"
        reason = ""
        try:
            resp = retry_network(lambda: client.chat_completion(messages))
            response_summary = {"content": resp.content}
            verdict, reason = _validate(resp.content, variant)
            if verdict == "PASS":
                passes += 1
        except httpx.HTTPError as exc:
            reason = f"HTTPError {exc.__class__.__name__}: {exc}"
        except Exception as exc:
            reason = f"Exception {exc.__class__.__name__}: {exc}"

        v = VariantResult(variant=idx, verdict=verdict, reason=reason, request_summary=request_summary, response_summary=response_summary)
        variants.append(v)
        log_event(trace_id, "P4", idx, provider, verdict, reason, request_summary, response_summary)

    protocol_verdict = "PASS" if passes >= 2 else "FAIL"
    return ProtocolResult(
        protocol="P4",
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
