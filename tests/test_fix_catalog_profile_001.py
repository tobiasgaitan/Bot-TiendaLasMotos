"""
[BOT-BUILD-FIX-CATALOG-PROFILE-001-AMPLIADO] Pins de certificación (5 fixes).

Milestone 3 - Etapa 4: Corrección de Flujo Post-Reset.

FIX-1  Compuerta de herramienta forzada extendida con alias searchBy dinámicos
       (_load_searchby_aliases): cualquier referencia indexada SOLO en searchBy
       (competencia o modelos tipo 'eco deluxe 100', 'CR4 150', 'FZ 150') ahora
       dispara el turno de validación forzada si el LLM evade search_catalog.
FIX-2A Timeout de cliente (GEMINI_CALL_TIMEOUT_S) en _call_gemini_with_retry_async
       vía asyncio.wait_for; asyncio.TimeoutError entra al conjunto reintentable.
FIX-2B Los fallos transitorios (5xx/internal, candidatos vacíos/safety filter)
       consumen el presupuesto max_retries=3 antes de degradar al fallback
       "colgado". RuntimeError genérico conserva el retorno inmediato heredado.
FIX-4A EXTRACTION_SCHEMA: 5 campos nuevos de perfilamiento (STRING, no required)
       persisten vía memory_service._merge_extracted_data.
FIX-4B _build_profiling_checklist: checklist determinista de la MATRIZ_DE
       PERFILAMIENTO (8 datos) inyectado SOLO en PHASE_3_CREDIT_PROFILING.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.ai_brain as ai_brain_module
from app.services.ai_brain import CerebroIA, EXTRACTION_SCHEMA
from app.services.catalog_service import CatalogService
from app.services.memory_service import MemoryService


# ---------------------------------------------------------------------------
# Mock helpers (patrón establecido en tests/test_agentic_loop_async.py)
# ---------------------------------------------------------------------------
class MockPart:
    def __init__(self, function_call=None, text=None):
        self.function_call = function_call
        self.text = text


class MockContent:
    def __init__(self, parts):
        self.parts = parts


class MockCandidate:
    def __init__(self, content):
        self.content = content


class MockResponse:
    def __init__(self, candidates):
        self.candidates = candidates


def _text_response(text: str) -> MockResponse:
    return MockResponse(candidates=[MockCandidate(content=MockContent(parts=[MockPart(text=text)]))])


def _tool_response(name: str, args: dict) -> MockResponse:
    fc = MagicMock()
    fc.name = name
    fc.args = args
    return MockResponse(candidates=[MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))])


def _empty_response() -> MockResponse:
    return MockResponse(candidates=[])


# [BOT-BUILD-DEADLINE-BUDGET-023 / F4.5] Fixture aditiva - cero edición de pins.
# La política frío/caliente de deadline_budget se activa si GEMINI_COLD_CALL_TIMEOUT_S
# existe en el entorno.  Borrarla aquí garantiza que los pins FIX-2A (que parchean la
# constante GEMINI_CALL_TIMEOUT_S) no deriven al timeout frío si un dev pone la var en
# su .env local.
@pytest.fixture(autouse=True)
def _clean_deadline_env_for_fix2a(monkeypatch):
    monkeypatch.delenv("GEMINI_COLD_CALL_TIMEOUT_S", raising=False)


# ===========================================================================
# FIX-1 — Compuerta forzada con alias searchBy dinámicos
# ===========================================================================
def test_fix1_load_searchby_aliases_filters_and_collects():
    """El helper carga valores únicos de searchBy (lowercase, sorted) y filtra
    tokens peligrosos bajo matching por substring: numéricos puros, len<3 y
    stopwords funcionales ('sin' colisiona con 'sin cuota inicial')."""
    catalog = CatalogService()
    catalog._items = [
        {"searchBy": ["Eco", "deluxe", "125", "sin", "ab", "Boxer"]},
        {"searchBy": "not-a-list"},      # tipo corrupto → ignorado
        {"searchBy": ["eco"]},           # duplicado → dedup
        "not-a-dict",                    # ítem corrupto → ignorado
        {"no_searchBy": True},           # llave ausente → ignorado
    ]
    cerebro = CerebroIA(catalog_service=catalog)
    assert cerebro._searchBy_aliases == ["boxer", "deluxe", "eco"]

    # Degradación fail-open sin catálogo inyectado
    cerebro_sin_catalogo = CerebroIA()
    assert cerebro_sin_catalogo._searchBy_aliases == []


@pytest.mark.asyncio
async def test_fix1_forced_turn_fires_for_searchby_only_reference():
    """Usuario pregunta por 'Eco Deluxe 100' (referencia que SOLO existe en
    searchBy; no está en base_keywords ni en alias de categoría). Si el LLM
    responde sin llamar search_catalog, la compuerta DEBE forzar el turno de
    validación y el flujo termina en la alternativa verificada del catálogo."""
    catalog = CatalogService()
    catalog._items = [
        {
            "id": "eco_deluxe_100",
            "name": "ECO DELUXE 100",
            "price": "$5.000.000",
            "category": "trabajo",
            "image_url": "http://img/eco.png",
            "summary": "Moto de trabajo económica.",
            "searchBy": ["eco", "deluxe", "eco deluxe"],
            "search_tokens": ["eco", "deluxe", "100", "trabajo"],
            "search_text": "eco deluxe 100 trabajo",
        }
    ]
    cerebro = CerebroIA(catalog_service=catalog)

    # Precondición: la referencia solo-searchBy quedó indexada en el helper.
    assert "eco" in cerebro._searchBy_aliases
    assert "deluxe" in cerebro._searchBy_aliases

    responses = [
        # Turno 1: el LLM evade la herramienta y responde texto puro.
        _text_response("No manejo esa referencia, ¿te interesa otra moto?"),
        # Turno 2 (forzado por la compuerta): el LLM ejecuta search_catalog.
        _tool_response("search_catalog", {"query": "eco deluxe"}),
        # Turno 3: respuesta final con la alternativa verificada.
        _text_response("La ECO DELUXE 100 es nuestra equivalente verificada. ¿Desde qué ciudad me escribes?"),
    ]
    gemini_calls = []

    async def mock_call(*args, **kwargs):
        gemini_calls.append(args)
        return responses[min(len(gemini_calls) - 1, len(responses) - 1)]

    prospect_data = {"exists": True, "nombre": "Test", "habeas_data_accepted": True}

    with patch("app.services.config_service.config_service.get_catalog_aliases", return_value={}), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch.object(catalog, "search_items", return_value=[{
             "name": "ECO DELUXE 100",
             "price": "$5.000.000",
             "category": "trabajo",
             "image_url": "http://img/eco.png",
             "summary": "Moto de trabajo económica.",
         }]), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        res = await cerebro.pensar_respuesta("Tienen la Eco Deluxe 100?", prospect_data=prospect_data)

    assert len(gemini_calls) >= 2, (
        "La compuerta NO forzó el turno de validación para una referencia "
        "presente únicamente en searchBy ('eco'/'deluxe')."
    )
    forced_msg = str(gemini_calls[1][1]) if len(gemini_calls[1]) > 1 else str(gemini_calls[1])
    assert "search_catalog" in forced_msg and "OBLIGADO" in forced_msg, (
        f"El segundo turno no es la instrucción forzada de catálogo: {forced_msg[:200]}"
    )
    assert "ECO DELUXE 100" in res


# ===========================================================================
# FIX-2A — Timeout de cliente en _call_gemini_with_retry_async
# ===========================================================================
@pytest.mark.asyncio
async def test_fix2a_timeout_retries_and_propagates():
    """Un hang de Gemini (la corutina nunca completa) dispara asyncio.wait_for;
    el wrapper reintenta con backoff (max_retries=2 → 3 llamadas) y propaga
    TimeoutError tras agotar el presupuesto."""
    cerebro = CerebroIA()
    calls = {"n": 0}

    async def slow_func(*args, **kwargs):
        calls["n"] += 1
        await asyncio.Event().wait()  # nunca completa → wait_for dispara timeout

    with patch("app.services.ai_brain.GEMINI_CALL_TIMEOUT_S", 0.05), \
         patch.object(ai_brain_module.asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(asyncio.TimeoutError):
            await cerebro._call_gemini_with_retry_async(slow_func)

    assert calls["n"] == 3, f"Esperaba 1 intento + 2 reintentos, hubo {calls['n']}"
    assert mock_sleep.await_count == 2, "El backoff exponencial no se ejecutó entre reintentos"


@pytest.mark.asyncio
async def test_fix2a_success_within_timeout_returns_value():
    """Una llamada que completa dentro del timeout retorna su valor intacto
    en el primer intento (sin reintentos)."""
    cerebro = CerebroIA()
    calls = {"n": 0}

    async def fast_func(*args, **kwargs):
        calls["n"] += 1
        return "ok"

    with patch("app.services.ai_brain.GEMINI_CALL_TIMEOUT_S", 1.0):
        assert await cerebro._call_gemini_with_retry_async(fast_func) == "ok"
    assert calls["n"] == 1


# ===========================================================================
# FIX-2B — Presupuesto de reintentos para fallos transitorios
# ===========================================================================
@pytest.mark.asyncio
async def test_fix2b_empty_candidates_retried_then_success():
    """Candidatos vacíos (safety filter) en intento 1 + respuesta válida en
    intento 2 → retorna el texto, NO el fallback 'colgado'."""
    cerebro = CerebroIA()
    responses = [_empty_response(), _text_response("Entendido, sigamos con tu solicitud.")]
    gemini_calls = []

    async def mock_call(*args, **kwargs):
        gemini_calls.append(args)
        return responses[min(len(gemini_calls) - 1, len(responses) - 1)]

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch.object(ai_brain_module.asyncio, "sleep", new_callable=AsyncMock), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        res = await cerebro.pensar_respuesta("hola", prospect_data=None, history=[])

    # Nota: clean_parrot_phrases sanea preámbulos ("Entendido, ..." → "Sigamos...").
    assert "igamos con tu solicitud" in res
    assert "colgado" not in res
    assert len(gemini_calls) == 2, f"El transitorio no consumió el presupuesto de reintentos: {len(gemini_calls)} llamadas"


@pytest.mark.asyncio
async def test_fix2b_empty_candidates_persistent_falls_back_after_budget():
    """Candidatos vacíos persistentes → fallback SOLO tras agotar max_retries=3
    (exactamente 3 llamadas a Gemini)."""
    cerebro = CerebroIA()
    gemini_calls = []

    async def mock_call(*args, **kwargs):
        gemini_calls.append(args)
        return _empty_response()

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch.object(ai_brain_module.asyncio, "sleep", new_callable=AsyncMock), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        res = await cerebro.pensar_respuesta("hola", prospect_data=None, history=[])

    assert "colgado" in res
    assert len(gemini_calls) == 3, f"El fallback debió esperar 3 intentos, hubo {len(gemini_calls)}"


@pytest.mark.asyncio
async def test_fix2b_transient_5xx_retried_then_success():
    """Excepción con firma 5xx/internal en intento 1 + éxito en intento 2 →
    retorna texto válido (los errores transitorios de Vertex sí reintentan)."""
    cerebro = CerebroIA()
    plan = [Exception("500 Internal Server Error (simulated)"), _text_response("Entendido, sigamos con tu solicitud.")]
    gemini_calls = []

    async def mock_call(*args, **kwargs):
        gemini_calls.append(args)
        item = plan[min(len(gemini_calls) - 1, len(plan) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch.object(ai_brain_module.asyncio, "sleep", new_callable=AsyncMock), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        res = await cerebro.pensar_respuesta("hola", prospect_data=None, history=[])

    assert "igamos con tu solicitud" in res
    assert len(gemini_calls) == 2


@pytest.mark.asyncio
async def test_fix2b_generic_runtime_error_falls_back_immediately():
    """RuntimeError genérico (sin firma 5xx) → fallback inmediato en 1 llamada.
    Comportamiento heredado CONSERVADO (protege pins previos con side_effect)."""
    cerebro = CerebroIA()
    gemini_calls = []

    async def mock_call(*args, **kwargs):
        gemini_calls.append(args)
        raise RuntimeError("boom genérico (simulated)")

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch.object(ai_brain_module.asyncio, "sleep", new_callable=AsyncMock), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        res = await cerebro.pensar_respuesta("hola", prospect_data=None, history=[])

    assert "colgado" in res
    assert len(gemini_calls) == 1, f"RuntimeError genérico debió caer al fallback sin reintentar: {len(gemini_calls)} llamadas"


# ===========================================================================
# FIX-4A — EXTRACTION_SCHEMA: nuevos campos de perfilamiento persistibles
# ===========================================================================
NEW_PROFILE_FIELDS = [
    "ingresos_mensuales",
    "gastos_mensuales",
    "plan_celular",
    "tiene_gas_natural",
    "mora_y_paz_salvo",
]


def test_fix4a_schema_contains_new_fields_not_required():
    """Los 5 campos de la MATRIZ_PERFILAMIENTO ausentes del schema ahora existen
    como STRING y NINGUNO entra al array required (constraint duro del ticket)."""
    props = EXTRACTION_SCHEMA["properties"]["extracted"]["properties"]
    required = EXTRACTION_SCHEMA["properties"]["extracted"]["required"]
    for field in NEW_PROFILE_FIELDS:
        assert field in props, f"Campo {field} ausente del EXTRACTION_SCHEMA"
        assert props[field]["type"] == "STRING", f"Campo {field} debe ser STRING"
        assert field not in required, f"Campo {field} no debe ser required"


def test_fix4a_merge_persists_new_fields():
    """_merge_extracted_data acepta los nuevos campos (ninguno es CRM-protected
    ni latch) y los deja fluir 1:1 hacia Firestore."""
    ms = MemoryService.__new__(MemoryService)
    current = {"nombre": "Ana"}
    incoming = {
        "ingresos_mensuales": "1705905",
        "gastos_mensuales": "800000",
        "plan_celular": "Sí",
        "tiene_gas_natural": "No",
        "mora_y_paz_salvo": "Sin reportes",
    }
    merged = ms._merge_extracted_data(current, incoming)
    for k, v in incoming.items():
        assert merged.get(k) == v, f"Campo {k} no persistió en el merge: {merged}"


def test_fix4a_merge_rejects_empty_values_for_new_fields():
    """Valores vacíos/'null'/None en los nuevos campos son rechazados por la
    compuerta _is_field_valid: NO entran al merge (protege el histórico válido)."""
    ms = MemoryService.__new__(MemoryService)
    current = {"ingresos_mensuales": "1705905"}
    incoming = {
        "ingresos_mensuales": "",
        "gastos_mensuales": "null",
        "plan_celular": None,
        "tiene_gas_natural": "   ",
    }
    merged = ms._merge_extracted_data(current, incoming)
    for k in incoming:
        assert k not in merged, f"Valor inválido para {k} no debió entrar al merge: {merged}"


# ===========================================================================
# FIX-4B — Checklist determinista de perfilamiento (render + inyección por fase)
# ===========================================================================
def test_fix4b_checklist_render_partial():
    """Render con datos parciales: marca CAPTURADO(valor) los datos presentes
    (Ocupación y Contrato leen 'ocupacion'; Gas lee servicios_publicos) y
    PENDIENTE los ausentes; siguiente_pendiente = primer PENDIENTE."""
    cerebro = CerebroIA()
    block = cerebro._build_profiling_checklist({
        "ocupacion": "Independiente",
        "datacredito": "Al día",
        "servicios_publicos": "Gas natural a su nombre",
    })
    assert '<item nombre="Ocupación" estado="CAPTURADO">Independiente</item>' in block
    assert '<item nombre="Contrato" estado="CAPTURADO">Independiente</item>' in block
    assert '<item nombre="Reportes Datacrédito" estado="CAPTURADO">Al día</item>' in block
    assert '<item nombre="Gas natural (Brilla)" estado="CAPTURADO">' in block
    assert '<item nombre="Ingresos" estado="PENDIENTE"/>' in block
    assert '<item nombre="Gastos mensuales" estado="PENDIENTE"/>' in block
    assert '<item nombre="Vivienda" estado="PENDIENTE"/>' in block
    assert '<item nombre="Plan celular" estado="PENDIENTE"/>' in block
    assert "<siguiente_pendiente>Ingresos</siguiente_pendiente>" in block


def test_fix4b_checklist_render_complete_and_empty():
    """Render completo → siguiente_pendiente=COMPLETO. Render vacío (None) →
    las 8 filas PENDIENTE y siguiente_pendiente=Ocupación (primera de la matriz)."""
    cerebro = CerebroIA()
    full = cerebro._build_profiling_checklist({
        "ocupacion": "Empleado",
        "ingresos_mensuales": "1705905",
        "datacredito": "Al día",
        "gastos_mensuales": "800000",
        "tiene_gas_natural": "Sí",
        "vivienda": "Propia",
        "plan_celular": "Sí",
    })
    assert "<siguiente_pendiente>COMPLETO</siguiente_pendiente>" in full
    assert 'estado="PENDIENTE"' not in full

    empty = cerebro._build_profiling_checklist(None)
    assert empty.count('estado="PENDIENTE"') == 8
    assert "<siguiente_pendiente>Ocupación</siguiente_pendiente>" in empty


@pytest.mark.asyncio
async def test_fix4b_checklist_injected_only_in_phase3():
    """El bloque <estado_perfilamiento> se inyecta en el prompt SOLO cuando la
    fase determinista es PHASE_3_CREDIT_PROFILING (ausente en PHASE_1)."""
    # --- Caso PHASE_3_CREDIT_PROFILING ---
    cerebro = CerebroIA()
    prospect_phase3 = {
        "exists": True,
        "nombre": "Ana",
        "ciudad": "Cali",
        "forma_pago": "credito",
        "moto_interest": "TVS SPORT 100 ELS",
        "habeas_data_accepted": True,
        "habeas_data_accepted_sent": True,
        "ocupacion": "Independiente",
    }
    history = [{"role": "model", "content": "Política: https://tiendalasmotos.com/politica-de-privacidad"}]

    prompts = []

    async def mock_call(*args, **kwargs):
        prompts.append(str(args[1]) if len(args) > 1 else "")
        return _text_response("Entendido, continuamos.")

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        await cerebro.pensar_respuesta("soy independiente", prospect_data=prospect_phase3, history=history)

    assert prompts, "No se capturó el prompt enviado a Gemini"
    assert "<estado_perfilamiento>" in prompts[0], "El checklist no se inyectó en PHASE_3_CREDIT_PROFILING"
    assert "Independiente" in prompts[0]
    assert "<siguiente_pendiente>" in prompts[0]

    # --- Caso PHASE_1_PROFILING (sin checklist) ---
    cerebro2 = CerebroIA()
    prospect_phase1 = {"exists": True, "nombre": "Ana"}
    prompts2 = []

    async def mock_call2(*args, **kwargs):
        prompts2.append(str(args[1]) if len(args) > 1 else "")
        return _text_response("Entendido, continuamos.")

    with patch.object(cerebro2, "_call_gemini_with_retry_async", side_effect=mock_call2), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        await cerebro2.pensar_respuesta("hola", prospect_data=prospect_phase1, history=[])

    assert prompts2, "No se capturó el prompt enviado a Gemini (fase 1)"
    assert "<estado_perfilamiento>" not in prompts2[0], "El checklist se filtró fuera de PHASE_3_CREDIT_PROFILING"


# ===========================================================================
# BOT-BUILD-FIX-PROMPT-RESTORE-EXACT-003 — Armonización total con texto fuente
# ===========================================================================
def test_promptrestore003_fuentes_armonizadas_texto_definitivo():
    """T1 (guard estático): AMBAS fuentes de prompt (personality.json y
    prompts.py) contienen el texto fuente definitivo carácter por carácter:
    la alucinación arquitectónica 'simulado internamente' queda erradicada, el
    disparo coercitivo 'INVOCA INMEDIATAMENTE' y la cláusula 'PRIORIDAD
    ABSOLUTA' están presentes, las 4 rutas JSON-driven se preservan con su
    redacción exacta, el PASO 4 es neutral ('nuestro sistema'), el Visual-Lock
    Markdown es explícito en la sección de competencia, y ambas fuentes son
    idénticas (armonización total)."""
    import json as _json
    import pathlib

    from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION

    root = pathlib.Path(__file__).resolve().parents[1]
    pj = _json.loads((root / "app/core/personality.json").read_text(encoding="utf-8"))["system_instruction"]
    py = JUAN_PABLO_SYSTEM_INSTRUCTION

    for name, src in (("personality.json", pj), ("prompts.py", py)):
        # Erradicación de la alucinación arquitectónica (texto viejo)
        assert "simulado internamente" not in src, f"Alucinación arquitectónica persiste en {name}"
        assert "evalúa el puntaje crediticio simulado internamente" not in src, \
            f"Frase vieja completa persiste en {name}"
        # Disparo coercitivo + cláusula de precedencia
        assert "INVOCA INMEDIATAMENTE" in src, f"Disparo coercitivo de herramienta ausente en {name}"
        assert "calculate_credit_score" in src, f"Referencia a herramienta ausente en {name}"
        assert "PRIORIDAD ABSOLUTA" in src, f"Cláusula de precedencia de las 4 rutas ausente en {name}"
        # Las 4 rutas del cierre de fase (redacción exacta del texto definitivo)
        assert "Si el JSON indica score igual o mayor a 750 puntos" in src, f"Ruta 1 (Banco >=750) ausente en {name}"
        assert "Si el JSON indica score entre 500 y 749 puntos" in src, f"Ruta 2 (Revisión Humana 500-749) ausente en {name}"
        assert "Un compañero revisará estos datos y se contactará contigo" in src, f"Texto revisión humana ruta 2 ausente en {name}"
        assert "Si el JSON indica score igual o menor a 499 puntos Y el dato de Gas Natural de la matriz es afirmativo" in src, f"Ruta 3 (Brilla <=499 + gas) ausente en {name}"
        assert "Si el JSON indica score igual o menor a 499 puntos Y el dato de Gas Natural de la matriz es negativo" in src, f"Ruta 4 (Rechazo <=499 sin gas) ausente en {name}"
        assert "no es posible aprobar el crédito" in src, f"Texto de rechazo ruta 4 ausente en {name}"
        # Invariante (b): PASO 4 neutral ('nuestro sistema')
        assert "validar tu cupo exacto con nuestro sistema" in src, \
            f"PASO 4 neutral ('nuestro sistema') ausente en {name}"
        # Invariante (c): Visual-Lock Markdown explícito en sección de competencia
        assert "incluye OBLIGATORIAMENTE la imagen en formato Markdown `![Nombre_Moto](URL_devuelta_por_search_catalog)`" in src, \
            f"Visual-Lock Markdown explícito ausente en la sección de competencia de {name}"

    # Pin de armonización total: identidad byte-exacta entre ambas fuentes
    assert pj == py, (
        "personality.json y JUAN_PABLO_SYSTEM_INSTRUCTION divergen: "
        "la armonización total se rompió"
    )


@pytest.mark.asyncio
async def test_cierre4rutas002_matriz_completa_coerce_invocacion_sin_texto_previo():
    """T2 (invocación): con los 8/8 datos de la matriz capturados, el prompt del
    turno contiene el MANDATO DE CIERRE DE FASE (coerción COMPLETO) y la prohibición
    de texto libre; el bucle procesa la function call de calculate_credit_score
    (sin partes de texto previas) y solo genera respuesta tras el JSON."""
    cerebro = CerebroIA()

    mock_financial = MagicMock()
    mock_financial.evaluate_profile.return_value = {
        "score": 450,
        "strategy": "BRILLA",
        "entity": "Brilla de Gases",
        "rate_key": None,
        "link_url": None,
        "requires_aval": False,
        "is_fallback": True,
    }
    cerebro.motor_financiero = mock_financial

    prospect_completo = {
        "exists": True,
        "nombre": "Ana",
        "ciudad": "Cali",
        "forma_pago": "credito",
        "moto_interest": "TVS SPORT 100 ELS",
        "habeas_data_accepted": True,
        "habeas_data_accepted_sent": True,
        # Los 8 datos de la matriz (Contrato se fusiona en 'ocupacion'):
        "ocupacion": "Empleada término fijo",
        "ingresos_mensuales": "1705905",
        "datacredito": "Al día",
        "gastos_mensuales": "800000",
        "tiene_gas_natural": "Sí",
        "vivienda": "Propia",
        "plan_celular": "Sí",
    }
    history = [{"role": "model", "content": "Política: https://tiendalasmotos.com/politica-de-privacidad"}]

    captured_prompts = []
    call_count = 0

    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if len(args) > 1:
            captured_prompts.append(str(args[1]))
        if call_count == 1:
            # El LLM obedece la coerción: function call SIN partes de texto previas.
            return _tool_response("calculate_credit_score", {})
        return _text_response("Tu estudio va por Brilla: necesito foto de tu cédula y los dos recibos del gas.")

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
        res = await cerebro.pensar_respuesta("ya respondí todo", prospect_data=prospect_completo, history=history)

    # 1. La coerción COMPLETO se inyectó en el prompt del turno
    assert captured_prompts, "No se capturó el prompt enviado a Gemini"
    assert "<siguiente_pendiente>COMPLETO</siguiente_pendiente>" in captured_prompts[0], \
        "El checklist no alcanzó estado COMPLETO con los 8/8 datos"
    assert "MANDATO DE CIERRE DE FASE" in captured_prompts[0], \
        "La rama COMPLETO no inyectó el mandato coercitivo de cierre"
    assert "PROHIBIDO generar texto libre antes de tener el JSON del score" in captured_prompts[0], \
        "El freno cognitivo de texto libre no se inyectó"
    assert "Tu única pregunta pendiente debe ser" not in captured_prompts[0], \
        "El mandato genérico (absurdo en COMPLETO) no debió inyectarse"

    # 2. La herramienta se ejecutó exactamente una vez (rama legacy evaluate_profile)
    mock_financial.evaluate_profile.assert_called_once()

    # 3. El texto final llega SOLO tras el JSON (nunca el fallback prematuro)
    assert "colgado" not in res
    assert "cédula" in res


@pytest.mark.asyncio
async def test_cierre4rutas002_fallback_logs_reason_on_budget_exhaustion():
    """T3 (Zero-Silent-Failures): al agotar max_retries por candidatos vacíos,
    el fallback 'colgado' queda precedido de un logger.error terminal con la
    firma [AI FALLBACK REASON] (sitios L1863/L1931 instrumentados)."""
    cerebro = CerebroIA()

    async def mock_call(*args, **kwargs):
        return _empty_response()

    with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call), \
         patch.object(ai_brain_module.asyncio, "sleep", new_callable=AsyncMock), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True), \
         patch("app.services.ai_brain.logger") as mock_logger:
        res = await cerebro.pensar_respuesta("hola", prospect_data=None, history=[])

    assert "colgado" in res
    error_msgs = [str(c) for c in mock_logger.error.call_args_list]
    assert any("AI FALLBACK REASON" in m and "Empty candidates" in m for m in error_msgs), \
        f"El agotamiento de reintentos no dejó rastro forense terminal: {error_msgs}"
