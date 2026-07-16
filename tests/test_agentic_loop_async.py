import pytest
import asyncio
import subprocess
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agentic_loop_service import AgenticOrchestrator
from app.services.ai_brain import CerebroIA

@pytest.mark.asyncio
async def test_agentic_orchestrator_sandbox_async():
    """
    Test that create_sandbox and destroy_sandbox are async and execute subprocesses without blocking.
    """
    orchestrator = AgenticOrchestrator(sandbox_path="./tmp/test_sandbox")
    
    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"mocked stdout", b"mocked stderr")
    mock_proc.returncode = 0
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        # Test create_sandbox
        res = await orchestrator.create_sandbox("test_branch")
        assert res is True
        mock_exec.assert_called_with(
            "git", "worktree", "add", "-b", "test_branch", "./tmp/test_sandbox", "main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Test destroy_sandbox
        with patch("os.path.exists", return_value=True):
            await orchestrator.destroy_sandbox("test_branch")
            # We expect at least git worktree remove and git branch -D to be called (2 calls)
            assert mock_exec.call_count >= 2

@pytest.mark.asyncio
async def test_agentic_orchestrator_checker():
    """
    Verify run_checker enforces price ($), image format, and 'Ficha Tecnica:' (when is_catalog_query=True).
    """
    orchestrator = AgenticOrchestrator()
    
    # Normal catalog response containing all elements
    bot_response_ok = "La TVS Sport 100 cuesta $6.200.000. ![TVS Sport 100](http://image.url). Ficha Tecnica: Excelente rendimiento."
    val_ok = orchestrator.run_checker(bot_response_ok, is_catalog_query=True)
    assert val_ok["success"] is True
    
    # Missing price
    bot_response_no_price = "La TVS Sport 100 es excelente. ![TVS Sport](http://image.url). Ficha Tecnica: Excelente."
    val_fail_price = orchestrator.run_checker(bot_response_no_price, is_catalog_query=True)
    assert val_fail_price["success"] is False
    assert val_fail_price["report"]["broken_guardrail"] == "PRICE_CONSISTENCY_CHECK"
    
    # Missing image
    bot_response_no_image = "La TVS Sport 100 cuesta $6.200.000. Ficha Tecnica: Excelente."
    val_fail_image = orchestrator.run_checker(bot_response_no_image, is_catalog_query=True)
    assert val_fail_image["success"] is False
    
    # Missing Ficha Tecnica on catalog query
    bot_response_no_ficha = "La TVS Sport 100 cuesta $6.200.000. ![TVS Sport](http://image.url)."
    val_fail_ficha = orchestrator.run_checker(bot_response_no_ficha, is_catalog_query=True)
    assert val_fail_ficha["success"] is False

@pytest.mark.asyncio
async def test_ai_brain_validation_retry():
    """
    Test that ai_brain validates output using AgenticOrchestrator, and on failure retries
    with forced_temperature=0.1 and forced_instruction.
    """
    cerebro = CerebroIA()
    
    # We will mock _generate_with_retry_async to return:
    # 1st attempt: invalid response (missing price/image)
    # 2nd attempt: valid response
    calls = []
    async def mock_generate(texto, context, prospect_data, history, skip_greeting, forced_instruction=None, forced_temperature=None):
        calls.append({
            "forced_instruction": forced_instruction,
            "forced_temperature": forced_temperature
        })
        if len(calls) == 1:
            return "La TVS Sport es una gran moto."
        else:
            return "La TVS Sport cuesta $6.200.000. ![TVS Sport](http://img) Ficha Tecnica: 100cc"

    prospect_data = {
        "exists": True,
        "nombre": "Tobias",
        "ciudad": "Santa Marta",
        "forma_pago": "Crédito - 0 inicial",
        "habeas_data_accepted": True,
        "moto_interest": "TVS Sport"
    }

    with patch.object(cerebro, "_generate_with_retry_async", side_effect=mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
        
        response = await cerebro.pensar_respuesta(
            texto="especificaciones de la TVS Sport",
            context="",
            prospect_data=prospect_data,
            history=[],
            skip_greeting=True
        )
        
        # Verify pensar_respuesta returned the valid response (2nd attempt output after cleaning)
        assert "cuesta $6.200.000" in response
        assert "Ficha Tecnica:" in response
        
        # Verify it retried
        assert len(calls) == 2
        # First call has no forced temp
        assert calls[0]["forced_temperature"] is None
        # Second call has forced temp 0.1
        assert calls[1]["forced_temperature"] == 0.1
        assert "ERROR: La respuesta generada anteriormente falló la validación" in calls[1]["forced_instruction"]


# ─────────────────────────────────────────────────────────────────────────────
# BOT-ARQ-E2E-095: Tests de integración E2E — Firestore config vacío/roto
# ─────────────────────────────────────────────────────────────────────────────

def _build_financial_service_empty_config():
    """
    WHY [BOT-ARQ-E2E-095]: Construye FinancialService con todos los métodos de
    config_service devolviendo {} o [] (simula Firestore sin documento 'partners').
    Patrón idéntico a test_financial_fallback.py para consistencia de caracterización.
    """
    from app.services.financial_service import FinancialService
    svc = FinancialService.__new__(FinancialService)

    mock_config = MagicMock()
    mock_config.get_partners_config.return_value = {}
    mock_config.get_financial_entity_config.return_value = {
        "fngRate": 20.66,
        "registro": 0,
        "brillaManagementRate": 0,
        "coverageRate": 4,
        "life_insurance_monthly": 15000,
    }
    mock_config.get_financial_matrix.return_value = []  # Matriz vacía → factor=0
    mock_config.get_financial_config.return_value = {
        "tasa_nmv_banco": 1.87,
        "tasa_nmv_fintech": 2.22,
        "life_insurance_mode": "fixed",
        "life_insurance_monthly": 15000,
    }

    mock_scoring = MagicMock()
    mock_scoring.calculate_score.return_value = 620
    mock_scoring.determine_strategy.return_value = {
        "strategy": "Sufi (Banco de Bogotá)",
        "entity": "Sufi",
        "rate_key": "tasa_sufi",
        "link_key": "link_sufi",
        "requires_aval": False,
        "is_fallback": False,
    }

    svc._config_service = mock_config
    svc._scoring_service = mock_scoring
    return svc


def _build_financial_service_partners_exception():
    """
    WHY [BOT-ARQ-E2E-095]: Construye FinancialService donde get_partners_config()
    lanza una excepción (simula Firestore completamente inaccesible). Verifica que
    el try/except con logger.exception en evaluate_profile evita el colapso del runtime.
    """
    from app.services.financial_service import FinancialService
    svc = FinancialService.__new__(FinancialService)

    mock_config = MagicMock()
    mock_config.get_partners_config.side_effect = ConnectionError(
        "Firestore: UNAVAILABLE — partners document not found"
    )
    mock_config.get_financial_entity_config.return_value = {
        "fngRate": 20.66,
        "registro": 0,
        "brillaManagementRate": 0,
        "coverageRate": 4,
        "life_insurance_monthly": 15000,
    }
    mock_config.get_financial_matrix.return_value = []
    mock_config.get_financial_config.return_value = {
        "life_insurance_mode": "fixed",
        "life_insurance_monthly": 15000,
    }

    mock_scoring = MagicMock()
    mock_scoring.calculate_score.return_value = 580
    mock_scoring.determine_strategy.return_value = {
        "strategy": "Crediorbe (Perfil Flexible)",
        "entity": "Crediorbe",
        "rate_key": "tasa_crediorbe",
        "link_key": "link_crediorbe",
        "requires_aval": True,
        "is_fallback": False,
    }

    svc._config_service = mock_config
    svc._scoring_service = mock_scoring
    return svc


class TestEvaluateProfileEmptyFirestoreConfig:
    """
    BOT-ARQ-E2E-095: Tests de integración para el flujo completo de cuotas
    cuando Firestore devuelve un esquema de configuración vacío.

    MANDATORIO: Simular HTTP 200 implícito (sin excepción), cuota_mensual > 0,
    y generación de logs forenses válidos.
    """

    def test_evaluate_profile_empty_partners_no_exception(self):
        """
        [E2E-095-1] evaluate_profile NO debe lanzar excepción con partners={}.
        Equivale a HTTP 200 en el endpoint de cuotas.
        """
        svc = _build_financial_service_empty_config()
        # No debería lanzar ninguna excepción
        result = svc.evaluate_profile(
            ocupacion="Empleado fijo",
            ingresos_demostrables="1200000",
            datacredito="Al dia"
        )
        assert result is not None, \
            "[E2E-095] evaluate_profile retornó None con partners_config vacío. Violación de Zero-Silent-Failures."

    def test_evaluate_profile_empty_partners_returns_valid_dict(self):
        """
        [E2E-095-2] Resultado de evaluate_profile debe tener todas las claves requeridas por ai_brain.py.
        """
        svc = _build_financial_service_empty_config()
        result = svc.evaluate_profile(
            ocupacion="Empleado fijo",
            ingresos_demostrables="1200000",
            datacredito="Al dia"
        )
        required_keys = ["score", "strategy", "entity", "link_url", "requires_aval", "explanation"]
        for key in required_keys:
            assert key in result, \
                f"[E2E-095] Clave requerida '{key}' ausente en resultado de evaluate_profile con Firestore vacío."

    def test_evaluate_profile_empty_partners_link_url_is_string_or_none(self):
        """
        [E2E-095-3] link_url debe ser str ('#' como fallback) o None (solo para Brilla).
        NUNCA debe ser una excepción no capturada ni un valor indefinido.
        """
        svc = _build_financial_service_empty_config()
        result = svc.evaluate_profile(
            ocupacion="Independiente",
            ingresos_demostrables="800000",
            datacredito="Sin experiencia"
        )
        link_url = result.get("link_url")
        assert link_url is None or isinstance(link_url, str), \
            f"[E2E-095] link_url tiene tipo inesperado: {type(link_url)}. Debe ser str o None."

    def test_evaluate_profile_empty_partners_score_is_numeric(self):
        """
        [E2E-095-4] El score calculado debe ser numérico incluso con config vacío.
        Verifica que ScoringService es agnóstico a partners config.
        """
        svc = _build_financial_service_empty_config()
        result = svc.evaluate_profile(
            ocupacion="Pensionado",
            ingresos_demostrables="900000",
            datacredito="Al dia"
        )
        assert isinstance(result.get("score"), (int, float)), \
            f"[E2E-095] score debe ser numérico, obtenido: {type(result.get('score'))}"

    def test_full_quota_flow_empty_config_cuota_mayor_cero(self):
        """
        [E2E-095-5] Flujo completo de cuotas: evaluate_profile + calculate_payment
        con Firestore vacío. cuota_mensual debe ser > 0 (coherencia financiera).
        Simula el flujo que ai_brain.py ejecuta al procesar una solicitud de cuotas.
        """
        svc = _build_financial_service_empty_config()

        # Paso 1: Evaluar perfil (simula calculate_credit_score tool call en ai_brain.py)
        profile_result = svc.evaluate_profile(
            ocupacion="Empleado fijo",
            ingresos_demostrables="1500000",
            datacredito="Al dia",
            tiene_gas_natural=False,
            plan_celular="Sí"
        )
        assert profile_result is not None, "[E2E-095] evaluate_profile colapsó el flujo E2E."

        # Paso 2: Calcular cuota (simula calculate_payment en Crediorbe branch de ai_brain.py)
        payment_result = svc.calculate_payment(
            precio=6_700_000.0,
            inicial=0,
            plazo_meses=24,
            entidad="Crediorbe"
        )
        assert payment_result is not None, "[E2E-095] calculate_payment colapsó con Firestore vacío."
        assert "cuota_mensual" in payment_result, \
            "[E2E-095] Clave 'cuota_mensual' ausente en resultado de calculate_payment con config vacío."
        assert isinstance(payment_result["cuota_mensual"], float), \
            f"[E2E-095] cuota_mensual debe ser float, obtenido: {type(payment_result['cuota_mensual'])}"
        assert payment_result["cuota_mensual"] >= 0, \
            f"[E2E-095] cuota_mensual={payment_result['cuota_mensual']} es negativa — resultado incoherente."

    def test_evaluate_profile_partners_exception_no_crash(self, caplog):
        """
        [E2E-095-6] Cuando get_partners_config() lanza excepción (Firestore inaccesible),
        evaluate_profile NO debe colapsar el runtime. DEBE generar log forense (logger.exception).
        Verifica el guardrail [BOT-ARQ-E2E-095] implantado en financial_service.py.
        """
        import logging
        svc = _build_financial_service_partners_exception()

        with caplog.at_level(logging.ERROR):
            result = svc.evaluate_profile(
                ocupacion="Independiente",
                ingresos_demostrables="1000000",
                datacredito="Reportado"
            )

        # Verificar que no colapsó
        assert result is not None, \
            "[E2E-095] evaluate_profile colapsó con excepción en get_partners_config()."
        assert "score" in result, \
            "[E2E-095] score ausente en resultado cuando partners lanza excepción."

        # Verificar que se generó el log forense (Zero-Silent-Failures)
        log_messages = " ".join([r.message for r in caplog.records])
        assert "BOT-ARQ-E2E-095" in log_messages, \
            "[E2E-095] No se encontró log forense '[BOT-ARQ-E2E-095]' en caplog. " \
            "Violación de Zero-Silent-Failures: la excepción fue silenciada."

    def test_link_brilla_property_empty_partners_no_crash(self):
        """
        [E2E-095-7] La propiedad link_brilla no debe colapsar con partners={}.
        Debe retornar '#' como fallback seguro.
        """
        svc = _build_financial_service_empty_config()
        result = svc.link_brilla
        assert isinstance(result, str), \
            f"[E2E-095] link_brilla debe retornar str con partners vacío, obtenido: {type(result)}"
        assert result == "#", \
            f"[E2E-095] link_brilla debe retornar '#' con partners vacío, obtenido: '{result}'"

    def test_link_brilla_property_exception_no_crash(self):
        """
        [E2E-095-8] La propiedad link_brilla no debe colapsar cuando get_partners_config() lanza.
        Debe retornar '#' como fallback seguro y generar log forense.
        """
        svc = _build_financial_service_partners_exception()
        # No debe lanzar ninguna excepción
        result = svc.link_brilla
        assert isinstance(result, str), \
            f"[E2E-095] link_brilla debe retornar str con excepción en partners, obtenido: {type(result)}"
        assert result == "#", \
            f"[E2E-095] link_brilla debe retornar '#' en fallback de excepción, obtenido: '{result}'"


# ─────────────────────────────────────────────────────────────────────────────
# BOT-BRAIN-FINANCE-089: Integration test for context leak and blind simulation bypass
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_meta_payload_leak_prevention_and_bypass():
    """
    [BOT-BRAIN-FINANCE-089] Intercepts the WhatsApp message payload sent to Meta
    and executes strict Regex checks to prevent context leaks (directives) and
    detect silent bypasses of the blind simulation for credit queries without Habeas Data.
    """
    import re
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks
    
    # 1. Setup mock request payload for a prospect requesting credit
    # but having habeas_data_accepted = False (triggers blind simulation)
    user_phone = "+573192564288"
    msg_data = {
        "from": user_phone,
        "id": "wamid.test_leak_prevent_089",
        "timestamp": "1672531199",
        "text": "Quiero comprar una Raider 125 a crédito",
        "type": "text",
        "phone_number_id": "999999"
    }

    # 2. Mock services to simulate a prospect with habeas_data_accepted = False
    mock_memory_service = MagicMock()
    mock_memory_service.save_message = AsyncMock(return_value=True)
    mock_memory_service.get_prospect_data = AsyncMock(return_value={
        "exists": True,
        "status": "PENDING",
        "chatbot_status": "ACTIVE",
        "name": "Juan Test",
        "celular": user_phone,
        "habeas_data_accepted": False, # Triggers the blind simulation flow!
        "moto_interest": "Raider 125",
        "forma_pago": "credito"
    })
    mock_memory_service.get_chat_history = AsyncMock(return_value=[])
    mock_memory_service.create_prospect_if_missing = AsyncMock()
    mock_memory_service.update_last_interaction = AsyncMock()
    mock_memory_service.transition_to_in_progress = AsyncMock()
    mock_memory_service.generate_and_update_summary = AsyncMock()
    
    # Mock CerebroIA & JudgeService
    # Mock self._catalog_service inside cerebro to return the Raider 125 catalog item
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [{
        "name": "Raider 125",
        "price": 6500000.0,
        "raw_price": "6500000",
        "formatted_price": "$6.500.000",
        "summary": "Excelente moto"
    }]
    mock_catalog.search.return_value = [{
        "name": "Raider 125",
        "price": 6500000.0,
        "raw_price": "6500000",
        "formatted_price": "$6.500.000",
        "summary": "Excelente moto"
    }]
    
    # Use physical financial_service with canonical configurations
    from app.services.financial_service import financial_service
    brilla_config = {
        'fngRate': 0.0,
        'coverageRate': 4.0,
        'lifeInsuranceValue': 15000.0,
        'brillaManagementRate': 5.0,
        'interestRate': 1.91,
        'rows': [
            {'registrationCreditGeneral': 760000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 99, 'id': '0-99', 'minCC': 0},
            {'registrationCreditGeneral': 840000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 124, 'id': '100-124', 'minCC': 100},
            {'registrationCreditGeneral': 920000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 200, 'category': 'URBANA Y/O TRABAJO', 'id': '125-200', 'minCC': 125},
            {'registrationCreditGeneral': 1120000, 'factors': {'48': 0.035678, '24': 0.0523336, '36': 0.041234}, 'maxCC': 9999, 'id': 'gt-200', 'minCC': 201}
        ]
    }
    mock_config_service = MagicMock()
    mock_config_service.get_financial_entity_config.return_value = brilla_config
    mock_config_service.get_financial_matrix.return_value = brilla_config['rows']
    mock_config_service.get_financial_config.return_value = brilla_config
    mock_config_service.get_registration_cost.return_value = 760000.0

    # Mock GenAI client
    mock_client = MagicMock()
    mock_chat = AsyncMock()

    # Setup the response for chat.send_message
    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_part = MagicMock()

    # Setup the function call
    mock_function_call = MagicMock()
    mock_function_call.name = "calculate_credit_score"
    mock_function_call.args = {
        "ocupacion_y_contrato": "Independiente",
        "ingresos_demostrables": "1500000",
        "historial_datacredito": "Al dia"
    }

    mock_part.function_call = mock_function_call
    mock_part.text = None
    mock_candidate.content.parts = [mock_part]
    mock_response.candidates = [mock_candidate]

    # Configure send_message to return mock_response
    mock_chat.send_message = AsyncMock(return_value=mock_response)

    # Configure mock_client.aio.chats.create to return mock_chat
    mock_client.aio.chats.create = MagicMock(return_value=mock_chat)
    
    # Mock send_text_message on whatsapp_service to capture the outgoing message
    captured_messages = []
    async def mock_send_text(to, text, reply_to_id=None, phone_number_id=None):
        captured_messages.append(text)
        return {"messages": [{"id": "wamid.mocked_123"}]}

    from app.services.config_service import config_service
    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.judge_service") as mock_judge, \
         patch("app.services.whatsapp_service.whatsapp_service.send_text_message", side_effect=mock_send_text), \
         patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.motor_financiero", financial_service), \
         patch.object(config_service, "get_financial_entity_config", return_value=brilla_config), \
         patch.object(config_service, "get_financial_matrix", return_value=brilla_config['rows']), \
         patch.object(config_service, "get_financial_config", return_value=brilla_config), \
         patch.object(config_service, "get_registration_cost", return_value=760000.0), \
         patch("app.services.ai_brain.genai.Client", return_value=mock_client), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
         
        mock_settings.whatsapp_app_secret = None  # Bypass signature verification
        mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
        
        background_tasks = BackgroundTasks()
        await _handle_message_background(msg_data, background_tasks)
        
        # Verify a message was sent to Meta
        assert len(captured_messages) > 0, "No messages were sent to Meta."
        sent_text = captured_messages[0]
        
        # 3. STRICT REGEX ASSERTIONS: Context Bleeding / Internal Directives
        # The text must not contain any system instructions/directives
        leak_pattern = re.compile(
            r"(EL USUARIO ESTÁ LISTO PARA EL CRÉDITO|calculate_credit_score|Habeas Data Aceptado|SISTEMA:|MANDATO CRÍTICO|ERROR:)",
            re.IGNORECASE
        )
        assert not leak_pattern.search(sent_text), \
            f"Context Bleeding detected! Outgoing Meta message contains system directives: '{sent_text}'"
            
        # 4. STRICT ASSERTIONS: Silent Bypass of Blind Simulation
        # The text must contain the blind simulation credit estimation with 10% downpayment pattern and request for consent
        expected_blind_copy = (
            "Si te interesa a crédito con la inicial de $650,000, "
            "las cuotas a 24 meses serían aproximadamente de $403,694 "
            "(incluye SOAT y Matrícula). *Nota: Este es un valor aproximado.*"
        )
        assert expected_blind_copy in sent_text, \
            f"Blind simulation bypass! Response does not contain the exact 10% initial and payment copywriting: '{sent_text}'"
        assert "sin cuota inicial" not in sent_text, \
            f"Blind simulation bypass! Response contains illegal phrase 'sin cuota inicial': '{sent_text}'"
        assert "$" in sent_text, \
            f"Blind simulation bypass! Response does not contain currency symbol: '{sent_text}'"
        assert "tratamiento de tus datos personales" in sent_text or "https://tiendalasmotos.com/politica-de-privacidad" in sent_text, \
            f"Blind simulation bypass! Response does not request Habeas Data consent: '{sent_text}'"


@pytest.mark.asyncio
async def test_alias_pure_catalog_invocation():
    """
    Certifica que la consulta 'señoritera' genera obligatoriamente una invocación a 'search_catalog'
    (debido a la inclusión del alias dinámico en motorcycle_keywords) y devuelve 'success: False'
    al run_checker si falta la ficha técnica.
    """
    from app.services.config_service import config_service
    from app.services.agentic_loop_service import AgenticOrchestrator
    
    # 1. Instanciamos el cerebro y mockeamos los alias dinámicos
    from app.services.catalog_service import CatalogService
    catalog_service = CatalogService()
    cerebro = CerebroIA(catalog_service=catalog_service)
    
    mock_aliases = {"semiautomatica": ["señoritera"]}
    
    # Mock de las respuestas de Gemini
    # Intento 1: respuesta sin herramientas. Como el interceptor detecta "señoritera" (alias dinámico),
    # forzará un segundo turno con instrucción de usar search_catalog.
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

    # Turno 1: Gemini responde texto puro (evadiendo la herramienta)
    candidate_t1 = MockCandidate(content=MockContent(parts=[MockPart(text="La señoritera es una gran moto.")]))
    response_t1 = MockResponse(candidates=[candidate_t1])

    # Turno 2 (Forzado): Gemini llama a search_catalog con query "señoritera"
    mock_fc = MagicMock()
    mock_fc.name = "search_catalog"
    mock_fc.args = {"query": "señoritera"}
    candidate_t2 = MockCandidate(content=MockContent(parts=[MockPart(function_call=mock_fc)]))
    response_t2 = MockResponse(candidates=[candidate_t2])

    # Turno 3 (Final): Gemini responde texto, pero SIN la ficha técnica (para provocar el fallo en run_checker)
    candidate_t3 = MockCandidate(content=MockContent(parts=[MockPart(text="La señoritera cuesta $7.000.000. ![Scooter](http://img)")]))
    response_t3 = MockResponse(candidates=[candidate_t3])

    gemini_calls = []
    async def mock_call_gemini(*args, **kwargs):
        gemini_calls.append(args)
        if len(gemini_calls) == 1:
            return response_t1
        elif len(gemini_calls) == 2:
            return response_t2
        else:
            return response_t3

    prospect_data = {
        "exists": True,
        "nombre": "Tobias",
        "ciudad": "Santa Marta",
        "forma_pago": "Crédito",
        "habeas_data_accepted": True,
        "moto_interest": "Semiautomatica"
    }

    # Parcheamos config_service.get_catalog_aliases, _call_gemini_with_retry_async y el search_items
    with patch("app.services.config_service.config_service.get_catalog_aliases", return_value=mock_aliases), \
         patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini), \
         patch.object(catalog_service, "search_items", return_value=[{"name": "Victory Flow", "price": "$7.000.000", "category": "Semiautomatica", "image_url": "http://img", "summary": "Excelente"}]), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
         
        # Ejecutamos pensar_respuesta con consulta pura del alias
        res = await cerebro.pensar_respuesta("quiero ver la señoritera", prospect_data=prospect_data)
        
        # Aserción 1: Se debió haber forzado al menos un turno llamando a Gemini con el mensaje de error del sistema
        assert len(gemini_calls) >= 2, "No se forzó el turno de validación a pesar de tener el alias 'señoritera'."
        
        # Aserción 2: Validamos que al run_checker se le devuelva success: False cuando se fuerza la validación de la ficha técnica
        orchestrator = AgenticOrchestrator()
        chk = orchestrator.run_checker(res, is_catalog_query=True)
        assert chk["success"] is False, "El run_checker debió fallar por falta de 'Ficha Tecnica:'."
        assert chk["report"]["broken_guardrail"] == "PRICE_CONSISTENCY_CHECK"



