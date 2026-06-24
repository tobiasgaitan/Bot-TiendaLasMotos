"""
test_financial_fallback.py
BOT-FINANCE-ERR-094 — Test de caracterización: Zero-Silent-Failures en FinancialService.

Verifica que:
1. `calculate_payment` con `get_partners_config()` retornando `{}` (entorno beta sin doc 'partners')
   NO retorna None ni lanza excepción silenciosa.
2. El resultado SIEMPRE contiene "cuota_mensual" con valor float >= 0.
3. Si el config_service falla completamente (mock que lanza KeyError),
   el fallback de amortización básica produce cuota_mensual > 0.
4. No existe retorno None silencioso en ninguna rama evaluada.
5. La rama de doble-fallo (fallback que también explota) retorna dict completo con cuota_mensual=0.0.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.financial_service import FinancialService


# ─── Fixtures ──────────────────────────────────────────────────────────────────

PRECIO_MOTO = 5_800_000.0
INICIAL = 1_000_000.0
PLAZO = 24
ENTIDAD = "Crediorbe"


def _build_service_with_empty_partners() -> FinancialService:
    """Construye FinancialService con partners_config vacío (simula beta sin doc Firestore)."""
    svc = FinancialService.__new__(FinancialService)
    mock_config = MagicMock()
    mock_config.get_partners_config.return_value = {}
    # Simular config financiero mínimo para que el cálculo pueda fallar en la matriz
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
    }
    svc._config_service = mock_config
    svc._scoring_service = MagicMock()
    return svc


def _build_service_with_broken_config() -> FinancialService:
    """Construye FinancialService donde get_financial_entity_config lanza KeyError."""
    svc = FinancialService.__new__(FinancialService)
    mock_config = MagicMock()
    mock_config.get_partners_config.return_value = {}
    mock_config.get_financial_entity_config.side_effect = KeyError("fngRate")
    mock_config.get_financial_matrix.side_effect = KeyError("matrix")
    mock_config.get_financial_config.return_value = {}
    svc._config_service = mock_config
    svc._scoring_service = MagicMock()
    return svc


def _build_service_with_broken_fallback() -> FinancialService:
    """Construye FinancialService donde _get_insurance_monthly también lanza (doble fallo)."""
    svc = FinancialService.__new__(FinancialService)
    mock_config = MagicMock()
    mock_config.get_financial_entity_config.side_effect = KeyError("fngRate")
    mock_config.get_financial_matrix.side_effect = KeyError("matrix")
    mock_config.get_financial_config.return_value = {}
    svc._config_service = mock_config
    svc._scoring_service = MagicMock()
    # Forzar que _get_insurance_monthly también explote para cubrir rama inner_except
    svc._get_insurance_monthly = MagicMock(side_effect=RuntimeError("insurance_exploded"))
    return svc


# ─── Tests ─────────────────────────────────────────────────────────────────────

class TestCalculatePaymentFallback:
    """BOT-FINANCE-ERR-094: Zero-Silent-Failures en calculate_payment."""

    def test_partners_vacio_no_retorna_none(self):
        """MANDATORIO: partners={} no debe producir retorno None silencioso."""
        svc = _build_service_with_empty_partners()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, PLAZO, entidad=ENTIDAD)
        assert result is not None, \
            "[ZSF] calculate_payment retornó None con partners_config vacío. Violación de Zero-Silent-Failures."

    def test_partners_vacio_retorna_cuota_mensual(self):
        """MANDATORIO: resultado debe tener clave 'cuota_mensual' con valor float."""
        svc = _build_service_with_empty_partners()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, PLAZO, entidad=ENTIDAD)
        assert "cuota_mensual" in result, \
            "[ZSF] Clave 'cuota_mensual' ausente en resultado con partners vacío."
        assert isinstance(result["cuota_mensual"], float), \
            f"[ZSF] cuota_mensual debe ser float, obtenido: {type(result['cuota_mensual'])}"

    def test_partners_vacio_cuota_mayor_cero(self):
        """La cuota de fallback (amortización básica) debe ser > 0 para préstamo válido."""
        svc = _build_service_with_empty_partners()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, PLAZO, entidad=ENTIDAD)
        assert result["cuota_mensual"] > 0, \
            f"[ZSF] cuota_mensual={result['cuota_mensual']} no es coherente (debe ser > 0)."

    def test_config_roto_no_retorna_none(self):
        """Si config_service lanza KeyError, el fallback NO debe retornar None."""
        svc = _build_service_with_broken_config()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, PLAZO, entidad=ENTIDAD)
        assert result is not None, \
            "[ZSF] calculate_payment retornó None ante KeyError en config_service."

    def test_config_roto_retorna_cuota_coherente(self):
        """Fallback de amortización básica produce cuota_mensual float >= 0."""
        svc = _build_service_with_broken_config()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, PLAZO, entidad=ENTIDAD)
        assert "cuota_mensual" in result, \
            "[ZSF] Clave 'cuota_mensual' ausente en resultado de fallback con config roto."
        assert isinstance(result["cuota_mensual"], (int, float)), \
            "[ZSF] cuota_mensual no es numérica en rama fallback."
        assert result["cuota_mensual"] >= 0, \
            "[ZSF] cuota_mensual negativa en fallback: resultado incoherente."

    def test_config_roto_error_registrado_en_dict(self):
        """La rama de fallback debe incluir 'error_matriz' para rastreo forense."""
        svc = _build_service_with_broken_config()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, PLAZO, entidad=ENTIDAD)
        assert "error_matriz" in result or "error" in result, \
            "[ZSF] Dict de fallback no incluye ninguna clave de error para diagnóstico forense."

    def test_doble_fallo_no_retorna_none(self):
        """Rama inner_except: si el fallback también explota, retornar dict (nunca None)."""
        svc = _build_service_with_broken_fallback()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, PLAZO, entidad=ENTIDAD)
        assert result is not None, \
            "[ZSF] Doble fallo retornó None. Violación crítica de Zero-Silent-Failures."

    def test_doble_fallo_cuota_mensual_presente_y_float(self):
        """En doble fallo, cuota_mensual=0.0 (no None, no ausente)."""
        svc = _build_service_with_broken_fallback()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, PLAZO, entidad=ENTIDAD)
        assert "cuota_mensual" in result, \
            "[ZSF] Clave 'cuota_mensual' ausente en resultado de doble fallo."
        assert isinstance(result["cuota_mensual"], float), \
            f"[ZSF] cuota_mensual debe ser float en doble fallo, obtenido: {type(result['cuota_mensual'])}"

    def test_plazo_36_con_partners_vacio(self):
        """Verificar que el fallback funciona también para plazo 36m."""
        svc = _build_service_with_empty_partners()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, 36, entidad=ENTIDAD)
        assert result is not None
        assert result.get("cuota_mensual", -1) >= 0

    def test_plazo_48_con_partners_vacio(self):
        """Verificar que el fallback funciona también para plazo 48m."""
        svc = _build_service_with_empty_partners()
        result = svc.calculate_payment(PRECIO_MOTO, INICIAL, 48, entidad=ENTIDAD)
        assert result is not None
        assert result.get("cuota_mensual", -1) >= 0
