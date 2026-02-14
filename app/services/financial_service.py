"""
Financial Service
Core decision engine for credit scoring and routing.
Evaluates user profiles effectively to determine the best financing partner.
"""

import logging
from typing import Dict, Any, List, Optional
from app.services.config_service import config_service

logger = logging.getLogger(__name__)

class FinancialService:
    """
    Service for calculating credit scores and determining financing strategies.
    
    Implements the "Fintech Decision Engine":
    1. Advanced Scoring Matrix (0-1000 pts)
    2. Mandatory Brilla Eligibility Check ("Plan B")
    3. Smart Routing (Banco vs Fintech vs Brilla vs Human)
    """

    def __init__(self):
        """Initialize with dependency on ConfigService."""
        self._config_service = config_service

    def calculate_score(self, profile: Dict[str, Any]) -> int:
        """
        Calculate financial score based on the 5-factor matrix.
        
        Matrix Weights:
        - Labor Profile (30%): Stability
        - Credit Experience (10%): History
        - Capacity (20%): Debt Ratio
        - Payment Habits (40%): The "King" Factor
        - Wildcard (10%): Cellphone Plan
        
        Max Score: 1000
        """
        score = 0
        
        # 1. Labor Profile (30%)
        labor_type = str(profile.get("labor_type", "")).lower()
        if "informal" in labor_type or "diario" in labor_type:
            score += 50
        elif any(x in labor_type for x in ["indefinido", "formal", "propio", "pensionado", "camara"]):
            score += 300
        elif any(x in labor_type for x in ["fijo", "obra"]):
            score += 150
        else: # Default low
            score += 50
            
        # 2. Credit Experience (10%)
        credit_history = str(profile.get("credit_history", "")).lower()
        if "actual" in credit_history or "vigente" in credit_history:
            score += 100
        elif "cerrado" in credit_history or "antiguo" in credit_history:
            score += 70
        else: # None / Never had credit
            score += 50
            
        # 3. Capacity (20%)
        # Logic: debt_ratio < 0.3 -> 200, > 0.3 -> 100, else 0
        try:
            capacity_status = str(profile.get("capacity_status", "")).lower()
            if "menos" in capacity_status or "sobra" in capacity_status:
                score += 200
            elif "mas" in capacity_status or "ajustado" in capacity_status:
                score += 100
            else: # No capacity logic derived from inputs
                 # Fallback if boolean/numeric passed
                 debt_ratio = float(profile.get("debt_ratio", 1.0))
                 if debt_ratio < 0.3:
                     score += 200
                 elif debt_ratio < 0.7:
                     score += 100
                 else:
                     score += 0
        except:
            score += 0

        # 4. Payment Habits (40%) - The "King" Factor
        payment_habit = str(profile.get("payment_habit", "")).lower()
        if "aldia" in payment_habit.replace(" ", "") or "al día" in payment_habit or "excelente" in payment_habit:
            score += 400
        elif "paz y salvo" in payment_habit or "recuperado" in payment_habit or "mora < 30" in payment_habit:
            score += 200
        else: # Reported, Default, Castigado
            score += 0

        # 5. Wildcard (10%) - Cellphone
        phone_plan = str(profile.get("phone_plan", "")).lower()
        if "postpago" in phone_plan and ("antiguo" in phone_plan or "> 1" in phone_plan or "año" in phone_plan):
            score += 100
        elif "postpago" in phone_plan: # New
            score += 50
        else: # Prepago
            score += 0

        return min(score, 1000)

    def determine_strategy(self, score: int, brilla_eligible: bool) -> Dict[str, Any]:
        """
        Determine the routing strategy based on score and backup flags.
        
        Routing:
        - > 700: BANCO (Redirect)
        - 400 - 699: FINTECH (Redirect)
        - < 400 AND Brilla: BRILLA (Capture)
        - < 400 No Brilla: HUMAN (Handoff)
        """
        # Get config
        partners = self._config_service.get_partners_config()
        
        # Link payloads
        link_banco = partners.get("link_banco_bogota", "https://digital.bancodebogota.com/")
        link_crediorbe = partners.get("link_crediorbe", "https://crediorbe.com/")
        link_asesor = partners.get("link_asesor", "https://wa.me/573000000000") 
        
        # Default Output
        decision = {
            "score": score,
            "strategy": "",
            "action_type": "",
            "payload": None,
            "backup_flags": {
                "brilla_viable": brilla_eligible
            }
        }
        
        if score >= 700:
            decision["strategy"] = "BANCO"
            decision["action_type"] = "REDIRECT"
            decision["payload"] = link_banco
            
        elif score >= 400:
            decision["strategy"] = "FINTECH"
            decision["action_type"] = "REDIRECT"
            decision["payload"] = link_crediorbe
            
        else:
            # Low Score Logic
            if brilla_eligible:
                decision["strategy"] = "BRILLA"
                decision["action_type"] = "CAPTURE_DATA"
                decision["payload"] = ["recibo_gas", "foto_cedula"] # List of docs to capture
            else:
                decision["strategy"] = "HUMAN"
                decision["action_type"] = "HANDOFF"
                decision["payload"] = link_asesor
                
        return decision

    def evaluate_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point to evaluate a user profile.
        
        Args:
            profile: Dict containing:
                - labor_type
                - credit_history
                - capacity_status (or debt_ratio)
                - payment_habit
                - phone_plan
                - has_gas_natural (bool)
                
        Returns:
            Decision object.
        """
        # 1. Calculate Score
        score = self.calculate_score(profile)
        logger.info(f"📊 Calculated Score: {score} for profile")

        # 2. Plan B Check
        # Ensure boolean
        has_gas = profile.get("has_gas_natural", False)
        if isinstance(has_gas, str):
            has_gas = has_gas.lower() in ["si", "true", "yes", "s"]
            
        # 3. Determine Strategy
        decision = self.determine_strategy(score, has_gas)
        
        logger.info(f"🏁 Decision Strategy: {decision['strategy']} ({decision['action_type']})")
        
        return decision

# Global instance
financial_service = FinancialService()