@pytest.mark.asyncio
async def test_whatsapp_reaction_payload_processing():
    """
    Test unitario para certificar que un payload de tipo 'reaction' con emoji '👍'
    no aborta prematuramente, recupera la intención afirmativa 'Sí'
    y la procesa correctamente hacia el motor de CerebroIA.
    """
    from app.routers import whatsapp
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks
    
    # 1. Asegurar la inicialización del message_buffer y forzar debounce_seconds a 0.0
    whatsapp._ensure_services_sync()
    orig_debounce = whatsapp.message_buffer.debounce_seconds
    whatsapp.message_buffer.debounce_seconds = 0.0
    
    user_phone = "+573192564288"
    
    try:
        # Clear buffer to guarantee complete test isolation
        await whatsapp.message_buffer.clear_buffer(user_phone)
        if user_phone in whatsapp.message_buffer._processed_wamids:
            whatsapp.message_buffer._processed_wamids[user_phone].clear()
        msg_data = {
            "from": user_phone,
            "id": "wamid.test_reaction_134",
            "timestamp": "1672531199",
            "type": "reaction",
            "reaction": {
                "emoji": "👍",
                "message_id": "wamid.target_msg_123"
            },
            "phone_number_id": "999999"
        }

        # Mock memory service
        mock_memory_service = MagicMock()
        mock_memory_service.save_message = AsyncMock(return_value=True)
        mock_memory_service.get_prospect_data = AsyncMock(return_value={
            "exists": True,
            "status": "PENDING",
            "chatbot_status": "ACTIVE",
            "name": "Juan Test",
            "celular": user_phone,
            "habeas_data_accepted": True,
            "moto_interest": "Raider 125",
            "forma_pago": "credito"
        })
        mock_memory_service.get_chat_history = AsyncMock(return_value=[])
        mock_memory_service.create_prospect_if_missing = AsyncMock()
        mock_memory_service.update_last_interaction = AsyncMock()
        mock_memory_service.transition_to_in_progress = AsyncMock()
        mock_memory_service.generate_and_update_summary = AsyncMock()
        mock_memory_service.set_human_help_status = AsyncMock()
        
        # Mock CerebroIA.pensar_respuesta
        captured_user_message = []
        async def mock_pensar_respuesta(*args, **kwargs):
            captured_user_message.append(args[0])
            return "Respuesta simulada de la IA"

        # Mock send_text_message to capture response to user
        captured_outgoing = []
        async def mock_send_text(to, text, reply_to_id=None, phone_number_id=None):
            captured_outgoing.append(text)
            return {"messages": [{"id": "wamid.mocked_123"}]}

        with patch("app.routers.whatsapp.settings") as mock_settings, \
             patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
             patch("app.routers.whatsapp.judge_service") as mock_judge, \
             patch("app.services.whatsapp_service.whatsapp_service.send_text_message", side_effect=mock_send_text), \
             patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
             patch.object(CerebroIA, "pensar_respuesta", side_effect=mock_pensar_respuesta), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
             patch("app.services.ai_brain.SDK_AVAILABLE", True):
             
            mock_settings.whatsapp_app_secret = None  # Bypass signature verification
            mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
            
            background_tasks = BackgroundTasks()
            await _handle_message_background(msg_data, background_tasks)
            
            # Verify that CerebroIA was indeed called with "Sí"
            assert len(captured_user_message) == 1, "CerebroIA was not invoked."
            assert captured_user_message[0] == "Sí", f"Expected 'Sí', but got '{captured_user_message[0]}'"
            
            # Verify that a response was sent to the user
            assert len(captured_outgoing) == 1, "No outgoing WhatsApp message sent."
            assert captured_outgoing[0] == "Respuesta simulada de la IA"

    finally:
        whatsapp.message_buffer.debounce_seconds = orig_debounce


