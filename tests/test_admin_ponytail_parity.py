"""
Pins de Paridad Ponytail en vía Admin — [M3-DEUDA-VIVA-001 / DV-2]

Invariante BOT-PONYTAIL-200: la activación de `human_help_requested` debe
despriorizar el ponytail (campo `ponytail_status` = "DEPRIORITIZED") en paridad
byte/valor con la vía router (`_mark_ponytail_deprioritized`, whatsapp.py L688,
pineada por CH-4 en tests/test_characterization_etapa1.py).

La vía admin (`_set_human_help_status_direct`, autosuficiente y síncrona) inyecta
el campo/valor canónico en el MISMO payload Firestore (commit atómico
flag+ponytail), SOLO en activación (status=True). En reanudación (status=False)
no se toca `ponytail_status`: la vía router no tiene flujo de reanudación.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.routers import admin
from app.routers.admin import _set_human_help_status_direct

PHONE_RAW = "573192564288"


def _build_firestore_mock(doc_exists: bool, legacy_hit: bool):
    """Firestore mockeado para las 3 ramas del helper admin.

    Devuelve (mock_db, doc_ref, legacy_doc): doc_ref captura el update/set de la
    rama de ID directo y de la rama de creación; legacy_doc captura el update de
    la rama de query por campo `celular`.
    """
    mock_db = MagicMock()
    prospectos_ref = mock_db.collection.return_value

    # ATTEMPT 1: lookup por ID directo (y ref de creación si no existe).
    doc_ref = prospectos_ref.document.return_value
    doc_ref.get.return_value.exists = doc_exists

    # ATTEMPT 2 (fallback): query por campo `celular`.
    legacy_doc = MagicMock()
    prospectos_ref.where.return_value.limit.return_value.get.return_value = (
        [legacy_doc] if legacy_hit else []
    )
    return mock_db, doc_ref, legacy_doc


def _run_helper(mock_db, status: bool) -> None:
    with patch.object(admin, "firestore") as mock_firestore:
        mock_firestore.Client.return_value = mock_db
        _set_human_help_status_direct(PHONE_RAW, status)


def _single_payload(write_mock) -> dict:
    write_mock.assert_called_once()
    return write_mock.call_args[0][0]


# ── DV-2-PIN-1: rama doc directo ──────────────────────────────────────────────

def test_dv2_direct_doc_activation_deprioritizes_ponytail():
    """DV-2-PIN-1: activación (status=True) vía doc directo inyecta
    ponytail_status=DEPRIORITIZED en el mismo payload (paridad CH-4)."""
    mock_db, doc_ref, _ = _build_firestore_mock(doc_exists=True, legacy_hit=False)
    _run_helper(mock_db, status=True)

    payload = _single_payload(doc_ref.update)
    assert payload["human_help_requested"] is True
    assert payload["ponytail_status"] == "DEPRIORITIZED", (
        f"Falta despriorizado ponytail (BOT-PONYTAIL-200) en rama directa: {payload}"
    )


# ── DV-2-PIN-2: rama legacy query ─────────────────────────────────────────────

def test_dv2_legacy_query_activation_deprioritizes_ponytail():
    """DV-2-PIN-2: activación (status=True) vía legacy query inyecta
    ponytail_status=DEPRIORITIZED en el mismo payload (paridad CH-4)."""
    mock_db, _, legacy_doc = _build_firestore_mock(doc_exists=False, legacy_hit=True)
    _run_helper(mock_db, status=True)

    payload = _single_payload(legacy_doc.reference.update)
    assert payload["human_help_requested"] is True
    assert payload["ponytail_status"] == "DEPRIORITIZED", (
        f"Falta despriorizado ponytail (BOT-PONYTAIL-200) en rama legacy: {payload}"
    )


# ── DV-2-PIN-3: rama creación de documento ────────────────────────────────────

def test_dv2_create_new_doc_activation_deprioritizes_ponytail():
    """DV-2-PIN-3: el prospecto creado con handoff activo nace con
    ponytail_status=DEPRIORITIZED desde el primer commit."""
    mock_db, doc_ref, _ = _build_firestore_mock(doc_exists=False, legacy_hit=False)
    _run_helper(mock_db, status=True)

    payload = _single_payload(doc_ref.set)
    assert payload["human_help_requested"] is True
    assert payload["ponytail_status"] == "DEPRIORITIZED", (
        f"Falta despriorizado ponytail (BOT-PONYTAIL-200) en rama creación: {payload}"
    )
    assert payload["celular"]


# ── DV-2-PIN-4: no-regresión de reanudación ───────────────────────────────────

def test_dv2_resume_never_touches_ponytail():
    """DV-2-PIN-4: reanudación (status=False) NO escribe ponytail_status en
    ninguna rama (la vía router no tiene flujo de reanudación que replicar)."""
    for doc_exists, legacy_hit in [(True, False), (False, True), (False, False)]:
        mock_db, doc_ref, legacy_doc = _build_firestore_mock(
            doc_exists=doc_exists, legacy_hit=legacy_hit
        )
        _run_helper(mock_db, status=False)

        if doc_exists:
            payload = _single_payload(doc_ref.update)
        elif legacy_hit:
            payload = _single_payload(legacy_doc.reference.update)
        else:
            payload = _single_payload(doc_ref.set)

        assert payload["human_help_requested"] is False
        assert "ponytail_status" not in payload, (
            f"Reanudación contaminó ponytail_status "
            f"(doc_exists={doc_exists}, legacy_hit={legacy_hit}): {payload}"
        )


# ── DV-2-PIN-5: guard estático Sincronía de Oficio ────────────────────────────

def test_dv2_admin_module_has_no_create_task():
    """DV-2-PIN-5 (guard estático): admin.py no introduce asyncio.create_task
    ni fire-and-forget (Sincronía de Oficio; el puente sigue siendo
    asyncio.to_thread bloqueante desde el endpoint)."""
    source = Path(admin.__file__).read_text(encoding="utf-8")
    assert "asyncio.create_task" not in source
    assert "create_task(" not in source
