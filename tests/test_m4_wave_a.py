"""
Wave A pins — M4-PLAN-FINAL-INTEGRATION-001 (A1-A4).

Covers:
- A1: forensic logs (catalog JSON, PCC, egress, Meta payload).
- A2: deterministic Visual-Lock V1 in egress.
- A3: generic moto_interest canonicalization (T1 + T5).
- A4: guards PEI-3/T2 updated to real CatalogService.search_catalog str signature.
"""
import re
import unicodedata
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers.whatsapp import _ensure_visual_lock, _pipeline_egress
from app.services.memory_service import MemoryService

PHONE_E164 = "+573192564288"
PHONE_NUMBER_ID = "999999"
MOTO_VICTORY = "Victory MRX 150"
MOTO_NTORQ = "TVS NTorq 125"
MOTO_RAIDER = "TVS Raider 125"
MOTO_URL = "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos.appspot.com/o/moto.png?alt=media"


class _FakeCatalog:
    """Minimal catalog stand-in for unit tests (no Firestore)."""

    def __init__(self, items):
        self._items = items

    @staticmethod
    def _normalize_item_id_key(raw: str) -> str:
        if not raw or not isinstance(raw, str):
            return ""
        s = unicodedata.normalize("NFKC", raw).lower().strip()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return s

    def search_items(self, query: str, trace_id: str = None):
        q = query.lower()
        matches = []
        for item in self._items:
            name = str(item.get("name", "")).lower()
            tags = [str(t).lower() for t in item.get("searchBy", [])]
            if q in name or any(q in t for t in tags):
                matches.append(item)
        return matches[:3]

    def search_catalog(self, query: str) -> str:
        return f"mock-catalog-markdown-for-{query}"


def _build_fake_catalog() -> _FakeCatalog:
    return _FakeCatalog([
        {"name": MOTO_VICTORY, "image_url": MOTO_URL, "price": "$8.500.000", "searchBy": ["doble proposito", "enduro"]},
        {"name": MOTO_NTORQ, "image_url": MOTO_URL, "price": "$7.200.000", "searchBy": ["automatica", "scooter"]},
        {"name": MOTO_RAIDER, "image_url": MOTO_URL, "price": "$9.000.000", "searchBy": ["sport"]},
    ])


def _build_memory_service(current_data: dict = None) -> MemoryService:
    ms = MemoryService.__new__(MemoryService)
    ms.collection_name = "prospectos"

    fake_snap = MagicMock()
    fake_snap.exists = True
    fake_snap.to_dict.return_value = current_data or {}

    async def _fake_io(coro, phone, label, timeout=None):
        if "doc_ref.set" in label:
            # Capture the merged payload for assertions.
            _fake_io.last_set = coro
            return MagicMock()
        return fake_snap

    ms._firestore_io = _fake_io
    ms._db = MagicMock()

    doc_ref = MagicMock()
    doc_ref.set = MagicMock(return_value=AsyncMock())
    ms.get_ref = AsyncMock(return_value=doc_ref)
    return ms


# -----------------------------------------------------------------------------
# A3 / T1: category query resolves to canonical model via catalog_moto_hint
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_interest_category_resolves_to_canonical_model():
    """T1: 'doble propósito' extraction overridden by tool hint 'Victory MRX 150'."""
    ms = _build_memory_service()
    catalog = _build_fake_catalog()

    await ms.update_prospect_summary(
        PHONE_E164,
        "",
        {"moto_interest": "doble propósito"},
        catalog_moto_hint=MOTO_VICTORY,
        catalog=catalog,
    )

    # The coro is doc_ref.set(update_payload, merge=True); unwrap MagicMock call.
    update_payload = ms.get_ref.return_value.set.call_args.args[0]
    assert update_payload.get("moto_interest") == MOTO_VICTORY
    assert update_payload.get("moto_interes") == MOTO_VICTORY


