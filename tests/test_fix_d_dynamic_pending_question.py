"""
Tests FIX-D — [BOT-BUILD-FIX-D-DYNAMIC-PENDING-QUESTION] (Fase 2).

`_get_pending_funnel_question` (PHASE_3_CREDIT_PROFILING) debe evaluar el estado
actual de la matriz y retornar dinámicamente el texto exacto del
<siguiente_pendiente> del checklist determinista (mapa canónico de 8 entradas),
erradicando la pregunta genérica hardcoded.

- T1: paramétrico 8×N — para cada dato de la matriz, con todos los anteriores
  capturados, la pregunta retornada es EXACTAMENTE la del mapa canónico.
- T2: contrato COMPLETO → "" (el freno FAQ emite el mandato de cierre de fase).
- T3: paridad SSOT — `_build_profiling_checklist` y `_get_pending_funnel_question`
  leen la misma verdad (`_evaluate_profiling_matrix`).
- T4: pin estático — la pregunta genérica hardcoded no existe en el cuerpo de
  `_get_pending_funnel_question` ni el cuerpo duplicado de filas vive fuera del
  evaluador compartido.
"""

import inspect
import re

import pytest

from app.services.ai_brain import CerebroIA

PHASE_3 = "PHASE_3_CREDIT_PROFILING"

# Campo CRM que llena cada fila de la matriz (paridad con _evaluate_profiling_matrix).
ROW_FIELD = {
    "Ocupación": "ocupacion",
    "Contrato": "ocupacion",  # filas 1-2 comparten campo (EXTRACTION_SCHEMA fusiona)
    "Ingresos": "ingresos_mensuales",
    "Reportes Datacrédito": "datacredito",
    "Gastos mensuales": "gastos_mensuales",
    "Gas natural (Brilla)": "tiene_gas_natural",
    "Vivienda": "vivienda",
    "Plan celular": "plan_celular",
}

EXPECTED_QUESTIONS = CerebroIA._PROFILING_QUESTION_MAP


def _prospect_with_prior_rows_filled(target_label: str) -> dict:
    """Prospecto con TODAS las filas anteriores a target_label llenas, la fila
    objetivo (y las siguientes) vacías. Las filas que comparten campo se llenan juntas."""
    data = {}
    for label in EXPECTED_QUESTIONS:
        if label == target_label:
            break
        data[ROW_FIELD[label]] = "VALOR"
    return data


# ---------------------------------------------------------------------------
# T1 — Paramétrico: el <siguiente_pendiente> determina la pregunta exacta
# ---------------------------------------------------------------------------

# La fila "Contrato" comparte campo con "Ocupación": nunca puede ser el primer
# pendiente (si ocupacion falta, el primer pendiente es Ocupación). Se excluye del
# paramétrico y se cubre con un test de invariante dedicado.
REACHABLE_LABELS = [l for l in EXPECTED_QUESTIONS if l != "Contrato"]


@pytest.mark.parametrize("label", REACHABLE_LABELS)
def test_pending_question_matches_canonical_map(label):
    cerebro = CerebroIA()
    data = _prospect_with_prior_rows_filled(label)
    question = cerebro._get_pending_funnel_question(PHASE_3, data)
    assert question == EXPECTED_QUESTIONS[label], (
        f"Para <siguiente_pendiente>={label!r} la pregunta debe ser la exacta del mapa canónico.\n"
        f"Esperada: {EXPECTED_QUESTIONS[label]!r}\nRecibida: {question!r}"
    )


def test_contrato_never_first_pending_invariant():
    """Filas 1-2 comparten `ocupacion`: si falta, el primer pendiente es Ocupación;
    si está, ambas filas quedan CAPTURADAS. 'Contrato' jamás es <siguiente_pendiente>."""
    cerebro = CerebroIA()
    _, next_empty = cerebro._evaluate_profiling_matrix({})
    assert next_empty == "Ocupación"
    _, next_filled = cerebro._evaluate_profiling_matrix({"ocupacion": "Empleado"})
    assert next_filled == "Ingresos"


