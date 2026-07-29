import pytest
from unittest.mock import MagicMock, patch
from app.services.catalog_service import CatalogService
from app.core.config_loader import ConfigLoader
from app.services.config_service import config_service

# Initialize the ConfigLoader singleton with a mock DB to prevent ValueError on first call
try:
    ConfigLoader(db=MagicMock())
except Exception:
    pass

@pytest.fixture(autouse=True)
def _init_config_loader_per_test():
    """[M4-ARNÉS-AISLAMIENTO-001] Re-establece la inicialización del singleton
    POR TEST (el bloque a nivel import solo cubre el momento de colección).

    WHY: el fixture global purge_config_loader_singletons (conftest.py) purga
    ConfigLoader._instance/_initialized antes de cada test; sin este re-seed,
    ConfigLoader() no-arg en catalog_service lanzaría ValueError. Mismo estado
    que el bloque de import original (Mock db), en el punto de ciclo de vida
    correcto (por test). Cero cambios de aserciones, cero cambios de cobertura.
    Import runtime: resuelve la clase vigente (anti divergencia BOT-174).
    """
    from app.core.config_loader import ConfigLoader as _CL
    _CL(db=MagicMock())
    yield

@pytest.fixture(autouse=True)
def mock_registration_cost():
    """Guard against Global State Pollution from other tests mocking config_service."""
    with patch.object(config_service, 'get_registration_cost', return_value=0):
        yield

def test_competitor_cache_hit_warning_injection():
    """
    Asserts that the system warning prefix is prepended to semantic cache hits
    when the query matches a competitor brand.
    """
    cat_service = CatalogService()
    query = "tvs sport vs boxer"
    mock_raw_response = "Encontré motos relacionados:\n- TVS Sport (Urbana): $9.969.000\nFicha Tecnica: Excelente moto."
    
    # Pre-populate the cache with the raw response (without the warning prefix)
    cat_service._cache_service.set(query, mock_raw_response)
    
    # Mock ConfigLoader to return standard competitor brands including 'boxer'
    mock_config = {
        "competitor_brands": ["boxer", "nkd", "pulsar", "yamaha", "honda", "suzuki", "akt"]
    }
    
    with patch.object(ConfigLoader, 'get_catalog_config', return_value=mock_config):
        # Execute search
        result = cat_service.search_catalog(query)
        
        warning_prefix = "[SISTEMA: El usuario preguntó por la competencia. ESTÁS OBLIGADO a pivotar a nuestras alternativas...]\n\n"
        
        assert result.startswith(warning_prefix)
        assert mock_raw_response in result
        # Check that it didn't do double prefixing
        assert result.count(warning_prefix) == 1

def test_competitor_no_duplication_warning():
    """
    Verifies that the warning prefix is never duplicated when calling search_catalog
    sequentially on competitor brands (validating post-cache warning sanitation).
    """
    cat_service = CatalogService()
    query = "pulsar 180"
    
    mock_config = {
        "competitor_brands": ["boxer", "nkd", "pulsar", "yamaha", "honda", "suzuki", "akt"]
    }
    
    with patch.object(ConfigLoader, 'get_catalog_config', return_value=mock_config):
        # First call (Miss: fetches and caches raw result, then intercepts and prepends warning)
        res_1 = cat_service.search_catalog(query)
        
        # Second call (Hit: gets result from cache, intercepts and prepends warning)
        res_2 = cat_service.search_catalog(query)
        
        warning_prefix = "[SISTEMA: El usuario preguntó por la competencia. ESTÁS OBLIGADO a pivotar a nuestras alternativas...]\n\n"
        
        # Both must have exactly ONE warning prefix
        assert res_1.startswith(warning_prefix)
        assert res_1.count(warning_prefix) == 1
        
        assert res_2.startswith(warning_prefix)
        assert res_2.count(warning_prefix) == 1
        assert res_1 == res_2

def test_hot_mutated_competitor_brands():
    """
    Validates dynamic hot-reloading of competitor brands from ConfigLoader.
    If a new brand (e.g. 'torito' or 'motocarro bajaj') is added in ConfigLoader,
    it must trigger the warning immediately. If it's removed, it must not.
    """
    cat_service = CatalogService()
    query_torito = "quiero comprar un torito"
    
    # 1. First scenario: 'torito' is NOT in competitor brands list
    mock_config_1 = {
        "competitor_brands": ["boxer", "nkd", "pulsar"]
    }
    
    with patch.object(ConfigLoader, 'get_catalog_config', return_value=mock_config_1):
        res_1 = cat_service.search_catalog(query_torito)
        warning_prefix = "[SISTEMA: El usuario preguntó por la competencia. ESTÁS OBLIGADO a pivotar a nuestras alternativas...]\n\n"
        assert not res_1.startswith(warning_prefix)

    # Clear cache to simulate fresh search or updated cache state
    cat_service._cache_service.clear()

    # 2. Second scenario: 'torito' is added dynamically to competitor brands
    mock_config_2 = {
        "competitor_brands": ["boxer", "nkd", "pulsar", "torito", "motocarro bajaj"]
    }
    
    with patch.object(ConfigLoader, 'get_catalog_config', return_value=mock_config_2):
        res_2 = cat_service.search_catalog(query_torito)
        assert res_2.startswith(warning_prefix)
        assert res_2.count(warning_prefix) == 1

    # Clear cache again
    cat_service._cache_service.clear()

    # 3. Third scenario: 'torito' is removed from competitor brands
    with patch.object(ConfigLoader, 'get_catalog_config', return_value=mock_config_1):
        res_3 = cat_service.search_catalog(query_torito)
        assert not res_3.startswith(warning_prefix)