# -----------------------------------------------------------------------------
# A3 / T5: generic cases
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_moto_interest_generic_canonicalization_cases():
    """T5: automatica→NTorq, canonical preserved, no-match conservative."""
    ms = _build_memory_service()
    catalog = _build_fake_catalog()

    # Case 1: category 'automatica' resolves to NTorq via hint.
    await ms.update_prospect_summary(
        PHONE_E164, "", {"moto_interest": "automatica"},
        catalog_moto_hint=MOTO_NTORQ, catalog=catalog,
    )
    payload1 = ms.get_ref.return_value.set.call_args.args[0]
    assert payload1["moto_interest"] == MOTO_NTORQ

    # Case 2: already-canonical value is left untouched when no hint.
    ms2 = _build_memory_service(current_data={"moto_interest": MOTO_VICTORY})
    await ms2.update_prospect_summary(
        PHONE_E164, "", {"moto_interest": MOTO_VICTORY}, catalog=catalog,
    )
    payload2 = ms2.get_ref.return_value.set.call_args.args[0]
    assert payload2["moto_interest"] == MOTO_VICTORY

    # Case 3: non-canonical extracted value with no hint and empty DB is persisted conservatively.
    ms3 = _build_memory_service()
    await ms3.update_prospect_summary(
        PHONE_E164, "", {"moto_interest": "algo raro"}, catalog=catalog,
    )
    payload3 = ms3.get_ref.return_value.set.call_args.args[0]
    assert payload3["moto_interest"] == "algo raro"


# -----------------------------------------------------------------------------
# A2: deterministic Visual-Lock V1
# -----------------------------------------------------------------------------
def test_ensure_visual_lock_finds_image_when_markdown_missing():
    catalog = _build_fake_catalog()
    text = f"La {MOTO_VICTORY} cuesta $8.500.000. ¿Te interesa?"
    result = _ensure_visual_lock(text, {"moto_interest": MOTO_VICTORY}, catalog)
    assert result is not None
    assert result[0] == MOTO_URL
    assert result[1] == MOTO_VICTORY


def test_ensure_visual_lock_returns_none_when_markdown_present():
    catalog = _build_fake_catalog()
    text = f"La {MOTO_VICTORY} cuesta $8.500.000. ![{MOTO_VICTORY}]({MOTO_URL})"
    result = _ensure_visual_lock(text, {"moto_interest": MOTO_VICTORY}, catalog)
    assert result is None


@pytest.mark.asyncio
async def test_pipeline_egress_v1_injects_image_when_no_markdown():
    """V1: response has price + canonical moto but no Markdown → Strategy A."""
    catalog = _build_fake_catalog()
    mock_ms = MagicMock()
    mock_ms.save_message = AsyncMock()
    mock_image_sender = AsyncMock(return_value=True)
    mock_unified = AsyncMock(return_value=True)

    response_text = f"Te recomiendo la {MOTO_VICTORY} por $8.500.000. ¿Te gusta?"

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_unified):
        await _pipeline_egress(
            response_text,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"moto_interest": MOTO_VICTORY},
            catalog=catalog,
        )

    mock_image_sender.assert_awaited_once()
    args = mock_image_sender.await_args
    assert args.args[0] == PHONE_E164
    assert args.args[1] == MOTO_URL
    assert MOTO_VICTORY in args.kwargs["caption"]
    assert "$8.500.000" in args.kwargs["caption"]
    mock_unified.assert_not_called()
    mock_ms.save_message.assert_awaited_once_with(PHONE_E164, "model", response_text)