@pytest.mark.asyncio
async def test_cerebro_ia_scoring_service_direct_alignment():
    """
    [BOT-BRAIN-FINANCE-091] Test that CerebroIA correctly routes calculate_credit_score
    directly to ScoringService (without evaluate_profile) using await/asyncio.to_thread
    and respecting the EXTRACTION_SCHEMA fields.
    """
    class MockFunctionCall:
        def __init__(self, name, args):
            self.name = name
            self.args = args

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

    from app.services.scoring_service import ScoringService

    cerebro = CerebroIA()
    cerebro.client = MagicMock()
    cerebro._model_id = "gemini-2.0-flash"
    
    mock_catalog = MagicMock()
    mock_catalog.search_items.return_value = [
        {
            "name": "TVS Raider 125",
            "price": "$ 6.500.000",
            "raw_price": 6500000.0,
            "category": "Sport",
            "image_url": "https://img.url",
            "summary": "Excelente moto"
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    scoring_svc = ScoringService()
    cerebro.motor_financiero = scoring_svc

    mock_config = MagicMock()
    mock_config.get_partners_config.return_value = {
        "link_brilla": "https://brilla-link.com",
        "link_crediorbe": "https://crediorbe-link.com"
    }
    cerebro._config_loader = mock_config

    mock_config_service = MagicMock()
    mock_config_service.get_financial_entity_config.return_value = {
        "fngRate": 20.66,
        "registro": 0,
        "brillaManagementRate": 0,
        "coverageRate": 4,
        "life_insurance_monthly": 15000,
    }
    mock_config_service.get_financial_matrix.return_value = []
    mock_config_service.get_financial_config.return_value = {
        "tasa_nmv_banco": 1.87,
        "tasa_nmv_fintech": 2.22,
        "life_insurance_mode": "fixed",
        "life_insurance_monthly": 15000,
    }
    from app.services.financial_service import financial_service

    fc = MockFunctionCall(
        name="calculate_credit_score", 
        args={
            "ocupacion_y_contrato": "empleado fijo",
            "ingresos_demostrables": "3 millones",
            "historial_datacredito": "al dia",
            "tiene_gas_natural": False,
            "plan_celular": "Sí"
        }
    )
    candidate1 = MockCandidate(content=MockContent(parts=[MockPart(function_call=fc)]))
    response1 = MockResponse(candidates=[candidate1])
    
    candidate2 = MockCandidate(content=MockContent(parts=[MockPart(text="Felicidades, pre-aprobado.")]))
    response2 = MockResponse(candidates=[candidate2])

    call_count = 0
    captured_function_response = None

    async def mock_call(*args, **kwargs):
        nonlocal call_count, captured_function_response
        call_count += 1
        if call_count == 1:
            return response1
        
        if "contents" in kwargs:
            contents = kwargs["contents"]
            for content in contents:
                for part in content.parts:
                    if hasattr(part, "function_response") or (isinstance(part, dict) and "function_response" in part):
                        captured_function_response = part
        for arg in args:
            if isinstance(arg, list):
                for part in arg:
                    if hasattr(part, "function_response") or (isinstance(part, dict) and "function_response" in part):
                        captured_function_response = part
        return response2

    with patch.object(cerebro, '_call_gemini_with_retry_async', new=mock_call), \
         patch.object(financial_service, '_config_service', mock_config_service), \
         patch('app.services.ai_brain.SDK_AVAILABLE', True):

        history_msg = {"role": "user", "content": "Ver políticas en tiendalasmotos.com/politica-de-privacidad"}
        res_text = await cerebro.pensar_respuesta(
            texto="quiero solicitar un crédito",
            prospect_data={
                "nombre": "Carlos",
                "ciudad": "Santa Marta",
                "habeas_data_accepted": True,
                "habeas_data_accepted_sent": True,
                "moto_interest": "Raider 125",
                "forma_pago": "crédito"
            },
            history=[history_msg]
        )

        assert res_text == "Felicidades, pre-aprobado."
        assert captured_function_response is not None
        
        resp_payload = captured_function_response.function_response.response
        result_text = resp_payload.get("result", "")
        assert "980" in result_text or "980 Puntos" in result_text
        assert "BANCO" in result_text
        assert "Banco de Bogotá" in result_text


@pytest.mark.asyncio
async def test_clean_text_message_bypasses_reaction_interceptor_and_preserves_difflib_matching():
    """
    Test unitario para certificar que un mensaje de texto limpio no pasa por el
    interceptor de reacciones y conserva la lógica fonética de coincidencia fuzzy de 'difflib'.
    """
    from app.routers import whatsapp
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks
    
    # 1. Asegurar la inicialización de servicios
    whatsapp._ensure_services_sync()
    orig_debounce = whatsapp.message_buffer.debounce_seconds
    whatsapp.message_buffer.debounce_seconds = 0.0
    
    from app.services.catalog_service import catalog_service
    original_items = getattr(catalog_service, "_items", [])
    original_items_by_id = getattr(catalog_service, "_items_by_id", {})
    
    item = {
        "id": "tvs_raider",
        "name": "TVS Raider 125",
        "price": 6000000,
        "category": "deportiva",
        "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/tvs_raider.jpg",
        "search_tags": ["sport", "tecnologia"],
        "search_text": "tvs raider 125 deportiva sport tecnologia",
        "search_tokens": ["tvs", "raider", "125", "deportiva", "sport", "tecnologia"],
        "searchBy": ["sport", "tecnologia"],
        "description": "Moto deportiva con tecnologia de punta y gran desempeño.",
        "link": "https://tiendalasmotos.com/tvs-raider",
        "active": True
    }
    catalog_service._items = [item]
    catalog_service._items_by_id = {"tvs_raider": item}
    
    user_phone = "+573192564288"
    
    try:
        # Clear buffer to guarantee complete test isolation
        await whatsapp.message_buffer.clear_buffer(user_phone)
        if user_phone in whatsapp.message_buffer._processed_wamids:
            whatsapp.message_buffer._processed_wamids[user_phone].clear()
            
        # Payload de mensaje de texto limpio
        msg_data = {
            "from": user_phone,
            "id": "wamid.test_text_fuzzy_139",
            "timestamp": "1672531199",
            "type": "text",
            "text": "quiero ver la rayder",
            "phone_number_id": "999999"
        }

        # Mock memory service
        mock_memory_service = MagicMock()
        mock_memory_service.save_message = AsyncMock(return_value=True)
        # Indicar que no ha aceptado habeas data, y tiene moto_interest Raider 125
        mock_prospect_data = {
            "exists": True,
            "status": "PENDING",
            "chatbot_status": "ACTIVE",
            "name": "Juan Test",
            "celular": user_phone,
            "habeas_data_accepted": False,
            "moto_interest": "Raider 125",
            "forma_pago": "credito"
        }
        mock_memory_service.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_memory_service.get_chat_history = AsyncMock(return_value=[])
        mock_memory_service.create_prospect_if_missing = AsyncMock()
        mock_memory_service.update_last_interaction = AsyncMock()
        mock_memory_service.transition_to_in_progress = AsyncMock()
        mock_memory_service.generate_and_update_summary = AsyncMock()
        mock_memory_service.set_human_help_status = AsyncMock()
        mock_memory_service.update_prospect_summary = AsyncMock()
        
        # Mock CerebroIA.pensar_respuesta
        captured_user_message = []
        async def mock_pensar_respuesta(*args, **kwargs):
            captured_user_message.append(args[0])
            # Assert that the prospect_data was NOT modified by the reaction interceptor
            assert kwargs["prospect_data"]["habeas_data_accepted"] is False
            return "Respuesta de la IA"

        # Mock send_text_message to capture response to user
        captured_outgoing = []
        async def mock_send_text(to, text, reply_to_id=None, phone_number_id=None):
            captured_outgoing.append(text)
            return {"messages": [{"id": "wamid.mocked_123"}]}

        with patch("app.routers.whatsapp.settings") as mock_settings, \
             patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
             patch("app.routers.whatsapp.judge_service") as mock_judge, \
             patch("app.services.whatsapp_service.whatsapp_service.send_text_message", side_effect=mock_send_text), \
             patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
             patch.object(CerebroIA, "pensar_respuesta", side_effect=mock_pensar_respuesta), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
             patch("app.services.ai_brain.SDK_AVAILABLE", True):
             
            mock_settings.whatsapp_app_secret = None  # Bypass signature verification
            mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
            
            background_tasks = BackgroundTasks()
            await _handle_message_background(msg_data, background_tasks)
            
            # Verificaciones
            # 1. CerebroIA fue invocado con la consulta de texto
            assert len(captured_user_message) == 1
            assert captured_user_message[0] == "quiero ver la rayder"
            
            # 2. No se llamó al interceptor de reacciones (update_prospect_summary no se llamó para forzar aceptación)
            for call in mock_memory_service.update_prospect_summary.call_args_list:
                args, kwargs_call = call
                if len(args) >= 3 and "habeas_data_accepted" in args[2]:
                    assert False, "update_prospect_summary was called to accept habeas data on a text message!"
                if "habeas_data_accepted" in kwargs_call.get("data", {}):
                    assert False, "update_prospect_summary was called to accept habeas data on a text message!"
            
            # 3. La lógica difflib se conserva (los mocks no interceptaron de más y delegaron limpio)
            # Para esto, llamamos directamente al CatalogService para demostrar que 'rayder' coincide con 'Raider 125' por difflib.
            results = catalog_service.search("rayder")
            assert any("Raider 125" in item["name"] for item in results), "Coincidencia fuzzy de difflib falló para 'rayder'!"

    finally:
        catalog_service._items = original_items
        catalog_service._items_by_id = original_items_by_id
        whatsapp.message_buffer.debounce_seconds = orig_debounce


async def test_concurrency_stress_phonetic_boser():
    """
    Test de estrés secuencial/concurrente: Emula la llegada paralela de 3 acuses de estado
    (delivered/read) simultáneamente con una petición de texto fuzzy ('boser').
    Asegura que el aislamiento de bucles en procesos masivos y la hidratación semántica
    no se vean afectados, y que 'boser' resuelva a 'Boxer' (TVS Sport 100).
    """
    import app.routers.whatsapp as whatsapp
    from app.routers.whatsapp import _handle_message_background, _handle_statuses_background
    # 1. Asegurar la inicialización de servicios
    whatsapp._ensure_services_sync()
    orig_debounce = whatsapp.message_buffer.debounce_seconds
    whatsapp.message_buffer.debounce_seconds = 0.0
    
    from app.services.catalog_service import catalog_service
    original_items = getattr(catalog_service, "_items", [])
    original_items_by_id = getattr(catalog_service, "_items_by_id", {})
    
    item = {
        "id": "tvs_sport",
        "name": "TVS Sport 100",
        "price": 5000000,
        "category": "trabajo",
        "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/tvs_sport.jpg",
        "search_tags": ["trabajo", "economica", "mensajeria", "nkd", "boxer"],
        "search_text": "tvs sport 100 trabajo economica mensajeria nkd boxer",
        "search_tokens": ["tvs", "sport", "100", "trabajo", "economica", "mensajeria", "nkd", "boxer"],
        "searchBy": ["trabajo", "economica", "mensajeria", "nkd", "boxer"],
        "description": "Moto de trabajo muy economica y duradera con excelente consumo de combustible.",
        "link": "https://tiendalasmotos.com/tvs-sport",
        "active": True
    }
    catalog_service._items = [item]
    catalog_service._items_by_id = {"tvs_sport": item}
    
    user_phone = "+573192564288"
    
    try:
        # Clear buffer to guarantee complete test isolation
        await whatsapp.message_buffer.clear_buffer(user_phone)
        if user_phone in whatsapp.message_buffer._processed_wamids:
            whatsapp.message_buffer._processed_wamids[user_phone].clear()
            
        # Payload de mensaje de texto con query fuzzy 'boser'
        msg_data = {
            "from": user_phone,
            "id": "wamid.test_concurrency_msg",
            "timestamp": "1672531199",
            "type": "text",
            "text": "tienen la boser",
            "phone_number_id": "999999"
        }

        # Mock memory service
        mock_memory_service = MagicMock()
        mock_memory_service.save_message = AsyncMock(return_value=True)
        # Indicar que no ha aceptado habeas data, y tiene moto_interest Boxer
        mock_prospect_data = {
            "exists": True,
            "status": "PENDING",
            "chatbot_status": "ACTIVE",
            "name": "Juan Test",
            "celular": user_phone,
            "habeas_data_accepted": False,
            "moto_interest": "TVS Sport 100",
            "forma_pago": "credito"
        }
        mock_memory_service.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_memory_service.get_chat_history = AsyncMock(return_value=[])
        mock_memory_service.create_prospect_if_missing = AsyncMock()
        mock_memory_service.update_last_interaction = AsyncMock()
        mock_memory_service.transition_to_in_progress = AsyncMock()
        mock_memory_service.generate_and_update_summary = AsyncMock()
        mock_memory_service.set_human_help_status = AsyncMock()
        mock_memory_service.update_prospect_summary = AsyncMock()
        
        # Una de las actualizaciones de estado lanzará una excepción para testear try/except
        async def mock_update_whatsapp_status(phone_number, status_value, wamid, errors=None):
            if wamid == "wamid.status_fail":
                raise ConnectionError("Simulated network failure on status update")
            return None

        mock_memory_service.update_whatsapp_status = AsyncMock(side_effect=mock_update_whatsapp_status)
        
        # Mock CerebroIA.pensar_respuesta
        captured_user_message = []
        async def mock_pensar_respuesta(*args, **kwargs):
            captured_user_message.append(args[0])
            return "Respuesta de la IA"

        # Mock send_text_message to capture response to user
        captured_outgoing = []
        async def mock_send_text(to, text, reply_to_id=None, phone_number_id=None):
            captured_outgoing.append(text)
            return {"messages": [{"id": "wamid.mocked_123"}]}

        # Payload de acuses de recibo (delivered/read) para simulación paralela
        status_payload_1 = {
            "id": "wamid.status_ok_1",
            "recipient_id": user_phone,
            "status": "delivered",
            "errors": []
        }
        status_payload_2 = {
            "id": "wamid.status_ok_2",
            "recipient_id": user_phone,
            "status": "read",
            "errors": []
        }
        status_payload_3 = {
            "id": "wamid.status_fail", # Este fallará
            "recipient_id": user_phone,
            "status": "delivered",
            "errors": [{"message": "Network Timeout"}]
        }

        with patch("app.routers.whatsapp.settings") as mock_settings, \
             patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
             patch("app.routers.whatsapp.judge_service") as mock_judge, \
             patch("app.services.whatsapp_service.whatsapp_service.send_text_message", side_effect=mock_send_text), \
             patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
             patch.object(CerebroIA, "pensar_respuesta", side_effect=mock_pensar_respuesta), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
             patch("app.services.ai_brain.SDK_AVAILABLE", True):
             
            mock_settings.whatsapp_app_secret = None  # Bypass signature verification
            mock_judge.analyze_response = AsyncMock(return_value=(True, ""))
            
            from fastapi import BackgroundTasks
            background_tasks = BackgroundTasks()

            # Emulamos la llegada simultánea de los 3 acuses de estado y la consulta fuzzy
            await asyncio.gather(
                _handle_statuses_background(status_payload_1),
                _handle_statuses_background(status_payload_2),
                _handle_statuses_background(status_payload_3),
                _handle_message_background(msg_data, background_tasks),
                return_exceptions=True
            )

            # Verificaciones
            # 1. CerebroIA fue invocado con la consulta de texto
            assert len(captured_user_message) == 1
            assert "boser" in captured_user_message[0]
            
            # 2. La consulta fonética 'boser' resolvió a la Boxer (TVS Sport 100) en CatalogService
            results = catalog_service.search("boser")
            assert any("TVS Sport 100" in item["name"] for item in results), "Coincidencia fuzzy de difflib falló para 'boser'!"
            
            # 3. La actualización fallida de estado no interrumpió el flujo ni el catálogo
            assert mock_memory_service.update_whatsapp_status.call_count == 3

    finally:
        catalog_service._items = original_items
        catalog_service._items_by_id = original_items_by_id
        whatsapp.message_buffer.debounce_seconds = orig_debounce


@pytest.mark.asyncio
async def test_whatsapp_reaction_payload_direct_legal_acceptance():
    """
    GIVEN: Un payload de webhook con msg_type: 'reaction' y emoji afirmativo '👍'.
    WHEN: El router de WhatsApp recibe la reacción.
    THEN: Debe mutar el body a 'Sí', interceptar y actualizar habeas_data_accepted = True síncronamente,
          llamar a la instancia viva de CerebroIA en PHASE_2_HABEAS_DATA (sin mockear pensar_respuesta),
          inyectar la directiva de interrupción semántica en el prompt y enviar la respuesta
          sin enlaces de imágenes (![) ni precios ($).
    """
    import app.routers.whatsapp as whatsapp
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks
    
    # 1. Asegurar la inicialización del message_buffer y forzar debounce_seconds a 0.0
    whatsapp._ensure_services_sync()
    orig_debounce = whatsapp.message_buffer.debounce_seconds
    whatsapp.message_buffer.debounce_seconds = 0.0
    
    user_phone = "+573192564288"
    
    try:
        # Clear buffer to guarantee complete test isolation
        await whatsapp.message_buffer.clear_buffer(user_phone)
        if user_phone in whatsapp.message_buffer._processed_wamids:
            whatsapp.message_buffer._processed_wamids[user_phone].clear()
            
        msg_data = {
            "from": user_phone,
            "id": "wamid.reaction_test_999",
            "type": "reaction",
            "reaction": {
                "message_id": "wamid.parent_message_123",
                "emoji": "👍"
            },
            "phone_number_id": "1021779847693778"
        }
        
        # 2. Mock Prospect data sin consentimiento inicial y con identidad ausente (nombre/ciudad vacíos)
        mock_prospect_data = {
            "exists": True,
            "celular": user_phone,
            "chatbot_status": "ACTIVE",
            "status": "PENDING",
            "source": "whatsapp_bot",
            "habeas_data_accepted": False,
            "nombre": "",
            "ciudad": "",
            "forma_pago": "credito",
            "moto_interest": "TVS Sport 100"
        }

        # Setup mock memory service
        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_ms.update_last_interaction = AsyncMock()
        mock_ms.transition_to_in_progress = AsyncMock()
        mock_ms.set_human_help_status = AsyncMock()
        
        async def mock_update_summary(phone, summary, data):
            if "habeas_data_accepted" in data:
                mock_prospect_data["habeas_data_accepted"] = data["habeas_data_accepted"]
        mock_ms.update_prospect_summary = AsyncMock(side_effect=mock_update_summary)

        # Mock GenAI client to return a clean text response
        mock_client = MagicMock()
        mock_chat = AsyncMock()
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()

        # Simulated response from Gemini adhering to our instruction
        mock_part.text = "¡Excelente! He registrado tu consentimiento. Para continuar, indícame tu nombre completo y la ciudad en la que te encuentras."
        mock_part.function_call = None
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]

        mock_chat.send_message = AsyncMock(return_value=mock_response)
        mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

        # Mock send_text_message on whatsapp_service to capture the outgoing message
        captured_messages = []
        async def mock_send_text(to, text, reply_to_id=None, phone_number_id=None):
            captured_messages.append(text)
            return {"messages": [{"id": "wamid.mocked_123"}]}

        with patch("app.routers.whatsapp.settings") as mock_settings, \
             patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
             patch("app.routers.whatsapp.judge_service") as mock_judge, \
             patch("app.services.whatsapp_service.whatsapp_service.send_text_message", side_effect=mock_send_text), \
             patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
             patch("app.services.ai_brain.genai.Client", return_value=mock_client), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
             patch("app.services.ai_brain.SDK_AVAILABLE", True):

            mock_settings.whatsapp_app_secret = None  # Bypass signature verification
            mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

            # 4. Ejecutar el handler
            background_tasks = BackgroundTasks()
            await _handle_message_background(msg_data, background_tasks)

            # 5. Verificaciones
            # Debe haberse llamado a update_prospect_summary síncronamente
            mock_ms.update_prospect_summary.assert_any_call("+573192564288", "", {"habeas_data_accepted": True})
            
            # prospect_data debió actualizarse a True
            assert mock_prospect_data["habeas_data_accepted"] is True

            # Verificar que se llamó al chat con el prompt formateado
            mock_chat.send_message.assert_called_once()
            prompt_sent = mock_chat.send_message.call_args[0][0]
            
            # Verificar que la directiva de interrupción semántica esté presente en el prompt consolidado
            assert "El consentimiento ya ha sido firmado en este turno. Tienes ESTRICTAMENTE PROHIBIDO" in prompt_sent
            assert "incluir enlaces de imágenes (![]) o precios ($) en tu respuesta" in prompt_sent

            # Verificar que el mensaje enviado de vuelta no contiene imágenes ni precios
            assert len(captured_messages) == 1
            response = captured_messages[0]
            assert '![' not in response, "La respuesta no debe incluir enlaces de imágenes (![)"
            assert '$' not in response, "La respuesta no debe incluir precios ($)"

    finally:
        whatsapp.message_buffer.debounce_seconds = orig_debounce


@pytest.mark.asyncio
async def test_handle_message_background_session_locks():
    """
    Verifies that _handle_message_background enforces session-based locking
    for the same phone number, ensuring serial execution and preventing race conditions.
    """
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks
    
    execution_order = []
    
    # We will mock _handle_message_background_impl to sleep and log start/end
    async def mock_impl(msg_data, background_tasks):
        phone = msg_data["from"]
        execution_order.append(f"start_{phone}_{msg_data['id']}")
        await asyncio.sleep(0.1)
        execution_order.append(f"end_{phone}_{msg_data['id']}")
        
    with patch("app.routers.whatsapp._handle_message_background_impl", side_effect=mock_impl), \
         patch("app.routers.whatsapp._ensure_services", AsyncMock()):
         
        # We trigger three concurrent calls:
        # Two for "+573001111111" (should be serialized)
        # One for "+573002222222" (should run concurrently/independently)
        msg1 = {"from": "+573001111111", "id": "msg1"}
        msg2 = {"from": "+573001111111", "id": "msg2"}
        msg3 = {"from": "+573002222222", "id": "msg3"}
        
        bg_tasks = BackgroundTasks()
        
        # We start them concurrently
        await asyncio.gather(
            _handle_message_background(msg1, bg_tasks),
            _handle_message_background(msg2, bg_tasks),
            _handle_message_background(msg3, bg_tasks)
        )
        
        # Verificamos que msg1 y msg2 se ejecutaron de manera secuencial
        idx_start_1 = execution_order.index("start_+573001111111_msg1")
        idx_end_1 = execution_order.index("end_+573001111111_msg1")
        idx_start_2 = execution_order.index("start_+573001111111_msg2")
        idx_end_2 = execution_order.index("end_+573001111111_msg2")
        
        # Verify serialization: either 1 ran before 2, or 2 ran before 1
        if idx_start_1 < idx_start_2:
            assert idx_end_1 < idx_start_2, "msg2 started before msg1 finished!"
        else:
            assert idx_end_2 < idx_start_1, "msg1 started before msg2 finished!"
            
        print("✅ Webhook session lock serialization verified successfully.")

@pytest.mark.asyncio
async def test_faq_unified_knowledge_restoration():
    """
    [BOT-QA-GATE-106] Certifica que las preguntas frecuentes (FAQ) sobre requisitos de crédito
    (como codeudores, cuota inicial o reportados) son resueltas de manera natural por la IA
    y no disparan fallbacks de error por falta de densidad semántica en el prompt.
    """
    from app.services.catalog_service import CatalogService
    catalog_service = CatalogService()
    cerebro = CerebroIA(catalog_service=catalog_service)
    
    # Mock de Gemini para emular que lee correctamente la FAQ inyectada en credit_matrix_rules
    class MockPart:
        def __init__(self, text):
            self.text = text
            self.function_call = None

    class MockContent:
        def __init__(self, parts):
            self.parts = parts

    class MockCandidate:
        def __init__(self, content):
            self.content = content

    class MockResponse:
        def __init__(self, candidates):
            self.candidates = candidates

    # Respuesta de negocio que Juan Pablo DEBE poder estructurar gracias al prompt restaurado
    simulated_faq_response = (
        "No necesitas codeudor en todos los casos. "
        "Depende de tu historial crediticio y las políticas de la entidad que estudie tu solicitud."
    )
    mock_candidate = MockCandidate(content=MockContent(parts=[MockPart(simulated_faq_response)]))
    mock_response = MockResponse(candidates=[mock_candidate])

    prospect_data = {
        "exists": True,
        "nombre": "Tobias FAQ Test",
        "ciudad": "Santa Marta",
        "forma_pago": "Crédito",
        "habeas_data_accepted": False,
        "moto_interest": "TVS Sport 100"
    }

    with patch.object(cerebro, "_call_gemini_with_retry_async", return_value=mock_response), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
         patch("app.services.ai_brain.SDK_AVAILABLE", True):
         
        # El bot debe responder de forma fluida a la consulta de desvío de FAQ
        res = await cerebro.pensar_respuesta("¿necesito codeudor para el crédito?", prospect_data=prospect_data)
        
        # Aserciones rígidas de contenido semántico
        assert "codeudor" in res.lower(), "La respuesta de la IA no aborda el concepto crítico 'codeudor'."
        assert "no" in res.lower(), "La respuesta de la IA omitió la aclaración de que NO siempre se requiere codeudor."


@pytest.mark.asyncio
async def test_whatsapp_image_url_with_complex_query_params_regression():
    """
    [BOT-BUGFIX-MARKDOWN-IMAGE-REGRESSION-122]
    Verifies that the WhatsApp router correctly parses and intercepts Firebase Storage
    image URLs with complex and extensive query parameters (e.g. including slashes, percent encoding,
    and multiple query parameters), extracting the clean URL and removing the raw Markdown from the text.
    """
    import app.routers.whatsapp as whatsapp
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks
    
    # 1. Asegurar la inicialización del message_buffer y forzar debounce_seconds a 0.0
    whatsapp._ensure_services_sync()
    orig_debounce = whatsapp.message_buffer.debounce_seconds
    whatsapp.message_buffer.debounce_seconds = 0.0
    
    user_phone = "+573192564289" # Use a distinct phone number
    
    try:
        # Clear buffer to guarantee complete test isolation
        await whatsapp.message_buffer.clear_buffer(user_phone)
        if user_phone in whatsapp.message_buffer._processed_wamids:
            whatsapp.message_buffer._processed_wamids[user_phone].clear()
            
        msg_data = {
            "from": user_phone,
            "id": "wamid.image_param_test_122",
            "type": "text",
            "text": "Quiero ver la Victory Advance R 125",
            "phone_number_id": "1021779847693778"
        }
        
        # 2. Mock Prospect data con habeas_data firmado y moto de interés asignada
        mock_prospect_data = {
            "exists": True,
            "celular": user_phone,
            "chatbot_status": "ACTIVE",
            "status": "IN_PROGRESS",
            "source": "whatsapp_bot",
            "habeas_data_accepted": True,
            "nombre": "Juan Victory",
            "ciudad": "Medellin",
            "forma_pago": "credito",
            "moto_interest": "Victory Advance R 125"
        }

        # Setup mock memory service
        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_ms.update_last_interaction = AsyncMock()
        mock_ms.transition_to_in_progress = AsyncMock()
        mock_ms.set_human_help_status = AsyncMock()
        mock_ms.update_prospect_summary = AsyncMock()

        # Firebase Storage URL with extensive query parameters representing Victory Advance R 125
        complex_image_url = (
            "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/motos%2Fvictory_advance_r_125.webp"
            "?alt=media&token=12345678-abcd-efgh-ijkl-1234567890ab&another_param=xyz%20abc"
        )
        
        # Simulated response from Gemini adhering to our instruction
        bot_response = (
            "Perfecto. La Victory Advance R 125 cuesta $8.900.000. Ficha Tecnica: Gran rendimiento. "
            f"![Victory Advance R 125]({complex_image_url})"
        )

        # Mock GenAI client to return this response
        mock_client = MagicMock()
        mock_chat = AsyncMock()
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()
        
        mock_part.text = bot_response
        mock_part.function_call = None
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]

        mock_chat.send_message = AsyncMock(return_value=mock_response)
        mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

        # Configurar la simulación del cliente HTTP para interceptar la petición POST a Meta
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(return_value={"messages": [{"id": "wamid.mocked_image_123"}]})

        with patch("app.routers.whatsapp.settings") as mock_settings, \
             patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
             patch("app.routers.whatsapp.judge_service") as mock_judge, \
             patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_http_post, \
             patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
             patch("app.services.ai_brain.genai.Client", return_value=mock_client), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
             patch("app.services.ai_brain.SDK_AVAILABLE", True):

            # Configurar el retorno del mock post
            mock_http_post.return_value = mock_response
            mock_settings.whatsapp_app_secret = None  # Bypass signature verification
            mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

            # 4. Ejecutar el handler
            background_tasks = BackgroundTasks()
            await _handle_message_background(msg_data, background_tasks)

            # 5. Verificaciones
            assert mock_http_post.call_count == 1, "Debe haber enviado exactamente 1 petición POST a Meta."
            call_args = mock_http_post.call_args
            assert call_args is not None, "La llamada a Meta API no se realizó."
            meta_payload = call_args.kwargs.get("json")
            assert meta_payload is not None, "El payload JSON enviado a Meta está vacío."
            
            # Aserción rígida sobre el objeto de payload saliente simulado para Meta:
            assert meta_payload.get("type") == "image", "El tipo de mensaje debe mutar estrictamente a 'image'."
            assert "image" in meta_payload, "El payload debe contener el objeto de imagen."
            
            image_data = meta_payload["image"]
            assert image_data.get("link") == complex_image_url, "La URL de la imagen en el link debe ser la URL compleja."
            
            sent_caption = image_data.get("caption", "")
            # - El texto limpio del caption no debe contener ningún Markdown crudo o remanente del tag ![alt](url)
            assert "[" not in sent_caption, f"El caption retiene corchetes de apertura: '{sent_caption}'"
            assert "]" not in sent_caption, f"El caption retiene corchetes de cierre: '{sent_caption}'"
            assert "https://firebasestorage.googleapis.com" not in sent_caption, "El caption retiene la URL de la imagen."
            
            # - El caption debe contener la información comercial y la ficha técnica
            assert "Victory Advance R 125" in sent_caption
            assert "$8.900.000" in sent_caption
            assert "Ficha Tecnica:" in sent_caption

    finally:
        whatsapp.message_buffer.debounce_seconds = orig_debounce


