"""
[BOT-BUILD-COHERENCE-WAVE07-01-PROMPT-TOOLS-001] FAQ & Locations Knowledge Service.

Single Source of Truth (SSOT) for the static dealership knowledge previously
embedded in the system prompt's <KNOWLEDGE_BASE> block (<credit_matrix_rules>
and <locations>). The data now lives in the backend and is exposed to the LLM
through the `query_faq` and `query_locations` function-calling tools registered
in ai_brain.py.

WHY: Keeping this knowledge in the prompt invited hallucination and prompt
drift. As backend tools, answers are deterministic, testable and auditable.
"""
import unicodedata
from typing import Dict, List

# ---------------------------------------------------------------------------
# DATA — migrated VERBATIM from <credit_matrix_rules> (app/core/prompts.py)
# ---------------------------------------------------------------------------
FAQ_RULES: Dict[str, Dict[str, object]] = {
    "empleados": {
        "keywords": [
            "empleado", "empleados", "nomina", "salario",
        ],
        "answer": "Empleados: Requieren Cédula, email, celular. "
                  "(Si presentan solo Cédula, la inicial sugerida es 150%).",
    },
    "reportados": {
        "keywords": [
            "reportado", "reportados", "reporte", "datacredito", "data credito",
            "historial", "castigado", "mora",
        ],
        "answer": "Reportados: Requieren Cédula + 10% de inicial OBLIGATORIA.",
    },
    "extranjeros": {
        "keywords": [
            "extranjero", "extranjeros", "extranjeria", "ppt", "pep",
            "pasaporte", "venezolano", "migrante",
        ],
        "answer": "Extranjeros: Requieren PPT/PEP + Pasaporte + Dirección física.",
    },
    "brilla": {
        "keywords": [
            "brilla", "gas", "recibo", "recibos",
        ],
        "answer": "Brilla: Requieren Cédula + 2 últimos recibos de gas pagados.",
    },
}

# ---------------------------------------------------------------------------
# DATA — migrated VERBATIM from <locations> (app/core/prompts.py)
# ---------------------------------------------------------------------------
LOCATIONS: List[Dict[str, object]] = [
    {
        "name": "Santa Marta (11 Noviembre)",
        "address": "Calle 30 # 79-85",
        "link": "https://maps.app.goo.gl/xjRquwXZZiRaDyeU7",
        "keywords": ["santa marta", "11 noviembre", "once noviembre"],
    },
    {
        "name": "Santa Marta (Piragua)",
        "address": "Sector 1 Mz I Casa 4 L 4",
        "link": "https://maps.app.goo.gl/mnV22T9J5cUErZSx5",
        "keywords": ["santa marta", "piragua"],
    },
    {
        "name": "Santa Marta (Gaira)",
        "address": "Carrera 4 # 20-45",
        "link": "https://maps.app.goo.gl/FG6jFQKm1J1httLZ6",
        "keywords": ["santa marta", "gaira"],
    },
    {
        "name": "Riohacha",
        "address": "Calle 15 # 11A-12",
        "link": "https://maps.app.goo.gl/8fp1D2c2due6UHMo9",
        "keywords": ["riohacha", "rio hacha", "guajira"],
    },
    {
        "name": "Zona Bananera (Orihueca)",
        "address": "Calle 5 # 2-135",
        "link": "https://maps.app.goo.gl/1savLzhGmEfB3qDT6",
        "keywords": ["zona bananera", "orihueca", "bananera"],
    },
]


def _normalize(text: str) -> str:
    """Lowercases and strips accents so 'Cédula' matches 'cedula'."""
    nfkd = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def get_faq_answer(query: str) -> str:
    """
    Returns the official credit-requirements rule(s) matching the user query.
    If no specific topic is detected, returns the full credit matrix so the
    LLM can answer generic requirement questions without hallucinating.
    """
    normalized = _normalize(query)
    matches = [
        str(entry["answer"])
        for entry in FAQ_RULES.values()
        if any(k in normalized for k in entry["keywords"])  # type: ignore[attr-defined]
    ]
    if matches:
        return "\n".join(f"- {m}" for m in matches)
    return "\n".join(f"- {entry['answer']}" for entry in FAQ_RULES.values())


def get_location_info(query: str) -> str:
    """
    Returns address + Google Maps link for the store branch(es) matching the
    user query. If no specific branch/city is detected, returns all branches.
    """
    normalized = _normalize(query)
    matches = [
        loc for loc in LOCATIONS
        if any(k in normalized for k in loc["keywords"])  # type: ignore[attr-defined]
    ]
    if not matches:
        matches = LOCATIONS
    return "\n".join(
        f"- {loc['name']}: {loc['address']}. {loc['link']}" for loc in matches
    )
