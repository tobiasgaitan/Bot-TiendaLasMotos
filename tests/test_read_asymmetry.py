"""
test_read_asymmetry.py — Pruebas de Asimetría de Lectura (v7.7.0)

WHY este archivo fue reescrito:
  El refactor b4471b3 eliminó _get_prospect_data_sync y normalizó las llaves
  canónicas de Firestore de 'habeasData'/'serviciosPublicos' a 'habeas_data'/'servicios_publicos'.
  Los tests anteriores exigían la arquitectura pre-v7.7.0 y fallaban con:
    - AttributeError: '_get_prospect_data_sync'
    - KeyError: 'habeasData'

  Esta versión testea el contrato ACTUAL del MemoryService:
    - Firestore usa llaves en snake_case: habeas_data, servicios_publicos
    - get_prospect_data() (async) devuelve esas llaves directamente
    - create_prospect_if_missing() inicializa con 'habeas_data': False
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.memory_service import MemoryService


@pytest.fixture
def memory_service():
    mock_db = MagicMock()
    return MemoryService(db=mock_db)


@pytest.mark.asyncio
async def test_template_sanitization_initialization(memory_service):
    """
    Test Rule: TEMPLATE_SANITIZATION (v7.7.0)
    Verifica que create_prospect_if_missing usa SOLO llaves canónicas (habeas_data,
    servicios_publicos) y NO llaves legacy (habeasData, serviciosPublicos,
    habeas_data_accepted).

    WHY async: create_prospect_if_missing es un coroutine nativo desde v6.9.6.
    Llamarlo sin await no ejecuta el cuerpo y set() nunca se invoca.
    """
    # Mock: prospect does not exist
    mock_doc_snap = MagicMock()
    mock_doc_snap.exists = False

    mock_doc_ref = AsyncMock()
    mock_doc_ref.get.return_value = mock_doc_snap
    mock_doc_ref.set = AsyncMock()

    mock_session_ref = AsyncMock()
    mock_session_ref.delete = AsyncMock()

    def collection_side_effect(name):
        col_mock = MagicMock()
        if name == "prospectos":
            col_mock.document.return_value = mock_doc_ref
        elif name == "mensajeria":
            col_mock.document.return_value.collection.return_value.document.return_value = mock_session_ref
        return col_mock

    memory_service._db.collection.side_effect = collection_side_effect

    phone = "573001234567"
    await memory_service.create_prospect_if_missing(phone)

    mock_doc_ref.set.assert_called_once()
    sent_data = mock_doc_ref.set.call_args[0][0]

    # Canonical keys (v7.7.0)
    assert "habeas_data" in sent_data, "Must use canonical key 'habeas_data'"
    assert "servicios_publicos" in sent_data, "Must use canonical key 'servicios_publicos'"
    assert sent_data["habeas_data"] is False
    assert sent_data["servicios_publicos"] is None

    # Legacy keys must NOT exist in new prospects
    assert "habeasData" not in sent_data, "Legacy key 'habeasData' must not be written"
    assert "serviciosPublicos" not in sent_data, "Legacy key 'serviciosPublicos' must not be written"
    assert "habeas_data_accepted" not in sent_data, "Deprecated alias must not be written"


@pytest.mark.asyncio
async def test_reverse_mapping_retrieval(memory_service):
    """
    Test Rule: CANONICAL_READ (v7.7.0)
    Verifica que get_prospect_data() lee correctamente las llaves canónicas de
    Firestore y las retorna usando el mismo esquema snake_case.

    WHY renombrado desde REVERSE_MAPPING: La arquitectura v7.7.0 eliminó el
    mapeo bidireccional (habeasData <-> habeas_data_accepted). Ahora hay una
    sola llave canónica: 'habeas_data'.
    """
    mock_doc = MagicMock()
    mock_doc.exists = True
    # Firestore document with v7.7.0 canonical keys
    mock_doc.to_dict.return_value = {
        "habeas_data": True,
        "servicios_publicos": "Brilla",
        "nombre": "Test User",
        "habeas_data_sent": True,
    }

    mock_doc_ref = AsyncMock()
    mock_doc_ref.get.return_value = mock_doc

    # Mock _find_prospect_ref to bypass Firestore query
    memory_service._find_prospect_ref = AsyncMock(return_value=mock_doc_ref)

    result = await memory_service.get_prospect_data("573001234567")

    # Canonical read contract
    assert result["habeas_data"] is True, "habeas_data debe leerse directamente de Firestore"
    assert result["servicios_publicos"] == "Brilla"
    assert result["nombre"] == "Test User"
    assert result["exists"] is True

    # Legacy alias must NOT be produced by get_prospect_data
    assert "habeasData" not in result, "get_prospect_data no debe generar alias legacy"


@pytest.mark.asyncio
async def test_collision_neutralization_priority(memory_service):
    """
    Test Rule: LATCH_PREVAILS_ON_COLLISION (v7.7.0)
    Si Firestore tiene habeas_data=True, el merge debe mantener True incluso si
    la IA extrae habeas_data=False en la misma sesión.

    WHY: El latch en _merge_extracted_data (línea 279-285) garantiza que un campo
    que ya es True no pueda revertir a False — protección contra race conditions
    y extracción errónea de IA.
    """
    current_data = {
        "habeas_data": True,        # Canonical — already accepted
        "servicios_publicos": "Crediorbe"
    }
    incoming_data = {
        "habeas_data": False,       # AI attempts rollback — latch must block
        "servicios_publicos": None  # Empty — must not overwrite existing
    }

    merged = memory_service._merge_extracted_data(current_data, incoming_data)

    # Latch: canonical True must survive the False attempt
    assert merged["habeas_data"] is True, "El latch canónico debe prevalecer sobre la extracción errónea"
    # Existing servicios_publicos must not be overwritten by None
    assert "servicios_publicos" not in merged, "None no debe sobreescribir el valor existente válido"