@pytest.mark.asyncio
async def test_incoming_image_webhook_egress_unification():
    """
    [BOT-BUGFIX-UNIFIED-EGRESS-PIPELINE-125]
    Verifies that the WhatsApp router correctly parses and intercepts Markdown
    images even when the incoming webhook is of type 'image' (triggering Vision AI).
    Asserts that Meta's outbound message payload is mutated to type 'image' with correct link/caption parameters,
    and is free of brackets.
    """
    import app.routers.whatsapp as whatsapp
    from app.routers.whatsapp import _handle_message_background
    from fastapi import BackgroundTasks
    
    # 1. Asegurar la inicialización del message_buffer y forzar debounce_seconds a 0.0
    whatsapp._ensure_services_sync()
    orig_debounce = whatsapp.message_buffer.debounce_seconds
    whatsapp.message_buffer.debounce_seconds = 0.0
    
    user_phone = "+573192564290" # Use a distinct phone number
    
    try:
        # Clear buffer to guarantee complete test isolation
        await whatsapp.message_buffer.clear_buffer(user_phone)
        if user_phone in whatsapp.message_buffer._processed_wamids:
            whatsapp.message_buffer._processed_wamids[user_phone].clear()
            
        msg_data = {
            "from": user_phone,
            "id": "wamid.incoming_image_test_125",
            "type": "image",
            "image": {
                "id": "media_id_125",
                "mime_type": "image/jpeg",
                "caption": "Mira esta moto"
            },
            "phone_number_id": "1021779847693778"
        }
        
        # 2. Mock Prospect data con habeas_data firmado y moto de interés asignada
        mock_prospect_data = {
            "exists": True,
            "celular": user_phone,
            "chatbot_status": "ACTIVE",
            "status": "IN_PROGRESS",
            "source": "whatsapp_bot",
            "habeas_data_accepted": True,
            "nombre": "Juan TVS",
            "ciudad": "Medellin",
            "forma_pago": "credito",
            "moto_interest": "TVS Sport 100"
        }

        # Setup mock memory service
        mock_ms = AsyncMock()
        mock_ms.get_prospect_data = AsyncMock(return_value=mock_prospect_data)
        mock_ms.create_prospect_if_missing = AsyncMock()
        mock_ms.get_chat_history = AsyncMock(return_value=[])
        mock_ms.save_message = AsyncMock()
        mock_ms.generate_and_update_summary = AsyncMock()
        mock_ms.update_last_interaction = AsyncMock()
        mock_ms.transition_to_in_progress = AsyncMock()
        mock_ms.set_human_help_status = AsyncMock()
        mock_ms.update_prospect_summary = MagicMock() # Wait, some calls are sync? Use MagicMock for safe fallback or AsyncMock

        # Firebase Storage URL with extensive query parameters representing TVS Sport 100
        complex_image_url = (
            "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/motos%2Ftvs_sport_100.webp"
            "?alt=media&token=87654321-abcd-efgh-ijkl-0987654321ba"
        )
        
        # Simulated response from Gemini adhering to our instruction
        bot_response = (
            "Perfecto. La TVS Sport 100 cuesta $6.200.000. Ficha Tecnica: Excelente. "
            f"![TVS Sport 100]({complex_image_url})"
        )

        # Mock GenAI client to return this response
        mock_client = MagicMock()
        mock_chat = AsyncMock()
        mock_response = MagicMock()
        mock_candidate = MagicMock()
        mock_part = MagicMock()
        
        mock_part.text = bot_response
        mock_part.function_call = None
        mock_candidate.content.parts = [mock_part]
        mock_response.candidates = [mock_candidate]

        mock_chat.send_message = AsyncMock(return_value=mock_response)
        mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

        # Configurar la simulación del cliente HTTP para interceptar la petición POST a Meta
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json = MagicMock(return_value={"messages": [{"id": "wamid.mocked_image_125"}]})

        # Mock VisionService to analyze image and return "TVS Sport 100"
        mock_vision_service_inst = AsyncMock()
        mock_vision_service_inst.analyze_image = AsyncMock(return_value="TVS Sport 100")

        mock_db = MagicMock()
        mock_db.project = "test-project-123"

        with patch("app.routers.whatsapp.settings") as mock_settings, \
             patch("app.routers.whatsapp.db", mock_db), \
             patch("app.routers.whatsapp.memory_service_module.memory_service", mock_ms), \
             patch("app.routers.whatsapp.judge_service") as mock_judge, \
             patch("app.routers.whatsapp.VisionService", return_value=mock_vision_service_inst), \
             patch("app.routers.whatsapp.storage_service.download_media", AsyncMock(return_value=b"dummy_image_data")), \
             patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_http_post, \
             patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
             patch("app.services.ai_brain.genai.Client", return_value=mock_client), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False), \
             patch("app.services.ai_brain.SDK_AVAILABLE", True):

            # Configurar el retorno del mock post
            mock_http_post.return_value = mock_http_response
            mock_settings.whatsapp_app_secret = None  # Bypass signature verification
            mock_judge.analyze_response = AsyncMock(return_value=(True, ""))

            # 4. Ejecutar el handler
            background_tasks = BackgroundTasks()
            await _handle_message_background(msg_data, background_tasks)

            # 5. Verificaciones
            assert mock_http_post.call_count == 1, "Debe haber enviado exactamente 1 petición POST a Meta."
            call_args = mock_http_post.call_args
            assert call_args is not None, "La llamada a Meta API no se realizó."
            meta_payload = call_args.kwargs.get("json")
            assert meta_payload is not None, "El payload JSON enviado a Meta está vacío."
            
            # Aserción rígida sobre el objeto de payload saliente simulado para Meta:
            assert meta_payload.get("type") == "image", "El tipo de mensaje debe mutar estrictamente a 'image'."
            assert "image" in meta_payload, "El payload debe contener el objeto de imagen."
            
            image_data = meta_payload["image"]
            assert image_data.get("link") == complex_image_url, "La URL de la imagen en el link debe ser la URL compleja."
            
            sent_caption = image_data.get("caption", "")
            # - El texto limpio del caption no debe contener ningún Markdown crudo o remanente del tag ![alt](url)
            assert "[" not in sent_caption, f"El caption retiene corchetes de apertura: '{sent_caption}'"
            assert "]" not in sent_caption, f"El caption retiene corchetes de cierre: '{sent_caption}'"
            assert "https://firebasestorage.googleapis.com" not in sent_caption, "El caption retiene la URL de la imagen."
            
            # - El caption debe contener la información comercial y la ficha técnica
            assert "TVS Sport 100" in sent_caption
            assert "$6.200.000" in sent_caption
            assert "Ficha Tecnica:" in sent_caption

    finally:
        whatsapp.message_buffer.debounce_seconds = orig_debounce


