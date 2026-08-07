import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.ai_brain import CerebroIA
from app.services.memory_service import MemoryService
from app.routers.whatsapp import _evaluate_skip_greeting
from tests.conftest import AsyncStreamMock


@pytest.fixture
def memory_service():
    mock_db = MagicMock()
    return MemoryService(db=mock_db)


class TestClassifierParentDominant:
    """
    BOT-BUILD-CLASSIFIER-011: el documento padre es la fuente primaria de verdad
    para la asignación de fase; el historial es fallback.
    """

    def test_phase_3_with_complete_parent_and_empty_history(self):
        """
        Pin 1: documento padre completo (habeas+sent+forma_pago+moto+nombre+ciudad)
        + historial vacío → PHASE_3. Reproduce la cura del incidente Jose Mario.
        """
        cerebro = CerebroIA()
        prospect_data = {
            "nombre": "Jose Mario",
            "ciudad": "Medellin",
            "moto_interest": "TVS Raider 125",
            "moto_confirmada": True,
            "forma_pago": "Crédito",
            "habeas_data_accepted": True,
            "habeas_data_accepted_sent": True,
            # Matriz 8 datos
            "ocupacion": "Empleado",
            "ingresos_mensuales": "2 mínimos",
            "datacredito": "Al día",
            "gastos_mensuales": "800000",
            "tiene_gas_natural": "Sí",
            "vivienda": "Arriendo",
            "plan_celular": "Sí",
        }
        phase = cerebro._determine_funnel_phase(prospect_data, history=[])
        assert phase == "PHASE_3_CREDIT_PROFILING"

    def test_phase_3_with_vacant_forma_pago_and_empty_history(self):
        """
        Pin 2: habeas_data_accepted latcheado actúa como intención crediticia
        dominante aunque forma_pago esté vacante y el historial esté borrado.
        """
        cerebro = CerebroIA()
        prospect_data = {
            "nombre": "Jose Mario",
            "ciudad": "Medellin",
            "moto_interest": "TVS Raider 125",
            "moto_confirmada": True,
            "forma_pago": "",
            "habeas_data_accepted": True,
            "habeas_data_accepted_sent": True,
            "ocupacion": "Empleado",
            "ingresos_mensuales": "2 mínimos",
            "datacredito": "Al día",
            "gastos_mensuales": "800000",
            "tiene_gas_natural": "Sí",
            "vivienda": "Arriendo",
            "plan_celular": "Sí",
        }
        phase = cerebro._determine_funnel_phase(prospect_data, history=[])
        assert phase == "PHASE_3_CREDIT_PROFILING"

    def test_phase_1_early_prospect_guardrail_intact(self):
        """
        Pin 3: prospecto temprano (sin habeas, sin forma_pago, sin moto) → PHASE_1.
        El guardrail de rechazo de calculate_credit_score en PHASE_1 permanece activo.
        """
        cerebro = CerebroIA()
        prospect_data = {
            "nombre": "",
            "ciudad": "",
            "moto_interest": "",
            "forma_pago": "",
            "habeas_data_accepted": False,
            "habeas_data_accepted_sent": False,
        }
        phase = cerebro._determine_funnel_phase(prospect_data, history=[])
        assert phase == "PHASE_1_PROFILING"


@pytest.mark.asyncio
class TestMemoryPurgeConditional:
    """
    BOT-BUILD-CLASSIFIER-011: el zombie purge de historial solo corre en fresh-start real.
    """

    @pytest.mark.parametrize("doc_exists,should_purge", [
        (True, False),
        (False, True),
    ])
    async def test_create_prospect_if_missing_purge_conditional(
        self, memory_service, doc_exists, should_purge
    ):
        """
        Pin 4: clear_memory solo corre cuando el documento padre NO existe
        (fresh-start real). Si existe con estado acumulado, el historial se preserva.
        """
        phone = "3227303760"

        mock_doc_snap = MagicMock()
        mock_doc_snap.exists = doc_exists

        mock_doc_ref = AsyncMock()
        mock_doc_ref.get.return_value = mock_doc_snap
        mock_doc_ref.set = AsyncMock()

        def collection_side_effect(name):
            col_mock = MagicMock()
            if name == "prospectos":
                doc_mock = MagicMock()
                doc_mock.get = mock_doc_ref.get
                doc_mock.set = mock_doc_ref.set
                historial_mock = MagicMock()
                historial_mock.stream.return_value = AsyncStreamMock([])
                doc_mock.collection.return_value = historial_mock
                col_mock.document.return_value = doc_mock
            return col_mock

        memory_service._db.collection.side_effect = collection_side_effect
        memory_service._db.batch.return_value = MagicMock(commit=AsyncMock())

        with patch.object(
            memory_service, "clear_memory", new=AsyncMock(return_value=True)
        ) as mock_clear:
            await memory_service.create_prospect_if_missing(phone)

            if should_purge:
                mock_clear.assert_called_once()
            else:
                mock_clear.assert_not_called()


class TestFreshStartDetection:
    """
    BOT-BUILD-CLASSIFIER-011: con historial preservado no debe dispararse fresh-start.
    """

    def test_no_fresh_start_when_existing_doc_has_past_user_messages(self):
        """
        Pin 5: documento existente + historial con mensajes de usuario pasados
        (timestamp reciente) → skip_greeting=True, es decir, NO fresh-start.
        """
        now = datetime.now(timezone.utc)
        prospect_data = {"exists": True, "nombre": "Jose Mario"}
        history = [
            {"role": "user", "content": "Hola", "timestamp": now},
            {"role": "user", "content": "Cuánto cuesta la TVS", "timestamp": now},
        ]
        skip = _evaluate_skip_greeting(
            history, prospect_data, current_message_saved=True
        )
        assert skip is True
