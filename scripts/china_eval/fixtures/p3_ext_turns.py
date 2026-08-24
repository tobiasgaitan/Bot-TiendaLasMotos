"""Fixtures y estado de la MATRIZ para P3-EXT.

Réplica verbatim del mecanismo de producción (_evaluate_profiling_matrix y
_build_profiling_checklist) para inyectar <estado_perfilamiento> y mandatos con
el mismo punto de inyección que app/services/ai_brain.py.

Inmutabilidad: este archivo SOLO LEE app/core/prompts.py y
app/core/personality.json. Cero modificaciones a archivos de producción.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def _load_system_instruction() -> str:
    """Carga JUAN_PABLO_SYSTEM_INSTRUCTION desde app/core/prompts.py (SSOT)."""
    prompts_path = Path("app/core/prompts.py")
    if prompts_path.exists():
        ns: dict[str, Any] = {}
        exec(compile(prompts_path.read_text(encoding="utf-8"), str(prompts_path), "exec"), ns)
        instr = ns.get("JUAN_PABLO_SYSTEM_INSTRUCTION", "")
        if instr:
            return instr.strip()
    # Fallback autorizado a personality.json (espejo del prompt de Firestore).
    personality_path = Path("app/core/personality.json")
    if personality_path.exists():
        data = json.loads(personality_path.read_text(encoding="utf-8"))
        return data.get("system_instruction", "").strip()
    raise RuntimeError("No se encontró JUAN_PABLO_SYSTEM_INSTRUCTION")


JUAN_PABLO_SYSTEM_INSTRUCTION = _load_system_instruction()


def _filled(data: dict[str, Any], key: str) -> bool:
    return bool(str(data.get(key) or "").strip())


def evaluate_profiling_matrix(
    prospect_data: Optional[dict[str, Any]],
) -> tuple[list[tuple[str, Optional[Any]]], Optional[str]]:
    """Réplica verbatim de app/services/ai_brain.py::_evaluate_profiling_matrix.

    Retorna (rows, siguiente_pendiente) donde rows es la lista ordenada de
    (label, valor|None) y siguiente_pendiente es el primer label sin valor
    (None si la matriz está COMPLETA).
    """
    data = prospect_data or {}
    servicios = str(data.get("servicios_publicos") or "").lower()

    rows = [
        ("Ocupación", data.get("ocupacion") if _filled(data, "ocupacion") else None),
        ("Contrato", data.get("ocupacion") if _filled(data, "ocupacion") else None),
        ("Ingresos", data.get("ingresos_mensuales") if _filled(data, "ingresos_mensuales") else None),
        ("Reportes Datacrédito", data.get("datacredito") if _filled(data, "datacredito") else None),
        ("Gastos mensuales", data.get("gastos_mensuales") if _filled(data, "gastos_mensuales") else None),
        (
            "Gas natural (Brilla)",
            (data.get("tiene_gas_natural") or data.get("servicios_publicos"))
            if (_filled(data, "tiene_gas_natural") or "gas" in servicios)
            else None,
        ),
        ("Vivienda", data.get("vivienda") if _filled(data, "vivienda") else None),
        (
            "Plan celular",
            (data.get("plan_celular") or data.get("servicios_publicos"))
            if (_filled(data, "plan_celular") or "celular" in servicios or "plan" in servicios)
            else None,
        ),
    ]

    next_pending = next((label for label, value in rows if not value), None)
    return rows, next_pending


def build_profiling_checklist(prospect_data: Optional[dict[str, Any]]) -> str:
    """Réplica verbatim de app/services/ai_brain.py::_build_profiling_checklist."""
    rows, next_pending = evaluate_profiling_matrix(prospect_data)

    lines = ["<estado_perfilamiento>"]
    for label, value in rows:
        if value:
            lines.append(f'  <item nombre="{label}" estado="CAPTURADO">{value}</item>')
        else:
            lines.append(f'  <item nombre="{label}" estado="PENDIENTE"/>')
    lines.append(f"  <siguiente_pendiente>{next_pending or 'COMPLETO'}</siguiente_pendiente>")
    lines.append("</estado_perfilamiento>")
    return "\n".join(lines)


def build_profiling_mandate(next_pending: Optional[str]) -> str:
    """Réplica verbatim del mandato inyectado en producción (ai_brain.py)."""
    if next_pending is None:
        return (
            "\n[MANDATO DE CIERRE DE FASE: <siguiente_pendiente> indica COMPLETO. "
            "Tu ÚNICA acción permitida en este turno es INVOCAR la herramienta "
            "calculate_credit_score con los datos del perfil. PROHIBIDO hacer más "
            "preguntas de perfilamiento. PROHIBIDO generar texto libre antes de "
            "tener el JSON del score.]\n"
        )
    return (
        "\n[MANDATO DE PERFILAMIENTO: Tienes ESTRICTAMENTE PROHIBIDO repreguntar "
        "los datos marcados como CAPTURADO. Tu única pregunta pendiente debe ser "
        "el dato indicado en <siguiente_pendiente>.]\n"
    )


def build_user_turn_message(prospect_data: dict[str, Any], user_text: str) -> str:
    """Construye el mensaje de usuario con checklist + mandato + texto.

    El punto de inyección imita al bloque <contexto_dinamico> de producción,
    donde profiling_xml se inserta después de captured_data_xml.
    """
    checklist = build_profiling_checklist(prospect_data)
    _, next_pending = evaluate_profiling_matrix(prospect_data)
    mandate = build_profiling_mandate(next_pending)
    profiling_xml = "\n" + checklist + mandate
    return (
        "<contexto_dinamico>\n"
        "  <estado_del_embudo>\n"
        "    <fase_actual>PHASE_3_CREDIT_PROFILING</fase_actual>\n"
        "  </estado_del_embudo>\n"
        f"{profiling_xml}"
        "</contexto_dinamico>\n"
        "\n"
        f"{user_text}"
    )


# Secuencia canónica de 8 turnos P3-EXT.
#
# Nota de alineación con producción: el checklist marca Contrato como CAPTURADO
# cuando ocupacion tiene valor (EXTRACTION_SCHEMA fusiona ambos datos). Por eso
# el turno 1 captura Ocupación+Contrato y el turno 2 pide Ingresos. El turno 8
# representa la respuesta del usuario al dato 8 con la matriz ya COMPLETA; el
# asistente debe invocar calculate_credit_score.
TURNS = [
    {
        "variant": 1,
        "field": "Ocupación",
        "user_text": "Soy empleado.",
        "captures": {"ocupacion": "Empleado"},
    },
    {
        "variant": 2,
        "field": "Ingresos",
        "user_text": "Gano dos salarios mínimos.",
        "captures": {"ingresos_mensuales": "2 SMLV"},
    },
    {
        "variant": 3,
        "field": "Reportes Datacrédito",
        "user_text": "Mi datacrédito es bueno.",
        "captures": {"datacredito": "Bueno"},
    },
    {
        "variant": 4,
        "field": "Gastos mensuales",
        "user_text": "Mis gastos mensuales son un salario mínimo.",
        "captures": {"gastos_mensuales": "1 SMLV"},
    },
    {
        "variant": 5,
        "field": "Gas natural (Brilla)",
        "user_text": "Sí tengo gas natural.",
        "captures": {"tiene_gas_natural": "Sí"},
    },
    {
        "variant": 6,
        "field": "Vivienda",
        "user_text": "Mi vivienda es propia.",
        "captures": {"vivienda": "Propia"},
    },
    {
        "variant": 7,
        "field": "Plan celular",
        "user_text": "Sí tengo plan celular a mi nombre.",
        "captures": {"plan_celular": "Sí"},
    },
    {
        "variant": 8,
        "field": "CIERRE",
        "user_text": "Sí tengo plan celular a mi nombre.",
        "captures": {},
    },
]
