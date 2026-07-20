"""
[BOT-BUILD-REGRESSION-TRIAGE-COMPETENCIA-CUOTA-203/204]
[BOT-BUILD-CLASSIFIER-PAYLOAD-205] Hardened classifier to eradicate false positives
on commercial greetings and short ambiguous signals.
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

# Minimum text length to be considered a credit FAQ (filters greetings).
MIN_FAQ_LENGTH = 10

# [BOT-BUILD-205] Strong FAQ signals that are unambiguous on their own.
# These signals clearly indicate credit FAQ intent without needing confirmation.
STRONG_FAQ_SIGNALS: List[str] = [
    "codeudor", "codeudora", "fiador", "fiadores",
    "datacredito", "data credito", "historial",
    "experiencia crediticia", "reportado",
    "requisito",  # In motorcycle dealership context, "requisitos" is almost always about credit
]

# [BOT-BUILD-205] Weak FAQ signals that require confirmation context.
# These signals are ambiguous and can appear in non-credit contexts.
WEAK_FAQ_SIGNALS: List[str] = [
    "papel", "documento", "aval", "avales",
    "qué necesito", "que necesito", "qué piden", "que piden", "qué se necesita",
    "que se necesita", "qué debo llevar", "que debo llevar",
    "extranjero", "pasaporte", "cédula", "cedula",
    "necesito para", "se necesita para", "puedo sacar",
]

# [BOT-BUILD-205] Strong confirmation signals that validate credit intent.
# Required when text contains only weak signals.
FAQ_CONFIRMATION_SIGNALS: List[str] = [
    "crédito", "credito", "financiar", "financiación", "financiacion",
    "sacar", "obtener", "aplicar", "solicitud", "solicitar",
    "préstamo", "prestamo", "cuota", "mensualidad",
    "necesito", "necesita", "necesitan", "piden", "piden",
]

# Backward compatibility: FAQ_SIGNALS combines strong and weak signals.
FAQ_SIGNALS: List[str] = STRONG_FAQ_SIGNALS + WEAK_FAQ_SIGNALS

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
    
    [BOT-BUILD-205] Hardened with:
    - Minimum length validation (filters greetings like "hola")
    - Strong vs weak signal distinction (weak signals require confirmation)
    """
    if not text:
        return False
    
    # [BOT-BUILD-205] Minimum length filter to reject greetings
    if len(text.strip()) < MIN_FAQ_LENGTH:
        return False
    
    t = text.lower()
    has_negative = any(s in t for s in NEGATIVE_SIGNALS)
    
    if has_negative:
        return False
    
    # [BOT-BUILD-205] Check for strong signals (unambiguous on their own)
    has_strong = any(s in t for s in STRONG_FAQ_SIGNALS)
    if has_strong:
        return True
    
    # [BOT-BUILD-205] Check for weak signals + confirmation
    has_weak = any(s in t for s in WEAK_FAQ_SIGNALS)
    has_confirmation = any(s in t for s in FAQ_CONFIRMATION_SIGNALS)
    
    return has_weak and has_confirmation


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
    
    [BOT-BUILD-205] Hardened with minimum length and strong/weak signal validation.
    """
    if not fragments:
        return TurnIntent.NONE

    cleaned = [str(f).lower() for f in fragments if f]
    
    # [BOT-BUILD-205] Apply length filter and strong/weak signal validation
    def _has_valid_faq_signal(fragment: str) -> bool:
        if len(fragment.strip()) < MIN_FAQ_LENGTH:
            return False
        # Strong signals are unambiguous on their own
        has_strong = any(s in fragment for s in STRONG_FAQ_SIGNALS)
        if has_strong:
            return True
        # Weak signals require confirmation
        has_weak = any(s in fragment for s in WEAK_FAQ_SIGNALS)
        has_confirmation = any(s in fragment for s in FAQ_CONFIRMATION_SIGNALS)
        return has_weak and has_confirmation
    
    has_faq = any(_has_valid_faq_signal(f) for f in cleaned)
    has_negative = any(
        any(s in f for s in NEGATIVE_SIGNALS) for f in cleaned
    )

    if has_faq and has_negative:
        return TurnIntent.MIXED
    if has_faq:
        return TurnIntent.FAQ_ONLY
    return TurnIntent.NONE