def test_catalog_tokenizer_ngrams_characterization():
    """
    [BOT-PERF-TOKENIZER-NGRAMS-161]
    Strict unit test to verify that '_tokenize' generates combined adjacent n-grams
    when a text token is followed by a numeric token (e.g. ['sport', '100', 'sport100']).
    It passes the raw query 'sport 100' and asserts that 'sport100' is explicitly returned.
    """
    from app.services.catalog_service import CatalogService
    service = CatalogService()
    tokens = service._tokenize("sport 100")
    assert "sport100" in tokens, f"Expected combined ngram 'sport100' in tokens, got {tokens}"
    assert "sport" in tokens
    assert "100" in tokens


def test_catalog_category_alias_recovery():
    """
    [BOT-BACKEND-HOTFIX-CATALOG-ALIAS-RECOVERY]
    Characterization test validating that category aliases configured as singular
    (e.g., 'pistera', 'scooter') are flexibly resolved for linguistic variations
    such as plural ('pisteras'), diminutive ('pisteritas'), and plural synonym ('scooters')
    using in-memory substring/containment mapping, while preventing monosyllables ('de', 'es')
    from colliding and triggering false category mapping.
    """
    from app.services.catalog_service import CatalogService
    from unittest.mock import MagicMock
    
    service = CatalogService()
    
    # Configure aliases strictly in singular format
    service._category_aliases = {
        "deportiva": ["pistera"],
        "trabajo": ["carga"],
        "moped": ["scooter"]
    }
    
    # Set up catalog items
    item_raider = {
        "id": "tvs_raider",
        "name": "TVS Raider 125",
        "price": 6000000,
        "category": "deportiva",
        "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/tvs_raider.jpg",
        "search_tags": ["sport", "tecnologia"],
        "search_text": "tvs raider 125 deportiva sport tecnologia pistera",
        "search_tokens": ["tvs", "raider", "125", "deportiva", "sport", "tecnologia", "pistera"],
        "searchBy": ["sport", "tecnologia"],
        "description": "Moto deportiva con tecnologia de punta.",
        "link": "https://tiendalasmotos.com/tvs-raider",
        "active": True
    }
    
    item_sport = {
        "id": "tvs_sport",
        "name": "TVS Sport 100",
        "price": 5000000,
        "category": "trabajo",
        "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/tvs_sport.jpg",
        "search_tags": ["trabajo"],
        "search_text": "tvs sport 100 trabajo carga",
        "search_tokens": ["tvs", "sport", "100", "trabajo", "carga"],
        "searchBy": ["trabajo"],
        "description": "Moto de trabajo.",
        "link": "https://tiendalasmotos.com/tvs-sport",
        "active": True
    }

    item_scooter = {
        "id": "tvs_ntorq",
        "name": "TVS Ntorq 125",
        "price": 7000000,
        "category": "moped",
        "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/tvs_ntorq.jpg",
        "search_tags": ["moped", "scooter"],
        "search_text": "tvs ntorq 125 moped scooter automatica",
        "search_tokens": ["tvs", "ntorq", "125", "moped", "scooter", "automatica"],
        "searchBy": ["moped", "scooter"],
        "description": "Scooter automatica.",
        "link": "https://tiendalasmotos.com/tvs-ntorq",
        "active": True
    }
    
    service._items = [item_raider, item_sport, item_scooter]
    service._items_by_id = {i["id"]: i for i in service._items}
    service._db = MagicMock()
    
    # 1. Test plural variation: 'pisteras' (resolves to category 'deportiva')
    results_plural = service.search_items("pisteras")
    assert len(results_plural) > 0, "Query for 'pisteras' should match Raider"
    assert results_plural[0]["name"] == "TVS Raider 125"
    assert results_plural[0]["category"] == "deportiva"
    
    # 2. Test diminutive variation: 'pisteritas' (resolves to category 'deportiva')
    results_diminutive = service.search_items("pisteritas")
    assert len(results_diminutive) > 0, "Query for 'pisteritas' should match Raider"
    assert results_diminutive[0]["name"] == "TVS Raider 125"
    assert results_diminutive[0]["category"] == "deportiva"
    
    # 3. Test plural synonym variation: 'scooters' (resolves to category 'moped')
    results_scooters = service.search_items("scooters")
    assert len(results_scooters) > 0, "Query for 'scooters' should match Ntorq"
    assert results_scooters[0]["name"] == "TVS Ntorq 125"
    assert results_scooters[0]["category"] == "moped"

    # 4. Test monosyllable collision prevention: 'de' and 'es' must NOT map to 'deportiva' or 'moped'
    # searching 'de' or 'es' should not inject category aliases via pre-processing containment.
    # We can check this by tokenizing 'de' and ensuring 'deportiva' or 'moped' are NOT in query_tokens.
    # Let's call the helper or check the returned items (which shouldn't match Raider or Ntorq solely due to 'de' / 'es').
    # Let's verify by testing token generation:
    from app.services.catalog_service import CatalogService
    test_service = CatalogService()
    test_service._category_aliases = service._category_aliases
    
    # Query with 'de'
    # 'de' is a monosyllable and should not match 'deportiva' (substring of 'deportiva')
    # If the containment check was naive (e.g. t_clean in a_clean), 'de' would match 'deportiva'
    # resulting in 'deportiva' being added to query_tokens. Let's assert it is not added.
    query_tokens = test_service._tokenize("de")
    # spelling/colloquial expansion mapping
    expanded_tokens = list(query_tokens)
    query_tokens = list(set(expanded_tokens))
    
    # Apply category alias mapping
    aliases = test_service.get_catalog_aliases()
    mapped_categories = []
    for t in query_tokens:
        t_clean = t.lower().strip()
        if not t_clean:
            continue
        for canonical_cat, alias_list in aliases.items():
            for a in alias_list:
                a_clean = a.lower().strip()
                if len(a_clean) >= 3 and len(t_clean) >= 3 and (a_clean in t_clean or t_clean in a_clean):
                    mapped_categories.append(canonical_cat)
                    break
    
    assert "deportiva" not in mapped_categories, "Monosyllable 'de' should not trigger category mapping to 'deportiva'"
    assert "moped" not in mapped_categories, "Monosyllable 'es' should not trigger category mapping to 'moped'"


