"""
[BOT-BUILD-REGRESSION-TRIAGE-COMPETENCIA-CUOTA-203]
Single Source of Truth (SSOT) for abstract credit FAQ classification.

This module decouples the classifier from both ai_brain.py and
agentic_loop_service.py so the credit-faq signal detection is evaluated
independently of generic FAQ keyword detection. Previously the credit
signals were nested inside `if is_faq_intent:`, which meant any token
present only in the credit taxonomy (e.g. historic/reportado/datacredito)
could never trigger the bypass on its own.
"""
from typing import List

# Stems / substrings that identify an abstract credit FAQ (requirements,
# documents, guarantor, credit history, foreigner docs, etc.).
FAQ_SIGNALS: List[str] = [
    "requisito", "papel", "documento", "codeudor", "fiador", "fiadores",
    "aval", "avales", "codeudora",
    "qué necesito", "que necesito", "qué piden", "que piden", "qué se necesita",
    "que se necesita", "qué debo llevar", "que debo llevar",
    "historial", "datacredito", "data credito", "reportado", "reporte",
    "experiencia crediticia", "necesito historial", "que piden",
    "extranjero", "ppt", "pep", "pasaporte", "cédula", "cedula",
    "necesito para", "se necesita para", "puedo sacar",
]

# Substrings that turn the query into a concrete simulation/quote request,
# therefore it must NOT be treated as an abstract FAQ.
NEGATIVE_SIGNALS: List[str] = [
    "cuota", "cuánto pago", "cuanto pago", "simul",
    "inicial de", "a 24", "a 36", "a 48", "a 12",
    "cuanto quedar", "cuánto quedar", "valor de la cuota",
]


def is_abstract_credit_faq(text: str) -> bool:
    """
    Deterministic classifier: user asks about credit requirements/documents/history
    WITHOUT requesting a specific cuota/simulation.
    Returns True only for abstract FAQ; False if user wants amounts.
    """
    if not text:
        return False
    t = text.lower()
    has_faq = any(s in t for s in FAQ_SIGNALS)
    has_negative = any(s in t for s in NEGATIVE_SIGNALS)
    return has_faq and not has_negative