def test_none_prospect_data_asks_first_row():
    cerebro = CerebroIA()
    assert cerebro._get_pending_funnel_question(PHASE_3, None) == EXPECTED_QUESTIONS["Ocupación"]


def test_gas_row_filled_by_servicios_publicos():
    cerebro = CerebroIA()
    data = _prospect_with_prior_rows_filled("Gas natural (Brilla)")
    data["servicios_publicos"] = "gas natural"
    _, nxt = cerebro._evaluate_profiling_matrix(data)
    assert nxt == "Vivienda"


# ---------------------------------------------------------------------------
# T2 — Contrato COMPLETO: sin pregunta genérica, retorna ""
# ---------------------------------------------------------------------------

def test_complete_matrix_returns_empty_contract():
    cerebro = CerebroIA()
    full = {field: "VALOR" for field in set(ROW_FIELD.values())}
    assert cerebro._get_pending_funnel_question(PHASE_3, full) == ""


def test_complete_checklist_reports_completo():
    cerebro = CerebroIA()
    full = {field: "VALOR" for field in set(ROW_FIELD.values())}
    checklist = cerebro._build_profiling_checklist(full)
    assert "<siguiente_pendiente>COMPLETO</siguiente_pendiente>" in checklist


# ---------------------------------------------------------------------------
# T3 — Paridad SSOT: checklist y freno FAQ leen la misma verdad
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", REACHABLE_LABELS)
def test_checklist_and_brake_share_same_truth(label):
    cerebro = CerebroIA()
    data = _prospect_with_prior_rows_filled(label)
    checklist = cerebro._build_profiling_checklist(data)
    assert f"<siguiente_pendiente>{label}</siguiente_pendiente>" in checklist
    assert cerebro._get_pending_funnel_question(PHASE_3, data) == EXPECTED_QUESTIONS[label]


# ---------------------------------------------------------------------------
# T4 — Pins estáticos anti-regresión
# ---------------------------------------------------------------------------

def test_hardcoded_generic_question_eradicated():
    """El genérico '¿Me indicas el dato que falta?' no debe existir en el cuerpo
    de _get_pending_funnel_question (erradicación FIX-D)."""
    src = inspect.getsource(CerebroIA._get_pending_funnel_question)
    assert "¿Me indicas el dato que falta?" not in src
    assert "Continuemos con el perfilamiento" not in src


def test_matrix_rows_single_source():
    """La definición de las 8 filas vive SOLO en _evaluate_profiling_matrix:
    _build_profiling_checklist no redefine filas (delega en el evaluador)."""
    src = inspect.getsource(CerebroIA._build_profiling_checklist)
    assert "_evaluate_profiling_matrix" in src
    assert '"Ocupación"' not in src, "Las filas de la matriz se redefinieron fuera del SSOT"


def test_map_has_exactly_eight_entries_in_matrix_order():
    expected_order = [
        "Ocupación", "Contrato", "Ingresos", "Reportes Datacrédito",
        "Gastos mensuales", "Gas natural (Brilla)", "Vivienda", "Plan celular",
    ]
    assert list(EXPECTED_QUESTIONS.keys()) == expected_order


def test_map_covers_every_evaluator_label():
    cerebro = CerebroIA()
    rows, _ = cerebro._evaluate_profiling_matrix({})
    for label, _ in rows:
        assert label in EXPECTED_QUESTIONS, f"Label {label!r} sin pregunta canónica en el mapa"


def test_generic_string_absent_from_ai_brain_source():
    """Pin de archivo: la cadena genérica hardcoded no existe en ai_brain.py."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "app/services/ai_brain.py").read_text(encoding="utf-8")
    assert "¿Me indicas el dato que falta?" not in src
