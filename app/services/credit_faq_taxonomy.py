"""
[BOT-BUILD-REGRESSION-TRIAGE-COMPETENCIA-CUOTA-203/204]
Single Source of Truth (SSOT) for abstract credit FAQ classification and
multi-fragment turn intent.

This module decouples the classifier from both ai_brain.py and
agentic_loop_service.py so the credit-faq signal detection is evaluated
independently of generic FAQ keyword detection. Previously the credit
signals were nested inside `if is_faq_intent:`, which meant any token
present only in the credit taxonomy (e.g. historic/reportado/datacredito)
could never trigger the bypass on its own.

[BOT-BUILD-204] classify_credit_turn adds a deterministic turn-level view
that prevents the message buffer from poisoning a FAQ signal with an earlier
simulation fragment.
"""
from enum import Enum
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


class TurnIntent(str, Enum):
    """Deterministic intent classification for a credit turn."""
    NONE = "none"
    FAQ_ONLY = "faq_only"
    MIXED = "mixed"


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


def classify_credit_turn(fragments: List[str]) -> TurnIntent:
    """
    Classifies a user turn composed of one or more message fragments.

    Rules:
    - FAQ_ONLY: at least one fragment carries a raw FAQ signal and NO fragment
      requests a concrete simulation/quote.
    - MIXED: at least one fragment carries a raw FAQ signal AND at least one
      fragment requests a concrete simulation/quote. Both intentions are
      processed in the same turn (Intercepción y Retorno de FAQ).
    - NONE: no FAQ signal detected.

    Note: We inspect raw FAQ/NEGATIVE signals per fragment instead of relying on
    is_abstract_credit_faq() globally, because the latter would suppress a FAQ
    signal whenever a simulation token appears in the same blob (the exact bug
    in the message buffer aggregation).
    """
    if not fragments:
        return TurnIntent.NONE

    cleaned = [str(f).lower() for f in fragments if f]
    has_faq = any(
        any(s in f for s in FAQ_SIGNALS) for f in cleaned
    )
    has_negative = any(
        any(s in f for s in NEGATIVE_SIGNALS) for f in cleaned
    )

    if has_faq and has_negative:
        return TurnIntent.MIXED
    if has_faq:
        return TurnIntent.FAQ_ONLY
    return TurnIntent.NONE
