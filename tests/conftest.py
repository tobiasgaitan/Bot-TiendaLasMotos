import pytest
from unittest.mock import MagicMock, patch
import sys
import os

pytest_plugins = ["tests.conftest_chaos"]

# Asegurar que el path del proyecto esté disponible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture(scope="session")
def _canonical_sys_modules():
    """[H-ARNÉS-4 / F2-sesión] Snapshot canónico de sys.modules al inicio de la
    sesión (post-colección: el grafo de imports de colección ES la referencia
    de identidad de clases/módulos para toda la sesión).

    Se captura UNA sola vez (scope session) y se expone al fixture function-scope
    `isolate_module_identity`. Prohibido re-capturar por test (C2).
    """
    return dict(sys.modules)


@pytest.fixture(autouse=True)
def isolate_module_identity(_canonical_sys_modules):
    """[H-ARNÉS-4 / F2] Neutraliza estructuralmente los barridos de sys.modules
    (H-ARNÉS-2: test_config_startup, test_brilla_gases_real_firestore_cuotas,
    test_startup_lock) sin tocar sus cuerpos.

    Teardown por test: para cada entrada canónica cuyo objeto actual `is not`
    el canónico (expulsada o sustituida por re-import), se reasigna
    sys.modules[key] = canonical → la identidad de clases, settings,
    unittest.mock y google.cloud vuelve a la referencia de sesión.
    Las expulsiones intra-test del test barredor NO se interfieren (sus
    aserciones ya corrieron). ZSF: dict-ops directas, sin try/except.
    Definido PRIMERO entre los fixtures function-scope: su teardown corre
    ÚLTIMO (LIFO), de modo que los imports de los demás teardowns ya ven los
    módulos canónicos.
    """
    yield
    for key, module in _canonical_sys_modules.items():
        if sys.modules.get(key) is not module:
            sys.modules[key] = module
    # Segunda pasada (re-anclaje de paquetes padre): `import a.b as c` resuelve
    # `c` vía ATRIBUTO del paquete padre, no vía sys.modules (verificado: tras
    # `del sys.modules['app.main']` + re-import, el atributo `app.main` queda
    # ligado al módulo nuevo aunque sys.modules se restaure). Sin este re-anclaje,
    # los patches por nombre de módulo (patch.object(main_module, ...)) caerían
    # sobre el módulo re-importado y el código bajo prueba ejecutaría las
    # referencias reales. ZSF: setattr directo, sin try/except.
    for key, module in _canonical_sys_modules.items():
        if "." in key:
            parent_name, _, attr = key.rpartition(".")
            parent = sys.modules.get(parent_name)
            if parent is not None and getattr(parent, attr, None) is not sys.modules.get(key):
                setattr(parent, attr, sys.modules[key])


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mocks de variables de entorno para evitar fallos de configuración.
    
    WHY (BOT-INFRA-RECOVERY-PARAM-197): El fixture original no inyectaba las 4 credenciales
    críticas validadas por Settings()._validate_config(). Esto creaba un falso positivo: los
    tests pasaban en CI/CD porque la suite importaba 'settings' como singleton ya inicializado
    desde el .env local, nunca verificando el RuntimeError de arranque con vars ausentes.
    """
    with patch.dict(os.environ, {
        "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/fake-key.json",
        # [Incidente H-A · HA-2] Las variables de modo de pruebas y el mínimo de
        # catálogo forzado a 0 fueron erradicados del arnés global: el guard es
        # estricto y los tests lo satisfacen vía fixtures dinámicos
        # (dynamic_catalog / catalog_guard_ready).
        # Credenciales críticas — requeridas por Settings()._validate_config()
        # Valores de prueba seguros, nunca tokens reales de producción.
        "WHATSAPP_TOKEN": "TEST_WHATSAPP_TOKEN_PLACEHOLDER_197",
        "PHONE_NUMBER_ID": "1234567890",
        "ADMIN_API_KEY": "test_admin_key_not_a_real_secret_197",
        "WEBHOOK_VERIFY_TOKEN": "test_verify_token_197",
        "WHATSAPP_APP_SECRET": "test_app_secret_197",
    }):
        yield


@pytest.fixture(autouse=True)
def purge_config_loader_singletons():
    """[M4-ARNÉS-AISLAMIENTO-001] Purga los singletons ConfigLoader/FinanceConfigLoader
    entre tests (setup + teardown).

    WHY: tests/test_pcc_ficha_tecnica.py instancia ConfigLoader(db_real) contra
    Firestore de producción en 6 tests, dejando _instance/_initialized ligados a
    credenciales y configuración reales; todo test posterior recibe __init__ no-op
    y datos fugados (corrupción del arnés en tests de concurrencia).
    Patrón promovido a global desde test_refresh_atomicity.py (_reset_singletons).
    Alcance mínimo (YAGNI): NO purga config_service/catalog_service (tienen
    protocolo propio de restore vía factories).
    ZSF: asignaciones directas, sin try/except — fail-fast ruidoso.
    """
    from app.core.config_loader import ConfigLoader
    from app.services.config_loader import FinanceConfigLoader

    ConfigLoader._instance = None
    ConfigLoader._initialized = False
    FinanceConfigLoader._instance = None
    FinanceConfigLoader._initialized = False
    yield
    ConfigLoader._instance = None
    ConfigLoader._initialized = False
    FinanceConfigLoader._instance = None
    FinanceConfigLoader._initialized = False


@pytest.fixture(autouse=True)
def isolate_app_state():
    """[H-ARNÉS-4 / F3] Aislamiento de app.state (FastAPI/Starlette).

    Productores neutralizados: test_health_check (delattr manual sobre la app
    real), test_startup_lock (lifespan real que muta catalog_ready/startup_task).
    Setup: snapshot del dict interno `_state`. Teardown: clear + update.
    Coexiste con real_lifespan_client/catalog_guard_ready (doble restauración
    convergente al snapshot). ZSF: dict-ops directas, sin try/except.
    """
    from app.main import app
    saved = dict(app.state._state)
    yield
    app.state._state.clear()
    app.state._state.update(saved)


@pytest.fixture(autouse=True)
def isolate_config_service():
    """[H-ARNÉS-4 / F4] Aislamiento del singleton config_service.

    Productor neutralizado: los 6 tests de integración real de
    test_pcc_ficha_tecnica.py (initialize con db de producción). La mutación es
    por asignación pura (initialize, L42-105) → snapshot shallow estructuralmente
    correcto. Setup: copia de __dict__. Teardown: clear + update.
    ZSF: dict-ops directas, sin try/except.
    """
    from app.services.config_service import config_service
    saved = dict(config_service.__dict__)
    yield
    config_service.__dict__.clear()
    config_service.__dict__.update(saved)


@pytest.fixture(autouse=True)
def isolate_catalog_service():
    """[H-ARNÉS-4 / F5] Aislamiento del singleton catalog_service.

    Productores neutralizados: carga de catálogo real desde los tests pcc
    (initialize + load) y asignaciones directas de _items (agentic). El swap de
    índices es por asignación (L473-477) → snapshot shallow correcto. La caché
    semántica (_cache_service) se vacía en setup Y teardown (contenido mutable
    in-place: canónica = vacía). Coexiste con dynamic_catalog (token restore
    propio; LIFO deja el estado final = snapshot pre-test).
    ZSF: dict-ops directas, sin try/except.
    """
    from app.services.catalog_service import catalog_service
    saved = dict(catalog_service.__dict__)
    catalog_service._cache_service.clear()
    yield
    catalog_service.__dict__.clear()
    catalog_service.__dict__.update(saved)
    catalog_service._cache_service.clear()


@pytest.fixture(autouse=True)
def isolate_router_globals():
    """[H-ARNÉS-4 / F6] Aislamiento de los globales mutables de app.routers.whatsapp
    (superficie Cerebro/LLM + latencia).

    Productores neutralizados: rebinding vía _ensure_services_sync(), mutación
    de debounce_seconds (agentic, try/finally manual), residuo de idempotencia
    BOT-INFRA-171 (_processed_wamids/_added_wamids) y locks ligados a event
    loops muertos (_locks por phone con loops function-scope).

    Setup: snapshot de refs (db, message_buffer) + reset canónico del buffer
    vivo: debounce_seconds = 4.0 (default real del constructor, verificado C3,
    message_buffer.py L32) y .clear() in-place de _buffers, _active_tasks,
    _locks, _processed_wamids, _added_wamids (in-place preserva la identidad del
    objeto). Teardown: idem reset sobre el buffer vigente + restore de refs.
    Rama explícita documentada: message_buffer is None → no-op (ausencia de
    estado ≠ fallo de restauración). ZSF: operaciones directas, sin try/except.
    """
    from app.routers import whatsapp as whatsapp_module
    saved_db = whatsapp_module.db
    saved_buffer = whatsapp_module.message_buffer
    if saved_buffer is not None:
        saved_buffer.debounce_seconds = 4.0
        saved_buffer._buffers.clear()
        saved_buffer._active_tasks.clear()
        saved_buffer._locks.clear()
        saved_buffer._processed_wamids.clear()
        saved_buffer._added_wamids.clear()
    yield
    current_buffer = whatsapp_module.message_buffer
    if current_buffer is not None:
        current_buffer.debounce_seconds = 4.0
        current_buffer._buffers.clear()
        current_buffer._active_tasks.clear()
        current_buffer._locks.clear()
        current_buffer._processed_wamids.clear()
        current_buffer._added_wamids.clear()
    whatsapp_module.db = saved_db
    whatsapp_module.message_buffer = saved_buffer


@pytest.fixture
def mock_prospect_data():
    """Fixture de datos de prospecto para pruebas de anclaje CRM."""
    return {
        "exists": True,
        "nombre": "Juan Perez",
        "moto_interest": "TVS APACHE 160",
        "ciudad": "Bogotá",
        "forma_pago": "Crédito"
    }

@pytest.fixture
def cerebro_mock():
    """Instancia de CerebroIA con el SDK desactivado para tests lógicos."""
    # Forzamos SDK_AVAILABLE = False importando y parcheando antes de instanciar
    with patch('app.services.ai_brain.SDK_AVAILABLE', False):
        from app.services.ai_brain import CerebroIA
        cerebro = CerebroIA()
        # Inyectar atributos que normalmente se setean solo si SDK_AVAILABLE es True
        cerebro.client = MagicMock()
        cerebro._model_id = "gemini-2.0-flash" 
        cerebro.privacy_policy_url = "https://tiendalasmotos.com/politica-de-privacidad"
        return cerebro

@pytest.fixture
def dynamic_catalog():
    """Catálogo dinámico de 60 ítems (tests/factories.py) inyectado en el singleton real.

    WHY (Incidente H-A · HA-3): sustituye los mocks ad-hoc `[MagicMock()] * N` y los
    literales de precio del arnés. Determinista (seed fija) y restaurado en teardown.
    """
    from tests.factories import install_dynamic_catalog, restore_catalog
    items, token = install_dynamic_catalog(60)
    yield items
    restore_catalog(token)


@pytest.fixture
def catalog_guard_ready(dynamic_catalog, monkeypatch):
    """Satisface el STARTUP-GUARD estricto para tests que ejercitan webhook/task-processor
    vía TestClient: catálogo dinámico instalado (60 ítems) + app.state.catalog_ready=True
    + settings.min_catalog_items=60. Restaura app.state en teardown.

    WHY (Incidente H-A · HA-2): tras la erradicación del bypass de modo de pruebas
    (04-03a), el guard es incondicional — este fixture es la forma aprobada de satisfacerlo.
    """
    from app.main import app
    from app.routers import whatsapp as whatsapp_router

    had_flag = hasattr(app.state, "catalog_ready")
    previous_flag = getattr(app.state, "catalog_ready", None)
    app.state.catalog_ready = True
    monkeypatch.setattr(whatsapp_router.settings, "min_catalog_items", 60)
    yield dynamic_catalog
    if had_flag:
        app.state.catalog_ready = previous_flag
    else:
        delattr(app.state, "catalog_ready")

@pytest.fixture
def real_lifespan_client(dynamic_catalog, monkeypatch):
    """[Incidente H-A · HA-2] TestClient sobre el LIFESPAN REAL de producción.

    WHY: erradicada la rama inline de modo de pruebas (04-03a), todo cliente de pruebas
    debe atravesar el mismo camino que Cloud Run — lifespan real → background deferred
    init → commit barrier (`app.state.catalog_ready=True`). El I/O externo (Firestore,
    Secret Manager, Storage, MemoryService) se mockea en la frontera (LazyProxies de
    app.main); el catálogo se inyecta DINÁMICAMENTE (60 ítems de tests/factories.py)
    y el umbral se fija al valor de producción (`min_catalog_items=60`), de modo que el
    STARTUP-GUARD del router se ejecuta exactamente como en producción.

    El deferred init real incluye un `asyncio.sleep(2)` deliberado (BOT-190) — coste
    aceptado ~2s por instanciación a cambio de fidelidad total.

    Yield: (client, items) — TestClient dentro de contexto de lifespan COMPLETADO.
    Falla explícitamente (TimeoutError) si el commit barrier no se alcanza en 15s:
    zero-silent-failures — jamás devolver un cliente en estado zombi.
    """
    import time
    import app.main as main_module
    from app.main import app
    from app.core.config import settings as app_settings
    from fastapi.testclient import TestClient

    # Umbral de producción: el guard valida 60 >= 60 contra el catálogo dinámico.
    monkeypatch.setattr(app_settings, "min_catalog_items", 60)

    mock_config_loader_inst = MagicMock()
    mock_config_loader_inst.get_juan_pablo_personality.return_value = {"model_version": "gemini-2.0-flash"}
    mock_config_loader_inst.get_routing_rules.return_value = {"financial_keywords": []}
    mock_config_loader_inst.get_catalog_config.return_value = {"items": []}

    state_snapshot = {}
    with patch.object(main_module, "get_firebase_credentials_object", return_value=MagicMock()), \
         patch.object(main_module, "firestore") as _mock_firestore, \
         patch.object(main_module, "config_service") as _mock_config_service, \
         patch.object(main_module, "ConfigLoader", return_value=mock_config_loader_inst), \
         patch.object(main_module, "FinanceConfigLoader", return_value=MagicMock()), \
         patch.object(main_module, "storage_service") as _mock_storage, \
         patch.object(main_module, "init_memory_service", MagicMock()), \
         patch.object(main_module, "catalog_service") as mock_main_catalog:

        # El init diferido de main consume el proxy mockeado (no-op); el router
        # sigue viendo el singleton REAL con los 60 ítems dinámicos instalados.
        mock_main_catalog.get_all_items.return_value = dynamic_catalog

        # Snapshot de app.state para restauración higiénica en teardown.
        for attr in ("catalog_ready", "config_loader", "db", "db_async", "finance_config_loader", "startup_task"):
            if hasattr(app.state, attr):
                state_snapshot[attr] = getattr(app.state, attr)

        with TestClient(app) as client:
            deadline = time.monotonic() + 15.0
            while not getattr(app.state, "catalog_ready", False):
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        "real_lifespan_client: el deferred init no completó en 15s "
                        "(catalog_ready=False) — estado zombi, abortando."
                    )
                time.sleep(0.05)
            yield client, dynamic_catalog

    # Teardown: restaurar app.state al snapshot previo (aislamiento entre tests).
    for attr in ("catalog_ready", "config_loader", "db", "db_async", "finance_config_loader", "startup_task"):
        if attr in state_snapshot:
            setattr(app.state, attr, state_snapshot[attr])
        elif hasattr(app.state, attr):
            delattr(app.state, attr)

class AsyncStreamMock:
    """
    Mock estandarizado para simular firestore.Query.stream().
    Implementa el protocolo de iteración asíncrona (__aiter__ y __anext__).
    """
    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item

def test_config_service_routing_dynamic_partners():
    """
    [BOT-ARQ-FS-066] Certifica que ConfigService.load_configurations hidrata
    _partners_config iterando sobre financial_config/general/financieras, 
    y que get_partners_config() no retorna None ni un diccionario vacío.
    """
    from app.services.config_service import ConfigService
    
    class MockDoc:
        def __init__(self, id, data):
            self.id = id
            self._data = data
        def to_dict(self):
            return self._data
            
    mock_docs = [
        MockDoc("banco_bogota", {"link_url": "https://bogota.com"}),
        MockDoc("brilla", {"link": "https://brilla.com"}),
        MockDoc("fintech_partner", {"url": "https://fintech-partner.com"})
    ]
    
    mock_db = MagicMock()
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value.exists = True
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value.get.return_value.to_dict.return_value = {"tasa_nmv_banco": 1.5}
    mock_db.collection.return_value.document.return_value.collection.return_value.stream.return_value = mock_docs
    
    service = ConfigService()
    service.initialize(mock_db)
    
    partners = service.get_partners_config()
    
    assert partners is not None, "get_partners_config() retornó None"
    assert len(partners) > 0, "get_partners_config() retornó un diccionario vacío"
    assert partners.get("link_banco_bogota") == "https://bogota.com", "Fallo mapeo link_url"
    assert partners.get("link_brilla") == "https://brilla.com", "Fallo mapeo link"
    assert partners.get("link_fintech_partner") == "https://fintech-partner.com", "Fallo mapeo url"

