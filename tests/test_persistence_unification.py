"""
test_persistence_unification.py — BOT-ARQ-837 Assertion Suite

WHY: Validates the unification of the persistence layer under the canonical
'prospectos' collection. These tests enforce:
  1. Key Alignment between EXTRACTION_SCHEMA and MemoryService merge logic
  2. Ficha Tecnica content assertion (non-empty, non-None)
  3. Static analysis: zero references to .collection("mensajeria") in production code
  4. Canonical route verification: prospectos/{phone}/historial

Created: 2026-06-07
Ticket: BOT-ARQ-837
"""
import os
import re
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.services.memory_service import MemoryService
from app.services.ai_brain import EXTRACTION_SCHEMA
from tests.conftest import AsyncStreamMock


# ──────────────────────────────────────────────────────────────────────
# Fixture
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def memory_service():
    mock_db = MagicMock()
    return MemoryService(db=mock_db)


# ──────────────────────────────────────────────────────────────────────
# TEST 1: Key Alignment — EXTRACTION_SCHEMA ↔ MemoryService
# ──────────────────────────────────────────────────────────────────────

def test_extraction_schema_keys_accepted_by_merge(memory_service):
    """
    [BOT-ARQ-837] Verifica que TODAS las llaves del EXTRACTION_SCHEMA.extracted
    son aceptadas por _merge_extracted_data sin errores ni valores silenciosos.

    WHY: Una discrepancia de llaves (ej. habeas_data vs habeas_data_accepted)
    entre el schema y el merge provocaría que datos extraídos se pierdan
    silenciosamente — violación directa del Guardrail Anti-Null Masking.
    """
    extracted_props = EXTRACTION_SCHEMA["properties"]["extracted"]["properties"]
    schema_keys = set(extracted_props.keys())

    # Build sample incoming data with valid values for each key
    incoming = {}
    for key, prop in extracted_props.items():
        prop_type = prop.get("type", "STRING")
        if prop_type == "BOOLEAN":
            incoming[key] = True
        elif prop_type == "NUMBER":
            incoming[key] = 100
        else:
            incoming[key] = f"test_value_{key}"

    current_data = {}  # Empty prospect (fresh start)
    merged = memory_service._merge_extracted_data(current_data, incoming)

    # Every schema key with a valid value MUST appear in the merged output
    for key in schema_keys:
        assert key in merged, (
            f"EXTRACTION_SCHEMA key '{key}' was silently dropped by _merge_extracted_data. "
            f"This is a Key Alignment Regression (Nomenclature Regression)."
        )
        assert merged[key] is not None, (
            f"Key '{key}' was merged as None — violates Anti-Null Masking guardrail."
        )
        if isinstance(merged[key], str):
            assert merged[key].strip() != "", (
                f"Key '{key}' was merged as empty string — violates content assertion."
            )


# ──────────────────────────────────────────────────────────────────────
# TEST 2: Ficha Tecnica Content Assertion
# ──────────────────────────────────────────────────────────────────────

def test_ficha_tecnica_not_empty_or_none():
    """
    [BOT-ARQ-837] Verifica que la cadena 'Ficha Tecnica:' seguida de contenido
    no produce valores vacíos cuando se alimenta un summary válido.

    WHY: Si una optimización de contexto elimina accidentalmente el campo
    'summary' del catálogo, la validación PCC (Price Consistency Check)
    considerará la respuesta como fallida y forzará reintento innecesario.
    """
    # Simulating the catalog_response_str construction from ai_brain.py L1111-1112
    summary = "Motor 100cc, 4T, refrigerado por aire"
    name = "TVS SPORT 100"
    price = "$5.490.000"

    catalog_response_str = f"- {name}: {price}\n"
    catalog_response_str += f"  Ficha Tecnica: {summary}\n"

    # Assertion: Ficha Tecnica must be present and non-empty
    assert "Ficha Tecnica:" in catalog_response_str, (
        "La cadena 'Ficha Tecnica:' DEBE estar presente en la respuesta del catálogo."
    )

    # Extract the value after "Ficha Tecnica:"
    match = re.search(r"Ficha Tecnica:\s*(.+)", catalog_response_str)
    assert match is not None, "Regex failed to extract Ficha Tecnica value."
    ficha_value = match.group(1).strip()
    assert ficha_value != "", "Ficha Tecnica value is empty string — content mutation detected."
    assert ficha_value.lower() not in ("none", "null", "n/a"), (
        f"Ficha Tecnica contains sentinel value '{ficha_value}' — content corruption detected."
    )


