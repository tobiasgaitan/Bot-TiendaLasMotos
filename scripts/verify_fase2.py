
import asyncio
import logging
import sys
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

# Add project root
sys.path.append(os.getcwd())

from app.services.scoring_service import ScoringService
from app.services.finance import MotorFinanciero

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_scoring_weights():
    logger.info("🧪 Testing Scoring Logic (Reference: V6.0 refined)")
    service = ScoringService()
    
    # Case 1: Perfect Profile
    # Contract: Indefinido (1000 * 0.35) = 350
    # Habit: Al día (1000 * 0.45) = 450
    # Income: > 2 SMLV (1000 * 0.20) = 200
    # Total: 1000
    score_perfect = service.calculate_score("Indefinido", "Al día", "> 2 SMLV")
    logger.info(f"PERFECT Profile Score: {score_perfect} (Expected: 1000)")
    assert score_perfect == 1000
    
    # Case 2: Average User
    # Contract: Obra (600 * 0.35) = 210
    # Habit: Mora < 30 (700 * 0.45) = 315
    # Income: 1-2 SMLV (800 * 0.20) = 160
    # Total: 685
    score_avg = service.calculate_score("Obra Labor", "Mora < 30", "1-2 Millones")
    logger.info(f"AVERAGE Profile Score: {score_avg} (Expected ~685)")
    assert abs(score_avg - 685) < 5
    
    # Case 3: Risk User
    # Contract: Informal (300 * 0.35) = 105
    # Habit: Reportado (0 * 0.45) = 0
    # Income: Minimo (800 * 0.20) = 160
    # Total: 265
    score_risk = service.calculate_score("Informal", "Reportado", "Minimo")
    logger.info(f"RISK Profile Score: {score_risk} (Expected ~265)")
    assert score_risk < 400

def test_finance_integration():
    logger.info("\n🧪 Testing Finance Service Integration")
    
    # Mock ConfigLoader
    mock_loader = MagicMock()
    mock_loader.get_financial_config.return_value = {"tasa_nmv_banco": 1.5, "tasa_nmv_fintech": 2.5}
    mock_loader.get_partners_config.return_value = {"link_brilla": "http://brilla.com"}
    
    motor = MotorFinanciero(db=MagicMock(), config_loader=mock_loader)
    
    # Test Evaluation - Bank
    res_bank = motor.evaluar_perfil("Indefinido", "Al día", "3 millones")
    logger.info(f"Bank Result: {res_bank['strategy']} - {res_bank['entity']}")
    assert res_bank["strategy"] == "BANCO"
    assert res_bank["requires_aval"] is False
    
    # Test Evaluation - Brilla
    res_brilla = motor.evaluar_perfil("Informal", "Reportado", "1 SMLV")
    logger.info(f"Brilla Result: {res_brilla['strategy']} - {res_brilla['entity']}")
    assert res_brilla["strategy"] == "BRILLA"
    
    # Test Link Property
    logger.info(f"Link Brilla: {motor.link_brilla}")
    assert motor.link_brilla == "http://brilla.com"

if __name__ == "__main__":
    test_scoring_weights()
    test_finance_integration()
    logger.info("\n✅ All Phase 2 Tests Passed!")
