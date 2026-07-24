"""
[BOT-BUILD-FIX-MATRIX-RESTART-001] Pins de certificación (FIX-1).

Milestone 3 - Etapa 4: Fix de mapeo semántico de ingresos en EXTRACTION_SCHEMA.

Causa raíz (validación forense BOT-PLAN-VALIDATE-MATRIX-RESTART-001): el campo
'ingresos_mensuales' EXISTÍA en el schema desde FIX-4A (L124), pero su
descripción ordenaba 'solo dígitos' y solo mapeaba 'el mínimo'→SMLV. La
respuesta real del usuario 'Dos mínimos' no encajaba en ningún patrón y el
bias negativo estricto la desechaba EN CADA TURNO → el campo jamás persistía
en Firestore → checklist FIX-4B lo marcaba PENDIENTE → reinicio de matriz
(re-pregunta de ingresos tras 8/8 respondidas).

FIX-1 (ADITIVO): enmienda ÚNICAMENTE la descripción del campo añadiendo la
regla de mapeo de múltiplos de SMLV (N × 1.705.905) y expresiones de monto.
type STRING y required quedan INTACTOS (constraints duros del ticket).
"""

from app.services.ai_brain import EXTRACTION_SCHEMA
from app.services.memory_service import MemoryService


def _extracted_props() -> dict:
    return EXTRACTION_SCHEMA["properties"]["extracted"]["properties"]


# ===========================================================================
# FIX-1a — Descripción con regla de mapeo de múltiplos SMLV (pin estático)
# ===========================================================================
def test_fix1a_ingresos_description_has_smlv_multiplier_mapping():
    """La descripción de ingresos_mensuales debe instruir al extractor el mapeo
    de expresiones en salarios mínimos a dígitos (SMLV vigente 1.705.905 COP),
    incluyendo el caso real del incidente: 'dos mínimos' → '3411810'."""
    field = _extracted_props()["ingresos_mensuales"]
    description = field["description"]

    # Regla de mapeo de múltiplos SMLV (caso incidente + generalización)
    assert "dos mínimos" in description
    assert "3411810" in description          # 2 × 1.705.905
    assert "1705905" in description          # SMLV base
    assert "5117715" in description          # 3 × 1.705.905
    assert "N × 1705905" in description      # regla general para múltiplos

    # Mapeos de expresiones de monto comunes
    assert "2 palos" in description
    assert "500 mil" in description

    # El bias negativo se conserva SOLO para ausencia real del dato
    assert "NO mencionó ingresos" in description

    # Constraints duros: type y required INTACTOS
    assert field["type"] == "STRING"
    assert "ingresos_mensuales" not in EXTRACTION_SCHEMA["properties"]["extracted"]["required"]


# ===========================================================================
# FIX-1b — Consistencia cruzada: fuentes del checklist ⊆ EXTRACTION_SCHEMA
# ===========================================================================
def test_fix1b_checklist_source_fields_exist_in_extraction_schema():
    """Anti-clase-de-bug: todo campo CRM que alimenta una fila del checklist
    FIX-4B debe tener su fuente de extracción en EXTRACTION_SCHEMA. Si una
    fila del checklist dependiera de un campo no extraíble, la matriz jamás
    podría alcanzar COMPLETO (misma familia del incidente 'Dos mínimos')."""
    # Fuentes documentadas del checklist (_build_profiling_checklist L512-568):
    # Ocupación/Contrato ← ocupacion; Ingresos ← ingresos_mensuales;
    # Datacrédito ← datacredito; Gastos ← gastos_mensuales;
    # Gas ← tiene_gas_natural | servicios_publicos; Vivienda ← vivienda;
    # Plan celular ← plan_celular | servicios_publicos
    checklist_source_fields = {
        "ocupacion",
        "ingresos_mensuales",
        "datacredito",
        "gastos_mensuales",
        "tiene_gas_natural",
        "vivienda",
        "plan_celular",
        "servicios_publicos",
    }
    schema_fields = set(_extracted_props().keys())
    missing = checklist_source_fields - schema_fields
    assert not missing, f"Campos del checklist sin fuente en EXTRACTION_SCHEMA: {missing}"

    # Además: los valores mapeados como dígitos deben sobrevivir la compuerta
    # de validación del merge (regresión del contrato PRESERVE_IF_HISTORIC_VALID).
    assert MemoryService._is_field_valid("3411810") is True
    assert MemoryService._is_field_valid("1705905") is True


# ===========================================================================
# FIX-1c — Cadena completa del incidente: valor mapeado → merge → COMPLETO
# ===========================================================================
def test_fix1c_mapped_income_survives_merge_and_completes_checklist():
    """Reproducción del escenario del incidente ya corregido: el extractor
    devuelve '3411810' ('Dos mínimos' mapeado) → _merge_extracted_data lo
    acepta → el prospecto con los 8 datos alcanza <siguiente_pendiente>
    COMPLETO</siguiente_pendiente> → la instrucción FIX-A ordena el CIERRE."""
    from app.services.ai_brain import CerebroIA

    current = {
        "ocupacion": "Independiente",
        "datacredito": "Sin experiencia",
        "gastos_mensuales": "500000",
        "tiene_gas_natural": "No",
        "vivienda": "Familiar",
        "plan_celular": "No",
        "habeas_data_accepted": True,
        # ingresos_mensuales AUSENTE — estado exacto del Firestore del incidente
    }
    incoming = {"ingresos_mensuales": "3411810"}  # 'Dos mínimos' ya mapeado

    merged = MemoryService(db=None)._merge_extracted_data(current, incoming)
    assert merged.get("ingresos_mensuales") == "3411810", \
        "El valor mapeado de 'Dos mínimos' no sobrevivió el merge"

    prospect_after_merge = {**current, **merged}
    checklist = CerebroIA()._build_profiling_checklist(prospect_after_merge)
    assert "<siguiente_pendiente>COMPLETO</siguiente_pendiente>" in checklist
    assert 'estado="PENDIENTE"' not in checklist