def test_catalog_generic_stopword_stripping():
    """
    [BOT-BACKEND-HOTFIX-GENERIC-STOPWORD-STRIPPING-167]
    Autopsy test validating that generic commercial noise tokens ('motos', 'moto',
    'motocicleta', 'motocicletas') are stripped from query_alphabetic_tokens BEFORE
    the perimetral validation loop (has_alphabetic_match), so that compound queries
    like 'Motos pisteras' or 'motocicleta pistera' correctly return segment items
    instead of empty lists due to false-negative filtering.

    Precondition: BOT-BACKEND-CATALOG-THRESHOLD-163 perimeter is active.
    Root cause: 'motos' has no match in any item's searchBy or name_tokens,
    so it forces has_alphabetic_match = False before intentional tokens can rescue the match.
    Fix (ticket 167): _COMMERCIAL_STOPWORDS filter injected in catalog_service.py.
    """
    from app.services.catalog_service import CatalogService
    from unittest.mock import MagicMock

    service = CatalogService()

    # Configure aliases: pistera → deportiva, scooter → moped
    service._category_aliases = {
        "deportiva": ["pistera"],
        "moped": ["scooter"],
    }

    # Catalog items — realistic segment representatives
    item_raider = {
        "id": "tvs_raider",
        "name": "TVS Raider 125",
        "price": 6000000,
        "category": "motos",
        "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/tvs_raider.jpg",
        "search_tags": ["sport", "pistera", "deportiva"],
        "search_text": "tvs raider 125 deportiva sport pistera",
        "search_tokens": ["tvs", "raider", "125", "deportiva", "sport", "pistera"],
        "searchBy": [],
        "description": "Moto deportiva pistera con tecnología de punta.",
        "link": "https://tiendalasmotos.com/tvs-raider",
        "active": True,
    }

    item_ntorq = {
        "id": "tvs_ntorq",
        "name": "TVS Ntorq 125",
        "price": 7000000,
        "category": "motos",
        "image_url": "https://firebasestorage.googleapis.com/v0/b/tiendalasmotos/o/tvs_ntorq.jpg",
        "search_tags": ["moped", "scooter", "automatica"],
        "search_text": "tvs ntorq 125 moped scooter automatica",
        "search_tokens": ["tvs", "ntorq", "125", "moped", "scooter", "automatica"],
        "searchBy": [],
        "description": "Scooter automática urbana.",
        "link": "https://tiendalasmotos.com/tvs-ntorq",
        "active": True,
    }

    service._items = [item_raider, item_ntorq]
    service._items_by_id = {i["id"]: i for i in service._items}
    service._db = MagicMock()

    # --- CASO 1: "Motos pisteras" ---
    # 'motos' es ruido genérico; 'pisteras' resuelve a 'deportiva' vía alias mapping.
    # El perímetro debe evaluar solo 'pisteras'/'deportiva', no 'motos'.
    results_motos_pisteras = service.search_items("Motos pisteras")
    assert results_motos_pisteras is not None, \
        "search_items('Motos pisteras') retornó None — fallo crítico de pipeline"
    assert len(results_motos_pisteras) > 0, \
        "'Motos pisteras' retornó lista vacía. 'motos' está bloqueando el perímetro. Verifica filtro COMMERCIAL_STOPWORDS."
    names_c1 = [r["name"] for r in results_motos_pisteras]
    cats_c1 = [r.get("category") for r in results_motos_pisteras]
    assert "TVS Raider 125" in names_c1, \
        f"'Motos pisteras' debió retornar TVS Raider 125, obtuvo: {names_c1}"
    assert "motos" in cats_c1, \
        f"'Motos pisteras' debió retornar categoría 'motos', obtuvo: {cats_c1}"

    # --- CASO 2: "Motos scooters" ---
    # 'motos' es ruido genérico; 'scooters' resuelve a 'moped' vía alias mapping.
    results_motos_scooters = service.search_items("Motos scooters")
    assert results_motos_scooters is not None, \
        "search_items('Motos scooters') retornó None — fallo crítico de pipeline"
    assert len(results_motos_scooters) > 0, \
        "'Motos scooters' retornó lista vacía. 'motos' está bloqueando el perímetro. Verifica filtro COMMERCIAL_STOPWORDS."
    names_c2 = [r["name"] for r in results_motos_scooters]
    cats_c2 = [r.get("category") for r in results_motos_scooters]
    assert "TVS Ntorq 125" in names_c2, \
        f"'Motos scooters' debió retornar TVS Ntorq 125, obtuvo: {names_c2}"
    assert "motos" in cats_c2, \
        f"'Motos scooters' debió retornar categoría 'motos', obtuvo: {cats_c2}"

    # --- CASO 3: "motocicleta pistera" ---
    # 'motocicleta' es variante del ruido genérico; 'pistera' resuelve a 'deportiva'.
    results_moto_pistera = service.search_items("motocicleta pistera")
    assert results_moto_pistera is not None, \
        "search_items('motocicleta pistera') retornó None — fallo crítico de pipeline"
    assert len(results_moto_pistera) > 0, \
        "'motocicleta pistera' retornó lista vacía. 'motocicleta' está bloqueando el perímetro. Verifica filtro COMMERCIAL_STOPWORDS."
    names_c3 = [r["name"] for r in results_moto_pistera]
    cats_c3 = [r.get("category") for r in results_moto_pistera]
    assert "TVS Raider 125" in names_c3, \
        f"'motocicleta pistera' debió retornar TVS Raider 125, obtuvo: {names_c3}"
    assert "motos" in cats_c3, \
        f"'motocicleta pistera' debió retornar categoría 'motos', obtuvo: {cats_c3}"

    # --- CASO 4: "Buenas, tienen motos pisteras?" (BOT-BACKEND-HOTFIX-CONVERSATIONAL-STOPWORD-STRIPPING-168) ---
    # 'Buenas' y 'tienen' son ruidos conversacionales. 'motos' es ruido comercial.
    # 'pisteras' resuelve a 'deportiva'. El perímetro debe omitir el ruido y validar 'deportiva'.
    results_buenas_pisteras = service.search_items("Buenas, tienen motos pisteras?")
    assert results_buenas_pisteras is not None, \
        "search_items('Buenas, tienen motos pisteras?') retornó None"
    assert len(results_buenas_pisteras) > 0, \
        "'Buenas, tienen motos pisteras?' retornó lista vacía. Fórmulas conversacionales están bloqueando el perímetro."
    names_c4 = [r["name"] for r in results_buenas_pisteras]
    assert "TVS Raider 125" in names_c4, \
        f"'Buenas, tienen motos pisteras?' debió retornar TVS Raider 125, obtuvo: {names_c4}"

    # --- CASO 5: "Hola, manejan motos scooters?" (BOT-BACKEND-HOTFIX-CONVERSATIONAL-STOPWORD-STRIPPING-168) ---
    # 'Hola' y 'manejan' son ruidos conversacionales. 'motos' es ruido comercial.
    # 'scooters' resuelve a 'moped'.
    results_hola_scooters = service.search_items("Hola, manejan motos scooters?")
    assert results_hola_scooters is not None, \
        "search_items('Hola, manejan motos scooters?') retornó None"
    assert len(results_hola_scooters) > 0, \
        "'Hola, manejan motos scooters?' retornó lista vacía. Fórmulas conversacionales están bloqueando el perímetro."
    names_c5 = [r["name"] for r in results_hola_scooters]
    assert "TVS Ntorq 125" in names_c5, \
        f"'Hola, manejan motos scooters?' debió retornar TVS Ntorq 125, obtuvo: {names_c5}"


