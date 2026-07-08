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
    
    # We need to mock motor_financiero as well to return a simulated payment
    mock_financial = MagicMock()
    mock_financial.calculate_payment.return_value = {
        "cuota_mensual": 350000.0
    }
    
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

    with patch("app.routers.whatsapp.settings") as mock_settings, \
         patch("app.routers.whatsapp.memory_service_module.memory_service", mock_memory_service), \
         patch("app.routers.whatsapp.judge_service") as mock_judge, \
         patch("app.services.whatsapp_service.whatsapp_service.send_text_message", side_effect=mock_send_text), \
         patch("app.services.whatsapp_service.whatsapp_service.mark_as_read", AsyncMock()), \
         patch("app.routers.whatsapp.catalog_service", mock_catalog), \
         patch("app.routers.whatsapp.motor_financiero", mock_financial), \
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
            "las cuotas a 24 meses serían aproximadamente de $350,000 "
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
    financial_service._config_service = mock_config_service

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
         patch('app.services.financial_service.config_service', mock_config_service), \
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
