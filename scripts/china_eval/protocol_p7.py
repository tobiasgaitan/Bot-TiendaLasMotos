"""Protocolo P7: GLM-5.2 replay de P1-P4 con documentación de diferencias."""
from __future__ import annotations

from scripts.china_eval import protocol_p1, protocol_p2, protocol_p3, protocol_p4
from scripts.china_eval.common.clients import get_client, preflight_models
from scripts.china_eval.common.report import ProtocolResult


def run(provider: str = "glm52") -> list[ProtocolResult]:
    client = get_client(provider)
    preflight_models(provider, client)
    results: list[ProtocolResult] = []
    for runner in (protocol_p1.run, protocol_p2.run, protocol_p3.run, protocol_p4.run):
        result = runner(provider)
        # Anotar observaciones GLM-5.2 específicas
        if provider == "glm52":
            result.reason += " | Observación GLM-5.2: documentar 'text rides with tool calls' si ocurre."
        results.append(result)
    return results