@pytest.mark.asyncio
async def test_pipeline_egress_v1_bypasses_when_markdown_present():
    """V1 must NOT double-send if the LLM already included Markdown."""
    catalog = _build_fake_catalog()
    mock_ms = MagicMock()
    mock_ms.save_message = AsyncMock()
    mock_image_sender = AsyncMock(return_value=True)
    mock_unified = AsyncMock(return_value=True)

    response_text = f"Te recomiendo la {MOTO_VICTORY} por $8.500.000. ![{MOTO_VICTORY}]({MOTO_URL})"

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp._send_whatsapp_image", mock_image_sender), \
         patch("app.routers.whatsapp._process_and_send_egress_message", mock_unified):
        await _pipeline_egress(
            response_text,
            user_phone=PHONE_E164,
            phone_number_id=PHONE_NUMBER_ID,
            prospect_data={"moto_interest": MOTO_VICTORY},
            catalog=catalog,
        )

    mock_image_sender.assert_not_called()
    mock_unified.assert_awaited_once()


# -----------------------------------------------------------------------------
# A1: forensic logs
# -----------------------------------------------------------------------------
def test_catalog_forensic_log_emits_image_url(caplog):
    import logging
    from unittest.mock import patch
    from app.services.catalog_service import CatalogService

    catalog = CatalogService()
    catalog._items = [
        {
            "id": "victory-mrx-150",
            "name": MOTO_VICTORY,
            "price": 8500000,
            "cc": 150,
            "category": "Urban",
            "searchBy": ["doble proposito"],
            "search_tokens": ["victory", "mrx", "150"],
            "search_text": "victory mrx 150 doble proposito",
            "description": "",
            "image_url": MOTO_URL,
            "bonusAmount": 0,
            "bonusEndDate": None,
        }
    ]
    catalog._category_aliases = {}
    catalog._class_category_aliases = {}

    caplog.set_level(logging.INFO, logger="app.services.catalog_service")
    with patch("app.services.config_service.config_service") as mock_cfg:
        mock_cfg.get_registration_cost.return_value = 0
        catalog.search_items(MOTO_VICTORY, trace_id="turn-123")
    assert any("📦 [CATALOG-FORENSIC]" in r.message for r in caplog.records)
    assert any("Victory MRX 150" in r.message and MOTO_URL in r.message for r in caplog.records)


def test_pcc_forensic_log_emits_with_trace_id(caplog):
    from app.services.agentic_loop_service import AgenticOrchestrator
    orch = AgenticOrchestrator()
    with caplog.at_level("INFO"):
        orch.run_checker(
            "La Victory MRX 150 cuesta $8.500.000",
            is_catalog_query=True,
            prospect_data={"phone": PHONE_E164, "moto_interest": MOTO_VICTORY},
            user_prompt="doble propósito",
            trace_id="turn-123",
        )
    assert any("🔍 [PCC-FORENSIC]" in r.message and "turn-123" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_meta_payload_log_emits_info(caplog):
    from app.services.whatsapp_service import WhatsAppService

    service = WhatsAppService.__new__(WhatsAppService)
    service.phone_number_id = PHONE_NUMBER_ID
    service.headers = {"Authorization": "Bearer test"}

    class _FakeResponse:
        status_code = 200
        def json(self):
            return {"messages": [{"id": "wamid.test"}]}
        def raise_for_status(self):
            return None

    class _FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, headers=None, json=None, timeout=None):
            return _FakeResponse()

    with caplog.at_level("INFO"), patch("app.services.whatsapp_service.httpx.AsyncClient", return_value=_FakeClient()):
        await service.send_image_message(PHONE_E164, MOTO_URL, caption="Mira", phone_number_id=PHONE_NUMBER_ID)

    assert any("📤 [META-PAYLOAD]" in r.message and "phone_number_id" in r.message for r in caplog.records)
    assert any("✅ [META-PAYLOAD]" in r.message and "wamid.test" in r.message for r in caplog.records)


