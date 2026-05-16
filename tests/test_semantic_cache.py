import pytest
from app.services.semantic_cache_service import SemanticCacheService

@pytest.fixture
def cache_service():
    service = SemanticCacheService()
    return service

def test_semantic_cache_exact_hit(cache_service):
    query = "tvs sport 100"
    response = "Markdown Response para TVS Sport 100"
    
    cache_service.set(query, response)
    
    cached_res, score = cache_service.get("tvs sport 100")
    assert cached_res == response
    assert score == 1.0

def test_semantic_cache_fuzzy_hit(cache_service):
    query = "tvs sport 100"
    response = "Markdown Response para TVS Sport 100"
    
    cache_service.set(query, response)
    
    # Slight variation in spacing/case
    cached_res, score = cache_service.get("Tvs Sport   100 ")
    assert cached_res == response
    assert score >= 0.85

    # Typo variation
    cached_res_typo, score_typo = cache_service.get("tvs sport 10")
    assert cached_res_typo == response
    assert score_typo >= 0.85

def test_semantic_cache_miss(cache_service):
    query = "tvs sport 100"
    response = "Markdown Response para TVS Sport 100"
    
    cache_service.set(query, response)
    
    cached_res, score = cache_service.get("honda navi")
    assert cached_res is None
    assert score < 0.85

def test_semantic_cache_normalization(cache_service):
    text1 = "¿Cuánto cuesta la TVS Sport?"
    text2 = "cuanto cuesta la tvs sport"
    
    norm1 = cache_service._normalize_text(text1)
    norm2 = cache_service._normalize_text(text2)
    
    assert norm1.strip() == norm2.strip()

def test_catalog_service_search_interception(caplog):
    from app.services.catalog_service import CatalogService
    import logging
    
    # We create a new instance to not pollute the global one if not needed
    cat_service = CatalogService()
    query = "test interceptor query"
    mock_response = "Mocked Markdown Response"
    
    # Inject into its internal cache
    cat_service._cache_service.set(query, mock_response)
    
    caplog.set_level(logging.INFO)
    
    res = cat_service.search_catalog(query)
    
    assert res == mock_response
    assert "⚡ Semantic Cache Hit" in caplog.text
