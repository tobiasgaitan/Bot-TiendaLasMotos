"""
AUD-FP-AUTO-007 — Deterministic forma_pago="Crédito" auto-fill on Habeas Data acceptance.

Pins:
  A: schema stable (create_prospect_if_missing initializes forma_pago="").
  B: acceptance at PASO 4 triggers deterministic auto-fill (via ALT-1 derivation
     layer in MemoryService.update_prospect_summary), only if vacant.
  C: acceptance without the legal script presented (e.g., "sí" at PASO 1) does
     NOT auto-fill.

6 unitarios + 1 e2e de reacción 👍 (7 ítems).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.memory_service import MemoryService


PHONE = "+573001234567"


def _build_real_ms_with_doc(current_data: dict):
    """Return a real MemoryService wired to a mocked Firestore document."""
    mock_db = MagicMock()
    ms = MemoryService(db=mock_db)

    snap = MagicMock()
    snap.exists = True
    snap.to_dict.return_value = current_data

    ref = MagicMock()
    ref.get = AsyncMock(return_value=snap)
    ref.set = AsyncMock()

    async def fake_get_ref(phone):
        return ref

    async def fake_firestore_io(coro, **kwargs):
        if hasattr(coro, "__await__"):
            return await coro
        return coro

    ms.get_ref = fake_get_ref
    ms._firestore_io = fake_firestore_io
    return ms, ref


def _build_reaction_buffer_mock():
    buffer = MagicMock()
    buffer.is_task_active = MagicMock(return_value=True)
    buffer.get_aggregated_message = AsyncMock(return_value=None)
    buffer.clear_buffer = AsyncMock()
    buffer.debounce_seconds = 0
    return buffer


def _reaction_payload():
    return {
        "from": "573001234567",
        "id": "wamid.fpa007",
        "type": "reaction",
        "phone_number_id": "12345",
        "reaction": {"message_id": "wamid.parent", "emoji": "👍"},
    }


# ── B-1: Aceptación PASO 4 + script presentado + vacío → "Crédito" ───────────

@pytest.mark.asyncio
async def test_forma_pago_autofill_on_habeas_acceptance():
    """
    R1 (transition False->True) + R2 (sent=True) + R3 (vacant) → Crédito.
    """
    ms, ref = _build_real_ms_with_doc(
        {
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": True,
            "forma_pago": "",
        }
    )
    await ms.update_prospect_summary(
        PHONE, "summary", {"habeas_data_accepted": True}
    )
    payload = ref.set.call_args[0][0]
    assert payload["forma_pago"] == "Crédito"
    assert payload["habeas_data_accepted"] is True


# ── B-2: Aceptación sin script presentado → SIN auto-fill (Pin C) ───────────

@pytest.mark.asyncio
async def test_forma_pago_no_autofill_when_script_not_sent():
    """
    R2 fails: current_data.habeas_data_accepted_sent is False → no fill.
    """
    ms, ref = _build_real_ms_with_doc(
        {
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": False,
            "forma_pago": "",
        }
    )
    await ms.update_prospect_summary(
        PHONE, "summary", {"habeas_data_accepted": True}
    )
    payload = ref.set.call_args[0][0]
    assert "forma_pago" not in payload


# ── B-3: Ya aceptado previamente → idempotente, no re-escribe ────────────────

@pytest.mark.asyncio
async def test_forma_pago_no_autofill_when_already_accepted():
    """
    R1 fails: current_data.habeas_data_accepted is True → transition consumed.
    """
    ms, ref = _build_real_ms_with_doc(
        {
            "habeas_data_accepted": True,
            "habeas_data_accepted_sent": True,
            "forma_pago": "",
        }
    )
    await ms.update_prospect_summary(
        PHONE, "summary", {"habeas_data_accepted": True}
    )
    payload = ref.set.call_args[0][0]
    assert "forma_pago" not in payload


# ── B-4: Extracción explícita "Contado" en mismo turno → gana ───────────────

@pytest.mark.asyncio
async def test_explicit_forma_pago_wins_over_autofill():
    """
    R3: same-turn explicit value takes precedence over derivation.
    """
    ms, ref = _build_real_ms_with_doc(
        {
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": True,
            "forma_pago": "",
        }
    )
    await ms.update_prospect_summary(
        PHONE, "summary", {"habeas_data_accepted": True, "forma_pago": "Contado"}
    )
    payload = ref.set.call_args[0][0]
    assert payload["forma_pago"] == "Contado"


# ── B-5: forma_pago ya poblado → no sobrescribe (explicit-wins forever) ────

@pytest.mark.asyncio
async def test_forma_pago_no_autofill_when_existing_valid():
    """
    R3: vacancy check fails because current_data has a valid "Contado".
    """
    ms, ref = _build_real_ms_with_doc(
        {
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": True,
            "forma_pago": "Contado",
        }
    )
    await ms.update_prospect_summary(
        PHONE, "summary", {"habeas_data_accepted": True}
    )
    payload = ref.set.call_args[0][0]
    assert "forma_pago" not in payload


# ── B-6: Sin aceptación (cambio normal) → SIN auto-fill ────────────────────

@pytest.mark.asyncio
async def test_forma_pago_no_autofill_without_acceptance():
    """
    R1 fails: no transition → no derivation.
    """
    ms, ref = _build_real_ms_with_doc(
        {
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": True,
            "forma_pago": "",
        }
    )
    await ms.update_prospect_summary(
        PHONE, "summary", {"nombre": "Juan"}
    )
    payload = ref.set.call_args[0][0]
    assert "forma_pago" not in payload


# ── B-7: E2E reacción 👍 → aceptación PASO 4 → "Crédito" en documento ───────

class _FakeMemoryModule:
    """Minimal module-like wrapper so whatsapp.memory_service_module.memory_service works."""
    def __init__(self, memory_service_instance):
        self.memory_service = memory_service_instance


@pytest.mark.asyncio
async def test_e2e_reaction_positive_autofill_forma_pago():
    """
    Pin B e2e: positive reaction intercept writes habeas_data_accepted + ponytail,
    and the MemoryService derivation layer materializes forma_pago="Crédito"
    in the Firestore payload (script already presented).
    """
    from app.routers import whatsapp as wa_module

    ms, ref = _build_real_ms_with_doc(
        {
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": True,
            "forma_pago": "",
        }
    )

    with patch.object(wa_module, "memory_service_module", _FakeMemoryModule(ms)), \
         patch.object(wa_module, "message_buffer", _build_reaction_buffer_mock()):
        result = await wa_module._pipeline_reaction_debounce(
            _reaction_payload(),
            user_phone=PHONE,
            msg_id_unique="wamid.fpa007",
            message_body="Sí",
            is_positive_reaction=True,
        )

    assert result == "Sí"
    assert ref.set.called, "Firestore set was never called"
    payload = ref.set.call_args[0][0]
    assert payload["habeas_data_accepted"] is True
    assert payload["forma_pago"] == "Crédito"
    assert payload["ponytail_status"] == "PENDING"