# -----------------------------------------------------------------------------
# Fix B / PIN-014-B1: reset_phase_latches zeros latches preserving identity
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reset_phase_latches_zeros_latches_preserves_identity_and_history():
    """PIN-014-B1: phase latches reset; nombre/ciudad and historial untouched."""
    ms = _build_memory_service(current_data={
        "nombre": "Tobias",
        "ciudad": "Bogota",
        "moto_interest": "doble propósito",
        "moto_interes": "doble propósito",
        "habeas_data_accepted": True,
        "habeas_data_accepted_sent": True,
        "forma_pago": "Crédito",
        "moto_confirmada": True,
        "score_resultado": "750",
    })

    await ms.reset_phase_latches(PHONE_E164)

    payload = ms.get_ref.return_value.set.call_args.args[0]
    assert payload["habeas_data_accepted"] is False
    assert payload["habeas_data_accepted_sent"] is False
    assert payload["habeas_data"] is False
    assert payload["habeas_data_sent"] is False
    assert payload["forma_pago"] == ""
    assert payload["moto_interest"] == ""
    assert payload["moto_interes"] == ""
    assert payload["moto_confirmada"] is False
    assert payload["score_resultado"] == ""
    assert payload["reset_by"] == "system_reset_command"
    assert "reset_at" in payload
    # Identity and history must NOT be touched by this method
    assert "nombre" not in payload
    assert "ciudad" not in payload


# -----------------------------------------------------------------------------
# Fix B / PIN-014-B2: delete=False -> reset + differentiated feedback + warning
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reset_handler_differentiated_feedback_when_delete_fails(caplog):
    """PIN-014-B2: delete_prospect_completely=False still resets latches and warns."""
    import logging
    from fastapi import BackgroundTasks
    from app.routers.whatsapp import _handle_message_background_impl

    caplog.set_level(logging.WARNING, logger="app.routers.whatsapp")

    mock_bg_tasks = BackgroundTasks()

    mock_ms = MagicMock()
    mock_ms.delete_prospect_completely = AsyncMock(return_value=False)
    mock_ms.reset_phase_latches = AsyncMock()
    mock_ms.create_prospect_if_missing = AsyncMock()
    mock_ms.update_last_interaction = AsyncMock()
    mock_ms.transition_to_in_progress = AsyncMock()
    mock_ms.generate_and_update_summary = AsyncMock()
    mock_ms.save_message = AsyncMock()
    mock_ms.get_prospect_data = AsyncMock(return_value={"exists": False})
    mock_ms.get_or_create_prospect = AsyncMock(return_value={
        "exists": True, "status": "PENDING", "chatbot_status": "ACTIVE"
    })
    mock_ms.get_chat_history = AsyncMock(return_value=[])
    mock_ms.claim_webhook_idempotency = AsyncMock(return_value=True)
    mock_ms.release_webhook_claim = AsyncMock()

    mock_whatsapp = MagicMock()
    mock_whatsapp.mark_as_read = AsyncMock()
    mock_whatsapp.send_text_message = AsyncMock()

    mock_catalog = MagicMock()
    mock_catalog.search = MagicMock(return_value=[])
    mock_catalog.get_all_items = MagicMock(return_value=[])

    mock_message_buffer = AsyncMock()
    mock_message_buffer.add_message = AsyncMock(return_value=True)
    mock_message_buffer.clear_messages = AsyncMock()
    mock_message_buffer.get_aggregated_message = MagicMock(return_value=None)
    mock_message_buffer.is_task_active = MagicMock(return_value=True)
    mock_message_buffer.clear_buffer = AsyncMock()
    mock_message_buffer.debounce_seconds = 0.01

    with patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
         patch("app.routers.whatsapp.CerebroIA", return_value=MagicMock()), \
         patch("app.routers.whatsapp.judge_service", MagicMock()), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_whatsapp), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.message_buffer", mock_message_buffer), \
         patch("app.routers.whatsapp.db", MagicMock()):

        msg_payload = {
            "from": "573192564288",
            "id": "wamid.reset_b2",
            "type": "text",
            "phone_number_id": "999999",
            "text": "/reset"
        }
        await _handle_message_background_impl(msg_payload, mock_bg_tasks)

    mock_ms.delete_prospect_completely.assert_awaited_once_with(PHONE_E164)
    mock_ms.reset_phase_latches.assert_awaited_once_with(PHONE_E164)
    mock_whatsapp.send_text_message.assert_awaited_once()
    args = mock_whatsapp.send_text_message.await_args
    assert args.args[0] == PHONE_E164
    assert "reiniciada" in args.args[1]
    assert "por completo" not in args.args[1]
    assert any("delete_prospect_completely returned False" in r.message for r in caplog.records)