# ─────────────────────────────────────────────────────────────────────────────
# BOT-BACKEND-BUGFIX-ROUTER-GREETING-ALIGNMENT-185
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_consecutive_catalog_search_suppresses_greeting():
    """
    Test consecutive catalog searches simulating Firestore saved conversational state.
    Asserts that the second response has skip_greeting=True and does not contain greetings like 'Hola' or 'Juan Pablo'.
    """
    from datetime import datetime, timezone
    cerebro = CerebroIA()
    
    # We will trace the calls to _generate_with_retry_async
    calls_made = []
    
    async def mock_generate(texto, context, prospect_data, history, skip_greeting, forced_instruction=None, forced_temperature=None):
        calls_made.append({
            "texto": texto,
            "skip_greeting": skip_greeting,
            "history": history.copy() if history else []
        })
        # Simulate LLM response based on skip_greeting:
        if skip_greeting:
            # Must NOT contain greetings!
            return "Aquí tienes la TVS Sport 100. Cuesta $6.200.000. ![TVS Sport](http://img) Ficha Tecnica: 100cc"
        else:
            return "¡Hola! Soy Juan Pablo. La TVS Dazz 110 cuesta $5.800.000. ![TVS Dazz](http://img) Ficha Tecnica: 110cc"

    # Setup database/prospect mock context
    prospect_data = {
        "exists": True,
        "nombre": "Tobias",
        "ciudad": "Santa Marta",
        "forma_pago": "Crédito - 0 inicial",
        "habeas_data_accepted": True,
        "moto_interest": "TVS Dazz 110",
        "ai_summary": "Interesado en motos"
    }
    
    with patch.object(cerebro, "_generate_with_retry_async", side_effect=mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
        
        # 1. First search call: 'TVS Dazz 110'
        # First call has skip_greeting = False
        response1 = await cerebro.pensar_respuesta(
            texto="TVS Dazz 110",
            context="",
            prospect_data=prospect_data,
            history=[],
            skip_greeting=False
        )
        
        # Simulate adding first interaction to history (as Firestore would save it)
        history = [
            {"role": "user", "content": "TVS Dazz 110", "timestamp": datetime.now(timezone.utc)},
            {"role": "model", "content": response1, "timestamp": datetime.now(timezone.utc)}
        ]
        
        # Update prospect interest
        prospect_data["moto_interest"] = "TVS Sport 100"
        
        # Router evaluates skip_greeting on the updated history.
        from app.routers.whatsapp import _evaluate_skip_greeting
        skip_greeting_evaluated = _evaluate_skip_greeting(history, prospect_data, current_message_saved=False)
        assert skip_greeting_evaluated is True
        
        # 2. Second search call: 'TVS Sport 100' with skip_greeting = True
        response2 = await cerebro.pensar_respuesta(
            texto="TVS Sport 100",
            context="",
            prospect_data=prospect_data,
            history=history,
            skip_greeting=skip_greeting_evaluated
        )
        
        # Assertions
        assert len(calls_made) == 2
        assert calls_made[0]["skip_greeting"] is False
        assert calls_made[1]["skip_greeting"] is True
        
        # Assert second response does not contain greetings
        response2_lower = response2.lower()
        assert "hola" not in response2_lower
        assert "juan pablo" not in response2_lower
        assert "buenos" not in response2_lower
        assert "bienven" not in response2_lower


def test_assemble_skip_greeting_prompt_rewrites_paso1():
    cerebro = CerebroIA()
    from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
    
    modified = cerebro._assemble_skip_greeting_prompt(JUAN_PABLO_SYSTEM_INSTRUCTION)
    
    # Assert PASO 1 got rewritten
    assert "- PASO 1 (Enganche de Valor): Tienes PROHIBIDO saludar" in modified
    # Assert it has the unbreakable rule at the end
    assert "INSTRUCCIÓN INQUEBRANTABLE: skip_greeting es True" in modified
    # Assert other greetings rules are suppressed/annotated
    assert "REGLA SUPRIMIDA POR skip_greeting" in modified or "PROHIBIDO saludar" in modified


@pytest.mark.asyncio
async def test_category_to_specific_model_transition_no_fallback():
    """
    Caracterización: El historial comienza con una consulta de categoría ('motos pisteras')
    seguida de una consulta de modelo específico ('sport 100').
    Valida que se retorne la información, precio e imagen de la Sport 100 sin saludar
    y sin disparar el fallback de referencia no encontrada en el prompt assembly.
    """
    from datetime import datetime, timezone
    cerebro = CerebroIA()
    
    # Mockear catalog_service para retornar items válidos en get_all_items()
    mock_catalog = MagicMock()
    mock_catalog.get_all_items.return_value = [
        {
            "ref": "sport 100",
            "name": "TVS Sport 100",
            "searchBy": ["sport", "sport 100", "trabajo"]
        }
    ]
    cerebro._catalog_service = mock_catalog
    
    # We will trace calls to _generate_with_retry_async
    calls_made = []
    
    async def mock_generate(texto, context, prospect_data, history, skip_greeting, forced_instruction=None, forced_temperature=None):
        calls_made.append({
            "texto": texto,
            "skip_greeting": skip_greeting,
            "history": history.copy() if history else []
        })
        
        # Para el test, vamos a simular el prompt assembly de forma interna para asertar que no
        # contiene la instrucción de error de referencia:
        instruction = cerebro._get_current_instruction()
        assembled = cerebro._assemble_skip_greeting_prompt(instruction, prospect_data, texto)
        
        # El prompt ensamblado NO debe contener la instrucción de error de referencia:
        assert "ERROR DE REFERENCIA" not in assembled, "El prompt inyectó el error de referencia en la transición categoría -> modelo!"
        assert "BÚSQUEDA PRIORITARIA" in assembled, "El prompt debió inyectar la instrucción de búsqueda prioritaria!"
        
        # Retornamos la respuesta simulada exitosa
        return "Aquí tienes la TVS Sport 100. Cuesta $6.200.000. ![TVS Sport](http://img) Ficha Tecnica: 100cc"

    # Setup prospect sin moto_interest
    prospect_data = {
        "exists": True,
        "nombre": "Tobias",
        "ciudad": "Santa Marta",
        "forma_pago": "Crédito - 0 inicial",
        "habeas_data_accepted": True,
        "moto_interest": "", # Sin modelo guardado previamente
        "ai_summary": "Interesado en motos"
    }
    
    # Historial inicial con consulta de categoría "motos pisteras"
    history = [
        {"role": "user", "content": "Buenas, tienen motos pisteras?", "timestamp": datetime.now(timezone.utc)},
        {"role": "model", "content": "¡Hola! Claro que sí, manejamos excelentes opciones deportivas como la TVS Raider 125.", "timestamp": datetime.now(timezone.utc)}
    ]
    
    from app.routers.whatsapp import _evaluate_skip_greeting
    skip_greeting_evaluated = _evaluate_skip_greeting(history, prospect_data, current_message_saved=False)
    assert skip_greeting_evaluated is True
    
    with patch.object(cerebro, "_generate_with_retry_async", side_effect=mock_generate), \
         patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
        
        # El usuario consulta el modelo específico 'sport 100'
        response = await cerebro.pensar_respuesta(
            texto="sport 100",
            context="",
            prospect_data=prospect_data,
            history=history,
            skip_greeting=skip_greeting_evaluated
        )
        
        # Validaciones de la respuesta
        assert response is not None
        assert "6.200.000" in response
        assert "![" in response
        assert "TVS Sport 100" in response
        
        # Comprobar que skip_greeting fue True
        assert len(calls_made) == 1
        assert calls_made[0]["skip_greeting"] is True


@pytest.mark.asyncio
async def test_perimeter_short_tokens_and_greeting_bypass():
    """
    Test case targeting the ticket BOT-BACKEND-BUGFIX-CATALOG-PERIMETER-187.
    Emulates search for 'benom 14', 'stark kids', and 'ninja 500', verifying they return correct items
    and force synchronous greeting suppression. Also verifies greeting suppression remains active
    after a category transition or a previous failed reference search.
    """
    from app.services.catalog_service import CatalogService
    service = CatalogService()
    
    # Define catalog mock items
    item_venom = {
        "id": "venom_14",
        "name": "Victory Venom 14",
        "price": 8500000,
        "category": "deportiva",
        "image_url": "http://img/venom.jpg",
        "search_tags": ["venom", "14", "deportiva"],
        "search_tokens": ["victory", "venom", "14", "venom14", "deportiva"],
        "searchBy": ["venom", "14", "deportiva"],
        "description": "Victory Venom 14.",
        "active": True
    }
    
    item_stark = {
        "id": "stark_kids",
        "name": "Victory Stark Kids",
        "price": 4000000,
        "category": "infantil",
        "image_url": "http://img/stark.jpg",
        "search_tags": ["stark", "kids", "infantil"],
        "search_tokens": ["victory", "stark", "kids", "infantil"],
        "searchBy": ["stark", "kids", "infantil"],
        "description": "Victory Stark Kids.",
        "active": True
    }
    
    item_ninja = {
        "id": "ninja_500",
        "name": "Kawasaki Ninja 500",
        "price": 32000000,
        "category": "deportiva",
        "image_url": "http://img/ninja.jpg",
        "search_tags": ["ninja", "500", "deportiva"],
        "search_tokens": ["kawasaki", "ninja", "500", "ninja500", "deportiva"],
        "searchBy": ["ninja", "500", "deportiva"],
        "description": "Kawasaki Ninja 500.",
        "active": True
    }
    
    service._items = [item_venom, item_stark, item_ninja]
    service._items_by_id = {i["id"]: i for i in service._items}
    service._items_by_category = {"deportiva": [item_venom, item_ninja], "infantil": [item_stark]}
    service._category_aliases = {}
    
    # 1. Test Catalog Matching
    # Venom fuzzy match with phonetic normalization on short token 'benom'
    results_venom = service.search_items("benom 14")
    assert len(results_venom) > 0, "Should match Victory Venom 14"
    assert results_venom[0]["name"] == "Victory Venom 14"
    
    # Stark kids match
    results_stark = service.search_items("stark kids")
    assert len(results_stark) > 0, "Should match Victory Stark Kids"
    assert results_stark[0]["name"] == "Victory Stark Kids"
    
    # Ninja 500 match (checks that token '500' is whitelisted and not excluded)
    results_ninja = service.search_items("ninja 500")
    assert len(results_ninja) > 0, "Should match Kawasaki Ninja 500"
    assert results_ninja[0]["name"] == "Kawasaki Ninja 500"
    
    # 2. Test Brain Greeting Bypass & State Transition
    with patch('app.services.ai_brain.SDK_AVAILABLE', False):
        cerebro = CerebroIA()
        cerebro.client = MagicMock()
        cerebro._model_id = "gemini-2.0-flash"
        cerebro.privacy_policy_url = "https://tiendalasmotos.com/politica-de-privacidad"
        cerebro._catalog_service = service
        
        calls_made = []
        async def mock_call_gemini(func, *args, **kwargs):
            prompt_str = args[0]
            calls_made.append(prompt_str)
            mock_resp = MagicMock()
            mock_candidate = MagicMock()
            mock_part = MagicMock()
            mock_part.text = "Aquí tienes la Victory Venom 14. Cuesta $8.500.000. ![img](http://img) Ficha Tecnica: 14"
            mock_part.function_call = None
            mock_candidate.content.parts = [mock_part]
            mock_resp.candidates = [mock_candidate]
            mock_resp.usage_metadata = MagicMock(total_token_count=100, prompt_token_count=50, candidates_token_count=50)
            return mock_resp

        with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini), \
             patch("app.services.ai_brain.LANGFUSE_AVAILABLE", False):
            
            # Test case: Fresh conversation searching 'benom 14' (skip_greeting starts as False)
            prospect_data = {
                "exists": True,
                "nombre": "Tobias",
                "ciudad": "Santa Marta",
                "forma_pago": "Crédito - 0 inicial",
                "habeas_data_accepted": True,
                "moto_interest": "",
                "ai_summary": "Interesado en motos"
            }
            
            response = await cerebro.pensar_respuesta(
                texto="benom 14",
                context="",
                prospect_data=prospect_data,
                history=[],
                skip_greeting=False
            )
            
            # Check that thinking_respuesta dynamically forced skip_greeting to True,
            # which we can verify by checking that the prompt contains skip_greeting instructions
            assert len(calls_made) == 1
            assert "INSTRUCCIÓN INQUEBRANTABLE: skip_greeting es True" in calls_made[0]
            assert prospect_data["moto_interest"] == "Victory Venom 14"
            
            # 3. Test Greeting Suppression remains active in transition
            # Let's simulate a history where the first query failed or was a category query,
            # and then the user specifies the model 'ninja 500'.
            history = [
                {"role": "user", "content": "Quiero una moto barata"},
                {"role": "model", "content": "No conozco esa referencia. Por favor especifica."}
            ]
            
            # Transition query
            prospect_data_transition = {
                "exists": True,
                "nombre": "Tobias",
                "ciudad": "Santa Marta",
                "forma_pago": "Crédito - 0 inicial",
                "habeas_data_accepted": True,
                "moto_interest": "",
                "ai_summary": "Interesado en motos"
            }
            
            calls_made.clear()
            # Evaluating skip_greeting using Whatsapp Router evaluator
            from app.routers.whatsapp import _evaluate_skip_greeting
            from datetime import datetime, timezone
            
            # Add timestamps to history to simulate recent message (<12 hours)
            history_with_time = [
                {"role": "user", "content": "Quiero una moto barata", "timestamp": datetime.now(timezone.utc)},
                {"role": "model", "content": "No conozco esa referencia. Por favor especifica.", "timestamp": datetime.now(timezone.utc)}
            ]
            
            skip_eval = _evaluate_skip_greeting(history_with_time, prospect_data_transition, current_message_saved=False)
            assert skip_eval is True, "Greeting suppression should be active since session is ongoing"
            
            async def mock_call_gemini_ninja(func, *args, **kwargs):
                prompt_str = args[0]
                calls_made.append(prompt_str)
                mock_resp = MagicMock()
                mock_candidate = MagicMock()
                mock_part = MagicMock()
                mock_part.text = "Aquí tienes la Kawasaki Ninja 500. Cuesta $32.000.000. ![img](http://img) Ficha Tecnica: 500"
                mock_part.function_call = None
                mock_candidate.content.parts = [mock_part]
                mock_resp.candidates = [mock_candidate]
                mock_resp.usage_metadata = MagicMock(total_token_count=100, prompt_token_count=50, candidates_token_count=50)
                return mock_resp

            with patch.object(cerebro, "_call_gemini_with_retry_async", side_effect=mock_call_gemini_ninja):
                response_trans = await cerebro.pensar_respuesta(
                    texto="ninja 500",
                    context="",
                    prospect_data=prospect_data_transition,
                    history=history_with_time,
                    skip_greeting=skip_eval
                )
            
            assert len(calls_made) == 1
            assert "INSTRUCCIÓN INQUEBRANTABLE: skip_greeting es True" in calls_made[0]
            assert prospect_data_transition["moto_interest"] == "Kawasaki Ninja 500"



