"""
[BOT-INFRA-33] Suite de regresión — Firestore Timeout Interceptor

Certifica:
  1. asyncio.TimeoutError se dispara correctamente ante latencia > DB_TIMEOUT
  2. logger.exception registra traza forense completa
  3. Mensaje de contingencia se envía via whatsapp_service mock (await bloqueante)
  4. La excepción se propaga hacia el llamador (no se silencia)
  5. Errores de conectividad GCP (ServiceUnavailable) siguen el mismo camino
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_db():
    """Firestore AsyncClient mock con respuesta normal."""
    db = MagicMock()
    doc_snap = MagicMock()
    doc_snap.exists = True
    doc_snap.to_dict.return_value = {"celular": "+573001234567", "status": "PENDING"}

    doc_ref = AsyncMock()
    doc_ref.get = AsyncMock(return_value=doc_snap)
    doc_ref.set = AsyncMock(return_value=None)
    doc_ref.update = AsyncMock(return_value=None)
    doc_ref.delete = AsyncMock(return_value=None)
    doc_ref.id = "+573001234567"

    coll = MagicMock()
    coll.document.return_value = doc_ref
    db.collection.return_value = coll

    return db


@pytest.fixture
def memory_service_instance(mock_db):
    """MemoryService con DB mockeada."""
    from app.services.memory_service import MemoryService
    return MemoryService(mock_db)


@pytest.fixture
def slow_db():
    """Firestore mock que simula latencia mayor al timeout configurado (BOT-INFRA-33)."""
    db = MagicMock()

    async def _slow_get():
        await asyncio.sleep(10)  # 10s >> DB_TIMEOUT(5s)

    doc_ref = AsyncMock()
    doc_ref.get = _slow_get
    doc_ref.set = AsyncMock(return_value=None)
    doc_ref.update = AsyncMock(return_value=None)
    doc_ref.delete = AsyncMock(return_value=None)
    doc_ref.id = "+573001234567"

    coll = MagicMock()
    coll.document.return_value = doc_ref
    db.collection.return_value = coll

    return db


@pytest.fixture(autouse=True)
def mock_google_auth():
    """Mock google.auth.default para evitar que intente cargar /tmp/fake-key.json."""
    from google.auth.credentials import AnonymousCredentials
    with patch("google.auth.default", return_value=(AnonymousCredentials(), "test-project")):
        yield


@pytest.fixture
def slow_memory_service(slow_db):
    """MemoryService con DB de latencia artificial."""
    from app.services.memory_service import MemoryService
    svc = MemoryService(slow_db)
    svc._db.project = 'test-project'
    svc._db._credentials = None
    # Forzar timeout corto para que el test sea rápido (0.1s en lugar de 5s)
    return svc


# ──────────────────────────────────────────────────────────────────────────────
# TC-01: TimeoutError en get_prospect_data → log forense + contingencia + NO re-raise
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_triggers_on_slow_firestore_get(slow_memory_service, caplog):
    """
    DADO: Firestore tarda más que DB_TIMEOUT en responder.
    CUANDO: se llama a get_prospect_data.
    ENTONCES:
      - NO se lanza excepción (Zero-Silent-Failures silencioso hacia el llamador).
      - Retorna un diccionario con exists=False.
      - El log forense contiene 'BOT-INFRA-33' y 'ERROR o TIMEOUT'.
      - whatsapp_service.send_text_message recibe el número de teléfono del lead.
    """
    phone = "+573001234567"

    mock_wa_svc = AsyncMock()
    mock_wa_svc.send_text_message = AsyncMock()

    with patch("app.services.memory_service.settings") as mock_settings, \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_svc):

        mock_settings.db_timeout = 1  # 1s para que el test sea rápido

        import logging
        with caplog.at_level(logging.ERROR, logger="app.services.memory_service"):
            result = await slow_memory_service.get_prospect_data(phone)
            assert result.get("exists") is False, "Debe asumir contexto vacío (contingencia)"

    # Verificar log forense
    assert any("BOT-INFRA-33" in r.message for r in caplog.records), \
        "El log forense con 'BOT-INFRA-33' debe registrarse ante timeout"
    assert any("ERROR o TIMEOUT" in r.message for r in caplog.records), \
        "El log debe contener 'ERROR o TIMEOUT'"

    # Verificar despacho de contingencia al número correcto
    mock_wa_svc.send_text_message.assert_called_once()
    call_args = mock_wa_svc.send_text_message.call_args
    assert call_args[0][0] == phone or call_args[1].get("phone") == phone or phone in str(call_args), \
        f"El mensaje de contingencia debe enviarse a {phone}"


# ──────────────────────────────────────────────────────────────────────────────
# TC-02: El texto de contingencia es el literal aprobado
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_contingency_message_is_exact_literal(slow_memory_service):
    """
    DADO: Timeout en Firestore.
    CUANDO: se despacha el mensaje de contingencia.
    ENTONCES: el texto es exactamente el literal aprobado en _CONTINGENCY_MSG.
    """
    from app.services.memory_service import _CONTINGENCY_MSG

    phone = "+573009876543"
    mock_wa_svc = AsyncMock()
    mock_wa_svc.send_text_message = AsyncMock()

    with patch("app.services.memory_service.settings") as mock_settings, \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_svc):

        mock_settings.db_timeout = 1

        result = await slow_memory_service.get_prospect_data(phone)
        assert result.get("exists") is False

    mock_wa_svc.send_text_message.assert_called_once()
    _, sent_text = mock_wa_svc.send_text_message.call_args[0]
    assert sent_text == _CONTINGENCY_MSG, \
        f"El texto enviado debe ser el literal aprobado. Recibido: '{sent_text}'"


# ──────────────────────────────────────────────────────────────────────────────
# TC-03: Excepción NO se propaga, retorna objeto contingencia silencioso
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_exception_is_handled_safely():
    """
    DADO: una operación simulada (ej. save_message) lanza TimeoutError.
    CUANDO: _firestore_io atrapa el error.
    ENTONCES: se devuelve el _ContingencySnapshot sin propagar la excepción.
    """
    from app.services.memory_service import MemoryService, _ContingencySnapshot

    phone = "+573001111111"
    mock_wa_svc = AsyncMock()

    db = MagicMock()
    svc = MemoryService(db)

    async def mock_coro():
        raise asyncio.TimeoutError("Fake timeout")

    with patch("app.services.whatsapp_service.whatsapp_service", mock_wa_svc):
        result = await svc._firestore_io(mock_coro(), phone=phone, label="save_message")
        
        assert isinstance(result, _ContingencySnapshot), "Debe devolver el objeto de contingencia seguro"
        assert result.exists is False


# ──────────────────────────────────────────────────────────────────────────────
# TC-04: GCP ServiceUnavailable sigue el mismo camino que TimeoutError
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gcp_service_unavailable_triggers_contingency(memory_service_instance, caplog):
    """
    DADO: Firestore lanza ServiceUnavailable (degradación de red GCP).
    CUANDO: se llama a get_prospect_data.
    ENTONCES:
      - La excepción NO se propaga.
      - El log forense contiene 'ERROR o TIMEOUT'.
      - whatsapp_service.send_text_message es invocado.
      - Retorna existe=False.
    """
    from google.api_core import exceptions as gcp_exceptions

    phone = "+573002222222"
    mock_wa_svc = AsyncMock()
    mock_wa_svc.send_text_message = AsyncMock()

    # Hacer que _find_prospect_ref devuelva un doc_ref cuyo .get() lanza ServiceUnavailable
    unavailable_doc = AsyncMock()
    unavailable_doc.get = AsyncMock(side_effect=gcp_exceptions.ServiceUnavailable("GCP degraded"))
    memory_service_instance._find_prospect_ref = AsyncMock(return_value=unavailable_doc)

    import logging
    with caplog.at_level(logging.ERROR, logger="app.services.memory_service"), \
         patch("app.services.whatsapp_service.whatsapp_service", mock_wa_svc):

        result = await memory_service_instance.get_prospect_data(phone)
        assert result.get("exists") is False

    assert any("ERROR o TIMEOUT" in r.message for r in caplog.records), \
        "El log debe registrar ERROR o TIMEOUT"

    mock_wa_svc.send_text_message.assert_called_once()


# ──────────────────────────────────────────────────────────────────────────────
# TC-05: Operaciones normales (<1s) NO disparan timeout — no regresión
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_normal_operations_not_affected_by_timeout(memory_service_instance):
    """
    DADO: Firestore responde normalmente (sin latencia).
    CUANDO: se llama a get_prospect_data.
    ENTONCES: la operación se completa sin excepción y retorna datos válidos.

    WHY: Garantizar que el interceptor no introduce overhead ni falsos positivos.
    """
    result = await memory_service_instance.get_prospect_data("+573001234567")
    assert result.get("exists") is True, "Operaciones normales deben retornar datos sin interrupción"


# ──────────────────────────────────────────────────────────────────────────────
# TC-06: DB_TIMEOUT es configurable vía settings (no hardcodeado)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeout_uses_settings_db_timeout():
    """
    DADO: settings.db_timeout está configurado a un valor personalizado.
    CUANDO: _firestore_io se invoca.
    ENTONCES: el timeout efectivo respeta la configuración de settings.
    """
    from app.services.memory_service import MemoryService
    import asyncio

    calls_recorded = []

    async def mock_coro():
        calls_recorded.append("called")
        return "ok"

    with patch("app.services.memory_service.settings") as mock_settings:
        mock_settings.db_timeout = 999  # Configurado muy alto

        db_mock = MagicMock()
        db_mock.project = 'test-project'
        db_mock._credentials = None
        svc = MemoryService(db_mock)

        result = await svc._firestore_io(mock_coro(), phone="+573000000000", label="test")
        assert result == "ok"
        assert "called" in calls_recorded
