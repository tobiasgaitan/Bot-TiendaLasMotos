import pytest
import re
from unittest.mock import patch, MagicMock
from app.services.catalog_service import catalog_service
from app.services.config_service import config_service

def test_pcc_ficha_tecnica_no_silent_null():
    """
    Verifica la presencia explícita de 'Ficha Tecnica:' y asegura que
    una mutación de llaves no resulte en valores 'None' silenciosos o
    strings vacíos, manteniendo la integridad del Price Consistency Check.
    """
    # Escenario 1: Comportamiento normal con la llave 'summary' correcta.
    mock_item_ok = {
        "id": "1",
        "name": "Moto Ghost",
        "price": 5000000,
        "cc": 125,
        "category": "Urban",
        "image_url": "http://img.url",
        "link": "http://link.url",
        "description": "Excelente moto urbana.",
        "summary": "Excelente moto urbana."
    }
    
    with patch.object(catalog_service, '_items', [mock_item_ok]), \
         patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):
        
        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()
        
        res = catalog_service.search_catalog("Ghost")
        assert "Ficha Tecnica:" in res, "La cadena transformada 'Ficha Tecnica:' DEBE estar explícita."
        
        match = re.search(r"Ficha Tecnica:\s*(.+)", res)
        assert match is not None, "El contenido después de 'Ficha Tecnica:' no puede ser nulo o vacío."
        val = match.group(1).strip()
        assert val != "", "El string de Ficha Tecnica no puede ser vacío."
        assert val != "None", "El string de Ficha Tecnica no puede ser 'None' silencioso."

    # Escenario 2: Mutación de llaves (ej: el backend cambió 'summary' a 'resumen_tecnico')
    # Omitimos 'summary' para simular la mutación/pérdida de la llave.
    mock_item_mutated = {
        "id": "1",
        "name": "Moto Ghost",
        "price": 5000000,
        "cc": 125,
        "category": "Urban",
        "image_url": "http://img.url",
        "link": "http://link.url",
        "resumen_tecnico": "Excelente moto urbana."
    }
    
    with patch.object(catalog_service, '_items', [mock_item_mutated]), \
         patch.object(catalog_service, '_db', MagicMock()), \
         patch.object(config_service, '_financial_config', None), \
         patch.object(config_service, 'get_registration_cost', return_value=0):
        
        catalog_service.load_configurations = MagicMock()
        catalog_service._cache_service.clear()
        
        res_mutated = catalog_service.search_catalog("Ghost")
        
        # Validar que si la llave mutó, no devuelva "Ficha Tecnica: " ni "Ficha Tecnica: None"
        if "Ficha Tecnica:" in res_mutated:
            match = re.search(r"Ficha Tecnica:\s*(.*)", res_mutated)
            if match:
                val = match.group(1).strip()
                assert val != "", "ALERTA: Se detectó 'Ficha Tecnica:' con string vacío debido a mutación de llaves."
                assert val != "None", "ALERTA: Se detectó 'None' silencioso en 'Ficha Tecnica:' debido a mutación."
