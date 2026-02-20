"""
Scoring Service (Fase 2)
Calculates financial risk score (0-1000) based on user profile.
Used to route leads to Bank, Fintech, or Alternative financing.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ScoringService:
    """
    Service to calculate credit scores and determine financing strategies.
    
    Formula (v6.0 Refined):
    Score = (Contract * 0.35) + (Habit * 0.45) + (Income * 0.20)
    """
    
    # Weights
    WEIGHT_CONTRACT = 0.35
    WEIGHT_HABIT = 0.45
    WEIGHT_INCOME = 0.20
    
    # Point Mappings (Normalized to 0-1000)
    POINTS_CONTRACT = {
        "indefinido": 1000,
        "fijo": 800,
        "obra": 600,
        "independiente": 500,
        "informal": 300,
        "desempleado": 0
    }
    
    POINTS_HABIT = {
        "al dia": 1000,
        "al día": 1000,
        "mora < 30": 700,
        "mora reciente": 700,
        "mora > 60": 300,
        "reportado": 0,
        "castigado": 0,
        "sin experiencia": 500 # Neutral start
    }
    
    POINTS_INCOME = {
        "mayor a 2 smlv": 1000,
        "> 2 smlv": 1000,
        "2 millones": 800, # Assuming 2M is roughly 1-2 SMLV contextually or specifically
        "3 millones": 1000,
        "1-2 smlv": 800,
        "1-2 millones": 800,
        "1 a 2 millones": 800,
        "1 a 2": 800,
        "minimo": 800, 
        "mínimo": 800,
        "menos del minimo": 400,
        "menos del mínimo": 400,
        "variable": 500
    }
    
    def calculate_score(self, ocupacion_y_contrato: str, historial_datacredito: str, ingresos_demostrables: str) -> int:
        """
        Calculate credit score based on user profile.
        
        Args:
            ocupacion_y_contrato: Contract type (e.g., "Indefinido")
            historial_datacredito: Payment habit details (e.g., "Al día", "Reportado")
            ingresos_demostrables: Income level (e.g., "1-2 SMLV")
            
        Returns:
            Calculated score (0-1000)
        """
        # Normalize inputs
        c_key = self._normalize_input(ocupacion_y_contrato)
        h_key = self._normalize_input(historial_datacredito)
        i_key = self._normalize_input(ingresos_demostrables)
        
        # Get points (Default to lowest safe value if unknown)
        p_contract = self._get_points(self.POINTS_CONTRACT, c_key, default=300)
        p_habit = self._get_points(self.POINTS_HABIT, h_key, default=500)
        p_income = self._get_points(self.POINTS_INCOME, i_key, default=400)
        
        # Calculate Weighted Score
        raw_score = (p_contract * self.WEIGHT_CONTRACT) + \
                    (p_habit * self.WEIGHT_HABIT) + \
                    (p_income * self.WEIGHT_INCOME)
                    
        final_score = int(round(raw_score))
        
        logger.info(f"📊 Score Config: C={p_contract} * {self.WEIGHT_CONTRACT} + H={p_habit} * {self.WEIGHT_HABIT} + I={p_income} * {self.WEIGHT_INCOME}")
        logger.info(f"✅ Final Score: {final_score}")
        
        return final_score

    def _normalize_input(self, text: str) -> str:
        """Normalize text for matching keys."""
        if not text:
            return ""
        return text.lower().strip()

    def _get_points(self, mapping: Dict[str, int], key: str, default: int) -> int:
        """Find best matching key in mapping."""
        # Exact match
        if key in mapping:
            return mapping[key]
        
        # Partial match (e.g. "tengo contrato indefinido" -> "indefinido")
        for k, v in mapping.items():
            if k in key:
                return v
                
        return default

    def determine_strategy(self, score: int, tiene_gas_natural: bool = False, historial_datacredito: str = "", mora_y_paz_salvo: str = "") -> Dict[str, Any]:
        """
        Determine financing strategy based on score.
        
        Returns dictionary with strategy details.
        """
        h_key = self._normalize_input(historial_datacredito)
        m_key = self._normalize_input(mora_y_paz_salvo)
        
        is_reported = "reportado" in h_key or "mora > 60" in h_key or "castigado" in h_key or "mora sin paz" in m_key
        has_paz_y_salvo = "paz y salvo" in m_key
        
        # Priority Logic: If user has gas receipt, is reported, and does NOT have a "paz y salvo".
        if tiene_gas_natural and is_reported and not has_paz_y_salvo:
            logger.info("⚡ Brilla priority path triggered: Gas receipt + Reported without Paz y Salvo.")
            return {
                "strategy": "BRILLA",
                "entity": "Brilla de Gases",
                "rate_key": None,
                "link_key": "link_brilla",
                "requires_aval": False,
                "is_fallback": False
            }

        if score >= 700:
            return {
                "strategy": "BANCO",
                "entity": "Banco de Bogotá",
                "rate_key": "tasa_nmv_banco",
                "link_key": "link_banco_bogota",
                "requires_aval": False
            }
        elif score >= 400:
            return {
                "strategy": "FINTECH",
                "entity": "Crediorbe",
                "rate_key": "tasa_nmv_fintech",
                "link_key": "link_crediorbe",
                "requires_aval": True
            }
        else:
            return {
                "strategy": "BRILLA",
                "entity": "Brilla de Gases",
                "rate_key": None, # Brilla has fixed rate usually or handled differently
                "link_key": "link_brilla",
                "requires_aval": False,
                "is_fallback": True
            }

# Global instance
scoring_service = ScoringService()