# -----------------------------------------------------------------------------
# PIN-014-E2E: /reset -> "doble propósito a crédito" permanece en PHASE_1
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pin_014_e2e_reset_then_category_credit_stays_phase_1_with_recommendation(caplog):
    """[BOT-BUILD-FUNNEL-SKIP-014 PIN-014-E2E]

    Escenario íntegro del incidente (diseño certificado C-9):
    1. /reset: reset_phase_latches REAL zero los latches de fase de un prospecto
       con embudo completo (habeas aceptado+enviado, forma_pago, moto, score).
    2. Turno post-reset "Hola, quisiera una moto doble propósito a crédito" con
       CerebroIA REAL + catálogo mockeado (CatalogService con _items en memoria)
       y Gemini scriptado (function_call search_catalog -> texto final).
    Aserciones del pin:
    - search_catalog invocada (dispatcher -> catalog.search_items) y su payload
      con el modelo canónico viaja de vuelta a Gemini.
    - Log forense [CATALOG-FORENSIC] presente.
    - funnel_phase == "PHASE_1_PROFILING" en TODAS las evaluaciones del turno
      (la compuerta canónica jamás deja saltar a PHASE_2 con categoría
      libre-texto post-reset).
    - Respuesta con precio ($\\d+) o instrucción de recomendación; NUNCA script
      de Habeas (sin link de privacidad ni solicitud de tratamiento de datos).
    """
    import logging
    from app.services.ai_brain import CerebroIA
    from app.services.catalog_service import CatalogService

    caplog.set_level(logging.INFO, logger="app.services.catalog_service")

    # --- Paso 1: /reset real sobre prospecto con embudo completo -------------
    pre_reset_state = {
        "nombre": "Tobias",
        "ciudad": "Bogota",
        "moto_interest": "Victory MRX 150",
        "moto_interes": "Victory MRX 150",
        "moto_confirmada": True,
        "forma_pago": "Crédito",
        "habeas_data_accepted": True,
        "habeas_data_accepted_sent": True,
        "habeas_data": True,
        "habeas_data_sent": True,
        "score_resultado": "750",
    }
    ms = _build_memory_service(current_data=dict(pre_reset_state))
    reset_ok = await ms.reset_phase_latches(PHONE_E164)
    assert reset_ok is True
    reset_payload = ms.get_ref.return_value.set.call_args.args[0]
    assert reset_payload["habeas_data_accepted"] is False
    assert reset_payload["moto_interest"] == ""
    assert reset_payload["forma_pago"] == ""

    # Documento post-reset = pre-estado mergeado con el payload aplicado (C-8).
    post_reset = {**pre_reset_state, **reset_payload}
    post_reset.pop("reset_at", None)
    post_reset.pop("reset_by", None)
    post_reset["exists"] = True
    post_reset["phone"] = PHONE_E164

    # --- Paso 2: catálogo mockeado (CatalogService real, ítems en memoria) ---
    catalog = CatalogService()
    catalog._items = [
        {
            "id": "victory-mrx-150",
            "name": MOTO_VICTORY,
            "price": 8500000,
            "cc": 150,
            "category": "Enduro",
            "searchBy": ["doble", "proposito", "enduro"],
            "search_tokens": ["victory", "mrx", "150", "doble", "proposito"],
            "search_text": "victory mrx 150 doble proposito enduro",
            "description": "Moto doble propósito",
            "image_url": MOTO_URL,
            "bonusAmount": 0,
            "bonusEndDate": None,
        }
    ]
    catalog._category_aliases = {}
    catalog._class_category_aliases = {}
    search_spy = MagicMock(wraps=catalog.search_items)
    catalog.search_items = search_spy

    cerebro = CerebroIA(catalog_service=catalog)
    cerebro.client = MagicMock()

    # Spy de fase: registra cada evaluación de _determine_funnel_phase del turno.
    evaluated_phases = []
    _orig_determine = cerebro._determine_funnel_phase

    def _phase_spy(*args, **kwargs):
        phase = _orig_determine(*args, **kwargs)
        evaluated_phases.append(phase)
        return phase

    cerebro._determine_funnel_phase = _phase_spy

    # --- Gemini scriptado: 1) function_call search_catalog, 2) texto final ---
    def _make_fc_response(tool_name, tool_args):
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = None
        fc = MagicMock()
        fc.name = tool_name
        fc.args = tool_args
        mock_part.function_call = fc
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.total_token_count = 100
        return mock_response

    def _make_text_response(text):
        mock_response = MagicMock()
        mock_part = MagicMock()
        mock_part.text = text
        mock_part.function_call = None
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [mock_part]
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.total_token_count = 100
        return mock_response

    user_text = "Hola, quisiera una moto doble propósito a crédito"
    scripted_final_text = (
        "¡Hola! Qué gusto saludarte. Para uso doble propósito te recomiendo la "
        f"{MOTO_VICTORY} por $8.500.000. ![{MOTO_VICTORY}]({MOTO_URL})\n\n"
        "Ficha Tecnica: Motor doble propósito, perfecto para ciudad y campo. "
        "¿con quién tengo el gusto?"
    )
    scripted_responses = [
        _make_fc_response("search_catalog", {"query": "doble propósito"}),
        _make_text_response(scripted_final_text),
    ]
    sent_payloads = []

    async def _send(*args, **kwargs):
        if args:
            sent_payloads.append(args[0])
        return scripted_responses.pop(0)

    mock_chat = MagicMock()
    mock_chat.send_message = AsyncMock(side_effect=_send)
    cerebro.client.aio.chats.create.return_value = mock_chat

    history = [{"role": "user", "content": user_text}]
    with patch("app.services.config_service.config_service") as mock_cfg:
        mock_cfg.get_registration_cost.return_value = 0
        mock_cfg.get_catalog_aliases.return_value = {}
        result = await cerebro.pensar_respuesta(
            texto=user_text,
            prospect_data=post_reset,
            history=history,
        )

    # --- Aserciones del pin ---------------------------------------------------
    # 1. search_catalog invocada: el dispatcher ejecutó catalog.search_items y
    #    el resultado canónico viajó de vuelta a Gemini en el function response.
    search_spy.assert_called_once()
    assert "doble" in str(search_spy.call_args.args[0]).lower()
    assert len(sent_payloads) == 2, "Debe existir el turno tool-response tras search_catalog."
    tool_turn_payload = str(sent_payloads[1])
    assert MOTO_VICTORY in tool_turn_payload
    assert "$8.500.000" in tool_turn_payload

    # 2. Log forense del catálogo presente.
    assert any("📦 [CATALOG-FORENSIC]" in r.message for r in caplog.records)

    # 3. funnel_phase == PHASE_1_PROFILING en todas las evaluaciones del turno.
    assert evaluated_phases, "_determine_funnel_phase debió ejecutarse al menos una vez."
    assert all(p == "PHASE_1_PROFILING" for p in evaluated_phases), (
        f"Compuerta canónica violada: fases evaluadas = {evaluated_phases}"
    )

    # 4. Respuesta con precio ($\d+) o instrucción de recomendación; NUNCA
    #    script de Habeas.
    has_price = bool(re.search(r"\$\d+", result or ""))
    recommendation_instruction = "INVOCA search_catalog" in str(sent_payloads[0])
    assert has_price or recommendation_instruction, (
        "La respuesta debe recomendar con precio o portar la instrucción de recomendación."
    )
    assert "politica-de-privacidad" not in result
    assert "tratamiento de datos" not in result.lower()
    assert "política de privacidad" not in result.lower()
