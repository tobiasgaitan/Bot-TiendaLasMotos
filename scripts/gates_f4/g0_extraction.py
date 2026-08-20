"""
G0-EXTRACTION: gate de extracción estructurada contra Qwen (qwen-turbo, rol agentic).
Mecanismo certificado BOT-PLAN-GATES-OVERRIDE-080:
  - Patch local de app.services.llm_client_service.is_qwen_enabled para la llamada Qwen.
  - Baseline Gemini usa el flag real de Firestore (false → Gemini).
  - ≥20 fixtures distintos sobre EXTRACTION_SCHEMA.
  - Retry ante ConnectError/ReadTimeout.
Reglas:
  - Cada fixture debe producir JSON válido con las claves mandatorias.
  - Divergencia Qwen (JSON inválido, mandatorios ausentes o valor esperado errado) → STOP.
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

from app.services.ai_brain import EXTRACTION_SCHEMA
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
    os.environ.setdefault("QWEN_AGENTIC_MODEL", "qwen-turbo")
    os.environ.setdefault("QWEN_MULTIMODAL_MODEL", "qwen-omni-turbo")
    os.environ.setdefault("QWEN_CALL_TIMEOUT_S", "60")


@dataclass
class ExtractionResult:
    provider: str
    prompt: str
    raw: str = ""
    parsed: Dict[str, Any] = field(default_factory=dict)
    ok: bool = False
    error: Optional[str] = None
    missing_required: Set[str] = field(default_factory=set)


REQUIRED_TOP_LEVEL = {"summary", "extracted"}
REQUIRED_EXTRACTED = {"nombre", "ciudad", "moto_interest", "habeas_data_accepted"}


def _make_prompt(conversation: str, last_bot_question: str = "") -> str:
    return (
        "Extrae la información del prospecto en JSON estricto siguiendo el schema.\n\n"
        "HISTORIAL DE CHAT:\n"
        f"{conversation}\n\n"
        f"ÚLTIMA PREGUNTA DEL BOT: {last_bot_question}\n"
    )


# ≥20 fixtures con valores esperados (comparación flexible, sin PII sensible).
FIXTURES: List[Dict[str, Any]] = [
    {
        "name": "nombre+ciudad+moto",
        "prompt": _make_prompt(
            "Bot: ¡Hola! Soy el asistente de Tienda Las Motos. ¿En qué puedo ayudarte?\n"
            "Usuario: Hola, soy Juan Pérez de Bogotá y busco una TVS Apache 160."
        ),
        "expected": {"nombre": "Juan Pérez", "ciudad": "Bogotá", "moto_interest": "TVS Apache 160"},
    },
    {
        "name": "habeas_acepta",
        "prompt": _make_prompt(
            "Bot: Para continuar necesito tu autorización. Puedes ver la política en "
            "https://tiendalasmotos.com/politica-de-privacidad ¿Aceptas?\n"
            "Usuario: Sí, acepto. Me llamo María Gómez, vivo en Medellín y quiero la TVS Sport 100."
        ),
        "expected": {"nombre": "María Gómez", "ciudad": "Medellín", "moto_interest": "TVS Sport 100", "habeas_data_accepted": True},
    },
    {
        "name": "habeas_rechaza",
        "prompt": _make_prompt(
            "Bot: ¿Autorizas el tratamiento de datos?\nUsuario: No estoy seguro."
        ),
        "expected": {"habeas_data_accepted": False},
    },
    {
        "name": "ingresos_gastos_palos",
        "prompt": _make_prompt(
            "Usuario: Buenas, mi nombre es Carlos Ruiz, soy de Cali. "
            "Gano 2 millones y gasto 800 mil. Busco moto para delivery."
        ),
        "expected": {"nombre": "Carlos Ruiz", "ciudad": "Cali", "ingresos_mensuales": "2000000", "gastos_mensuales": "800000"},
    },
    {
        "name": "ingresos_minimos",
        "prompt": _make_prompt(
            "Usuario: Me llamo Ana López, vivo en Cartagena. Gano tres mínimos y gasto uno."
        ),
        "expected": {"nombre": "Ana López", "ciudad": "Cartagena", "ingresos_mensuales": "5117715"},
    },
    {
        "name": "ocupacion_independiente",
        "prompt": _make_prompt(
            "Usuario: Soy Pedro Vargas, independiente en Bucaramanga. Quiero la TVS Sport 100."
        ),
        "expected": {"nombre": "Pedro Vargas", "ciudad": "Bucaramanga", "ocupacion": "Independiente", "moto_interest": "TVS Sport 100"},
    },
    {
        "name": "ocupacion_empleado",
        "prompt": _make_prompt(
            "Usuario: Mi nombre es Luisa Fernández, trabajo como empleada en Manizales y busco moto automática."
        ),
        "expected": {"nombre": "Luisa Fernández", "ciudad": "Manizales"},
    },
    {
        "name": "datacredito_al_dia",
        "prompt": _make_prompt(
            "Usuario: Soy Andrés Muñoz de Pereira. Estoy al día en datacrédito y quiero la Apache 160."
        ),
        "expected": {"nombre": "Andrés Muñoz", "ciudad": "Pereira", "datacredito": "Al día", "moto_interest": "Apache 160"},
    },
    {
        "name": "vivienda_arriendo",
        "prompt": _make_prompt(
            "Usuario: Me llamo Diana Torres, vivo en arriendo en Cúcuta. Busco moto 125."
        ),
        "expected": {"nombre": "Diana Torres", "ciudad": "Cúcuta", "vivienda": "Arriendo"},
    },
    {
        "name": "forma_pago_credito",
        "prompt": _make_prompt(
            "Usuario: Hola, soy Javier Díaz de Villavicencio. Quiero la NKD 125 a crédito con 0 inicial."
        ),
        "expected": {"nombre": "Javier Díaz", "ciudad": "Villavicencio", "forma_pago": "Crédito", "moto_interest": "NKD 125"},
    },
    {
        "name": "forma_pago_contado",
        "prompt": _make_prompt(
            "Usuario: Soy Patricia Morales de Pasto. Voy a pagar la moto de contado."
        ),
        "expected": {"nombre": "Patricia Morales", "ciudad": "Pasto", "forma_pago": "Contado"},
    },
    {
        "name": "plan_celular_si",
        "prompt": _make_prompt(
            "Usuario: Me llamo Roberto Castro de Ibagué. Tengo plan postpago y quiero moto para trabajo."
        ),
        "expected": {"nombre": "Roberto Castro", "ciudad": "Ibagué", "plan_celular": "Sí"},
    },
    {
        "name": "gas_natural_no",
        "prompt": _make_prompt(
            "Usuario: Soy Natalia Ríos de Montería. No tengo gas natural a mi nombre. Busco moto 160."
        ),
        "expected": {"nombre": "Natalia Ríos", "ciudad": "Montería", "tiene_gas_natural": "No"},
    },
    {
        "name": "mora_paz_salvo",
        "prompt": _make_prompt(
            "Usuario: Me llamo Esteban Salazar de Armenia. Tuve una mora hace 2 años pero tengo paz y salvo."
        ),
        "expected": {"nombre": "Esteban Salazar", "ciudad": "Armenia", "mora_y_paz_salvo": "Paz y salvo"},
    },
    {
        "name": "moto_confirmada",
        "prompt": _make_prompt(
            "Bot: ¿Te interesa la TVS Apache 160?\n"
            "Usuario: Sí, me interesa, esa es la moto que quiero. Me llamo Laura Vargas de Sincelejo."
        ),
        "expected": {"nombre": "Laura Vargas", "ciudad": "Sincelejo", "moto_interest": "TVS Apache 160", "moto_confirmada": True},
    },
    {
        "name": "pivot_competencia",
        "prompt": _make_prompt(
            "Usuario: Busco una Boxer 100.\n"
            "Bot: Te recomiendo la TVS Sport 100, equivalente en nuestro catálogo.\n"
            "Usuario: Perfecto, la TVS Sport 100 me interesa. Soy Miguel Ángel de Riohacha."
        ),
        "expected": {"nombre": "Miguel Ángel"},
        "acceptable": {"moto_interest": ["TVS Sport 100", "Boxer 100"]},
    },
    {
        "name": "cedula_explicita",
        "prompt": _make_prompt(
            "Usuario: Me llamo Sergio Ortiz de Valledupar, mi cédula es 1234567890 y busco moto doble propósito."
        ),
        "expected": {"nombre": "Sergio Ortiz", "ciudad": "Valledupar", "cedula_usuario": "1234567890"},
    },
    {
        "name": "servicios_publicos",
        "prompt": _make_prompt(
            "Usuario: Soy Camila Herrera de Popayán. Tengo gas natural y plan de celular a mi nombre."
        ),
        "expected": {"nombre": "Camila Herrera", "ciudad": "Popayán", "servicios_publicos": "Gas Natural", "plan_celular": "Sí"},
    },
    {
        "name": "estudiante",
        "prompt": _make_prompt(
            "Usuario: Hola, soy Daniela Castaño de Tunja, estudiante, busco moto barata."
        ),
        "expected": {"nombre": "Daniela Castaño", "ciudad": "Tunja", "ocupacion": "Estudiante"},
    },
    {
        "name": "pensionado",
        "prompt": _make_prompt(
            "Usuario: Me llamo Fernando Beltrán de Neiva, pensionado, gano 1.5 millones."
        ),
        "expected": {"nombre": "Fernando Beltrán", "ciudad": "Neiva", "ocupacion": "Pensionado", "ingresos_mensuales": "1500000"},
    },
]


async def _extract(prompt: str, provider: str, retries: int = 3) -> ExtractionResult:
    result = ExtractionResult(provider=provider, prompt=prompt)
    last_error: Optional[str] = None

    for attempt in range(retries):
        reset_shared_llm_clients()
        try:
            facade = await get_shared_llm_client_async(
                role="agentic" if provider == "qwen" else "multimodal"
            )
            model = os.environ["QWEN_AGENTIC_MODEL"] if provider == "qwen" else _gemini_model()

            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=EXTRACTION_SCHEMA,
            )

            if provider == "qwen":
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

            raw = response.text.strip()
            result.raw = raw
            parsed = json.loads(raw)
            result.parsed = parsed
            result.ok = True

            missing_top = REQUIRED_TOP_LEVEL - set(parsed.keys())
            extracted = parsed.get("extracted", {}) or {}
            missing_ext = REQUIRED_EXTRACTED - set(extracted.keys())
            result.missing_required = missing_top | missing_ext
            return result
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            result.error = last_error
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))

    result.ok = False
    result.error = last_error
    return result


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower()


def _check_expected(
    extracted: Dict[str, Any],
    expected: Dict[str, Any],
    acceptable: Optional[Dict[str, List[str]]] = None,
) -> Set[str]:
    failed: Set[str] = set()
    acceptable = acceptable or {}
    for key, exp_val in expected.items():
        actual = extracted.get(key)
        if isinstance(exp_val, bool):
            if bool(actual) != exp_val:
                failed.add(key)
        else:
            exp_norm = _normalize(exp_val)
            act_norm = _normalize(actual)
            accepted_norms = {_normalize(v) for v in acceptable.get(key, [])}
            if act_norm in accepted_norms:
                continue
            if exp_norm and act_norm and exp_norm not in act_norm and act_norm not in exp_norm:
                failed.add(key)
            elif not exp_norm and not act_norm:
                pass
            elif not exp_norm or not act_norm:
                failed.add(key)
    return failed


async def main() -> int:
    _bootstrap_env()
    print("=" * 60)
    print("G0-EXTRACTION: extracción estructurada Qwen (qwen-turbo) vs Gemini")
    print("=" * 60)

    results: List[Dict[str, Any]] = []
    failures = 0
    divergences = 0

    for idx, fixture in enumerate(FIXTURES, 1):
        name = fixture["name"]
        prompt = fixture["prompt"]
        expected = fixture["expected"]
        print(f"\n[Caso {idx:02d}] {name}")

        baseline = await _extract(prompt, "gemini")
        qwen = await _extract(prompt, "qwen")

        baseline_extracted = baseline.parsed.get("extracted", {}) if baseline.parsed else {}
        qwen_extracted = qwen.parsed.get("extracted", {}) if qwen.parsed else {}

        acceptable = fixture.get("acceptable", {})
        baseline_failed = _check_expected(baseline_extracted, expected, acceptable)
        qwen_failed = _check_expected(qwen_extracted, expected, acceptable)

        print(f"  Baseline Gemini -> ok={baseline.ok} missing={sorted(baseline.missing_required)} expected_fail={sorted(baseline_failed)}")
        print(f"  Qwen            -> ok={qwen.ok} missing={sorted(qwen.missing_required)} expected_fail={sorted(qwen_failed)}")

        case_result = {
            "case": idx,
            "name": name,
            "prompt": prompt,
            "baseline": {"ok": baseline.ok, "missing": sorted(baseline.missing_required), "failed": sorted(baseline_failed), "raw": baseline.raw},
            "qwen": {"ok": qwen.ok, "missing": sorted(qwen.missing_required), "failed": sorted(qwen_failed), "raw": qwen.raw},
        }

        if not qwen.ok or qwen.missing_required or qwen_failed:
            case_result["verdict"] = "FAIL"
            failures += 1
            divergences += 1
            print("  -> FAIL")
        else:
            case_result["verdict"] = "PASS"
            print("  -> PASS")

        results.append(case_result)

    print("\n" + "=" * 60)
    status = "ROJO" if failures else "VERDE"
    print(f"RESULTADO: {status}")
    print(f"  Fallos: {failures}/{len(FIXTURES)}")
    print(f"  Divergencias: {divergences}")
    print("=" * 60)

    with open("scripts/gates_f4/g0_extraction_report.json", "w", encoding="utf-8") as f:
        json.dump({"status": status, "failures": failures, "divergences": divergences, "cases": results}, f, ensure_ascii=False, indent=2)
    print("Reporte guardado en scripts/gates_f4/g0_extraction_report.json")
    return 1 if status == "ROJO" else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
