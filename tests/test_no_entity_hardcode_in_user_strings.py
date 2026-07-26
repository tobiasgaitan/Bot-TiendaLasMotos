"""
Guard anti-regresión [BOT-PLAN-FIX-HARDCODE-ENTITY-LEAK-007].

Erradicación de menciones hardcoded de entidades financieras en strings
dirigidos al usuario dentro de app/services/ai_brain.py, alineando el código
con la doctrina neutral del PASO 4 del prompt ("...con nuestro sistema...").

T1 — Pin de identidad verbatim (drift-proof): la pregunta pendiente de
     PHASE_2_HABEAS_DATA debe ser byte-idéntica al script del PASO 4 extraído
     del prompt SSOT (prompts.py). Si el prompt cambia, el test fuerza sincronía.
T2 — Guard estático: toda línea de ai_brain.py que mencione una entidad debe
     corresponder a un patrón SANCIONADO (parámetros de herramienta válidos,
     doctrina ruta 1/ruta 3 del prompt, schema LLM-facing, comentarios/logs).
     Cualquier otra ocurrencia → FAIL con la línea exacta.
T3 — Pin de ausencia: la pregunta pendiente PHASE_2 no contiene entidades.
"""

import pathlib
import re

import pytest

from app.services.ai_brain import CerebroIA
from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION

ENTITIES = ["Brilla de Gases", "Brilla", "Banco de Bogotá", "Crediorbe", "CrediOrbe"]

# Patrones sancionados (constraint del ticket + doctrina del prompt).
# Toda línea de ai_brain.py con una entidad DEBE matchear al menos uno.
# Los parámetros internos de herramientas (entidad="Brilla de Gases") son
# VÁLIDOS por constraint y quedan ignorados por construcción del allowlist.
SANCTIONED_PATTERNS = [
    r'entidad\s*=\s*"Brilla de Gases"',            # parámetro calculate_credit_score / helper (VÁLIDO)
    r'"entidad":\s*"Brilla de Gases"',             # BLIND_CREDIT_DEFAULTS (VÁLIDO)
    r'entidad:\s*str\s*=\s*"Brilla de Gases"',     # default de _calculate_payment_helper
    r'entity",\s*"Brilla de Gases"',               # kwargs.get("entity", ...) fallback interno
    r"\[[\"']Brilla de Gases[\"'],\s*[\"']Brilla[\"']\]",  # ramas internas de scoring
    r"==\s*[\"']Brilla de Gases[\"']",             # rama doctrinal ruta 3 (CIERRE del prompt)
    r"res\.get\('entity', 'Brilla de Gases'\)",    # fallback interno de entity
    r"- ENTIDAD: Brilla de Gases",                 # tool response LLM-facing (ruta 3 sancionada)
    r"APTO para Brilla",                           # mandato interno ruta 3
    r"Gas natural \(Brilla\)",                     # label checklist (= ítem 6 de la matriz del prompt)
    r"- Brilla: Requieren",                        # FAQ requisitos (SSOT sancionado, doctrina ruta 3)
    r"Indispensable para Brilla",                  # descripción schema herramienta (LLM-facing)
    r"Sufi, Finesa, Brilla",                       # ejemplo en descripción schema (LLM-facing)
    r"Extranjeros, Brilla",                        # descripción schema query_faq (LLM-facing)
    r"^\s*#",                                      # comentarios
    r"logger\.",                                   # logs forenses (no van al usuario)
]


def test_pending_question_matches_paso4_verbatim():
    """
    [BOT-PLAN-FIX-HARDCODE-ENTITY-LEAK-007] T1 — Pin de identidad drift-proof.
    La pregunta pendiente de PHASE_2_HABEAS_DATA debe ser byte-idéntica al
    script del PASO 4 del prompt SSOT (constraint 'obligatorio' del ticket).
    """
    m = re.search(r'lanza exactamente: "(.+?)"', JUAN_PABLO_SYSTEM_INSTRUCTION)
    assert m, "No se pudo extraer el script del PASO 4 desde el prompt SSOT"
    paso4_script = m.group(1)

    cerebro = CerebroIA()
    question = cerebro._get_pending_funnel_question(
        "PHASE_2_HABEAS_DATA", {"moto_interest": "TVS APACHE 160"}
    )
    assert question == paso4_script, (
        "La pregunta pendiente de PHASE_2 se desincronizó del PASO 4 del prompt.\n"
        f"Prompt SSOT : {paso4_script!r}\n"
        f"Código      : {question!r}"
    )


def test_no_entity_hardcode_in_user_strings():
    """
    [BOT-PLAN-FIX-HARDCODE-ENTITY-LEAK-007] T2 — Guard estático anti-regresión.
    Escanea ai_brain.py: toda línea que mencione una entidad financiera debe
    corresponder a un patrón sancionado (parámetros de herramienta válidos,
    doctrina del prompt, schema LLM-facing, comentarios/logs). Falla con las
    líneas exactas si aparece una entidad en un string de usuario.
    Patrón hermano de test_crediorbe_eradicated_from_source (FIX-E).
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    src = (root / "app/services/ai_brain.py").read_text(encoding="utf-8")

    offenders = []
    for i, line in enumerate(src.splitlines(), start=1):
        if any(entity in line for entity in ENTITIES):
            if not any(re.search(p, line) for p in SANCTIONED_PATTERNS):
                offenders.append(f"  L{i}: {line.strip()}")

    assert not offenders, (
        "Entidades financieras en strings NO sancionados de ai_brain.py "
        "(¿string de usuario sin neutralizar? PASO 4 exige 'nuestro sistema'):\n"
        + "\n".join(offenders)
    )


def test_pending_question_has_no_entity():
    """
    [BOT-PLAN-FIX-HARDCODE-ENTITY-LEAK-007] T3 — Pin directo de la fuga
    erradicada: la pregunta pendiente de PHASE_2 (repetida textualmente al
    usuario por el FAQ brake block) no debe contener ninguna entidad.
    """
    cerebro = CerebroIA()
    question = cerebro._get_pending_funnel_question(
        "PHASE_2_HABEAS_DATA", {"moto_interest": "TVS RAIDER 125"}
    )
    for entity in ENTITIES:
        assert entity not in question, (
            f"La entidad '{entity}' reapareció en la pregunta pendiente de PHASE_2: {question!r}"
        )