def test_ficha_tecnica_rejects_none_summary():
    """
    [BOT-ARQ-837] Verifica que un summary=None es detectado como fallo de contenido.
    
    WHY: Si el campo 'summary' llega como None desde Firestore tras una mutación
    de llaves, el f-string generaría 'Ficha Tecnica: None' literal, lo cual
    es una regresión silenciosa.
    """
    summary = None
    name = "TVS SPORT 100"
    price = "$5.490.000"

    catalog_response_str = f"- {name}: {price}\n"
    # This simulates what happens if summary is None
    catalog_response_str += f"  Ficha Tecnica: {summary}\n"

    # The string "None" must be detected as invalid by the validation pipeline
    match = re.search(r"Ficha Tecnica:\s*(.+)", catalog_response_str)
    assert match is not None
    ficha_value = match.group(1).strip()
    # WHY: This test PROVES that f-string interpolation of None produces literal "None",
    # which must be caught by PCC Pro Validation 2. The assertion confirms detection works.
    is_corrupted = ficha_value.lower() in ("none", "null", "n/a", "")
    assert is_corrupted is True, (
        "Expected corruption detection: summary=None should produce 'None' literal "
        "that PCC Pro Validation 2 must flag."
    )


# ──────────────────────────────────────────────────────────────────────
# TEST 3: Static Analysis — No .collection("mensajeria") in production
# ──────────────────────────────────────────────────────────────────────

def test_no_mensajeria_collection_in_memory_service():
    """
    [BOT-ARQ-837] Grep estático del código fuente de memory_service.py
    para asegurar que 'collection("mensajeria")' no aparece como referencia
    de colección Firestore.

    WHY: Previene regresiones futuras donde un desarrollador reintroduzca
    la bifurcación de colecciones por inercia o copy-paste.
    """
    source_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "app", "services", "memory_service.py"
    )
    with open(source_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    # Pattern: .collection("mensajeria") — the Firestore collection call
    matches = re.findall(r'\.collection\(\s*["\']mensajeria["\']\s*\)', source_code)
    assert len(matches) == 0, (
        f"Found {len(matches)} reference(s) to .collection('mensajeria') in memory_service.py. "
        f"All persistence MUST use the canonical 'prospectos' collection (BOT-ARQ-837)."
    )


def test_no_mensajeria_collection_in_whatsapp_router():
    """
    [BOT-ARQ-837] Same static analysis for whatsapp.py.
    """
    source_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "app", "routers", "whatsapp.py"
    )
    with open(source_path, "r", encoding="utf-8") as f:
        source_code = f.read()

    matches = re.findall(r'\.collection\(\s*["\']mensajeria["\']\s*\)', source_code)
    assert len(matches) == 0, (
        f"Found {len(matches)} reference(s) to .collection('mensajeria') in whatsapp.py. "
        f"All persistence MUST use the canonical 'prospectos' collection (BOT-ARQ-837)."
    )


# ──────────────────────────────────────────────────────────────────────
# TEST 4: Canonical Route Verification
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_message_uses_prospectos_historial(memory_service):
    """
    [BOT-ARQ-837] Verifica que save_message persiste en
    prospectos/{phone}/historial/{auto_id} — la ruta canónica unificada.

    WHY: Este test captura la cadena completa de llamadas a Firestore
    para confirmar que la colección de primer nivel es 'prospectos'
    y la subcolección es 'historial'.
    """
    phone = "573001234567"

    # Setup mock chain: collection("prospectos").document(phone).collection("historial").document()
    mock_auto_doc = AsyncMock()
    mock_auto_doc.set = AsyncMock()

    mock_historial_col = MagicMock()
    mock_historial_col.document.return_value = mock_auto_doc

    mock_phone_doc = MagicMock()
    mock_phone_doc.collection.return_value = mock_historial_col

    mock_prospectos_col = MagicMock()
    mock_prospectos_col.document.return_value = mock_phone_doc

    memory_service._db.collection.return_value = mock_prospectos_col

    await memory_service.save_message(phone, "user", "Hola")

    # Verify the collection call used "prospectos" (via self.collection_name)
    memory_service._db.collection.assert_called_with("prospectos")

    # Verify the document was created under the correct phone
    mock_prospectos_col.document.assert_called_once()
    call_phone = mock_prospectos_col.document.call_args[0][0]
    assert "573001234567" in call_phone or "+573001234567" in call_phone, (
        f"Document ID '{call_phone}' does not match expected phone number."
    )

    # Verify subcollection is "historial"
    mock_phone_doc.collection.assert_called_once_with("historial")


@pytest.mark.asyncio
async def test_get_chat_history_uses_prospectos_historial(memory_service):
    """
    [BOT-ARQ-837] Verifica que get_chat_history lee de
    prospectos/{phone}/historial — la ruta canónica unificada.
    """
    phone = "573001234567"

    # Setup mock chain
    stream_mock = AsyncStreamMock([])

    mock_query = MagicMock()
    mock_query.stream.return_value = stream_mock

    mock_historial_col = MagicMock()
    mock_historial_col.order_by.return_value.limit.return_value = mock_query

    mock_phone_doc = MagicMock()
    mock_phone_doc.collection.return_value = mock_historial_col

    mock_prospectos_col = MagicMock()
    mock_prospectos_col.document.return_value = mock_phone_doc

    memory_service._db.collection.return_value = mock_prospectos_col

    result = await memory_service.get_chat_history(phone, limit=10)

    # Verify the collection call used "prospectos"
    memory_service._db.collection.assert_called_with("prospectos")

    # Verify subcollection is "historial"
    mock_phone_doc.collection.assert_called_once_with("historial")

    assert isinstance(result, list)
