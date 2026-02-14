"""
Verification Script for Financial Service
Tests the scoring engine and routing logic with various dummy profiles.
"""

import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from app.services.financial_service import financial_service
from typing import Dict, Any

# Mock Config Service for testing
class MockConfigService:
    def get_partners_config(self) -> Dict[str, Any]:
        return {
            "link_banco_bogota": "https://mock.banco.com",
            "link_crediorbe": "https://mock.crediorbe.com",
            "link_asesor": "https://mock.asesor.com"
        }

# Inject Mock
financial_service._config_service = MockConfigService()

def test_profile(name: str, profile: Dict[str, Any]):
    print(f"--- Testing Profile: {name} ---")
    print(f"Input: {profile}")
    decision = financial_service.evaluate_profile(profile)
    print(f"Output Score: {decision['score']}")
    print(f"Strategy: {decision['strategy']}")
    print(f"Action: {decision['action_type']}")
    print(f"Payload: {decision['payload']}")
    print(f"Backup Flags: {decision['backup_flags']}")
    print("-" * 30 + "\n")

if __name__ == "__main__":
    # Case A: Perfect Profile (Should be BANCO)
    # Labor: Indefinido (300)
    # Credit: Actual (100)
    # Capacity: Menos (200)
    # Habits: Al dia (400)
    # Wildcard: Postpago antiguo (100)
    # Total: 1100 -> 1000
    test_profile("Perfect Profile (Bank)", {
        "labor_type": "indefinido",
        "credit_history": "actual",
        "capacity_status": "menos del 30%",
        "payment_habit": "al dia",
        "phone_plan": "postpago antiguo",
        "has_gas_natural": True
    })

    # Case B: Mid Profile (Should be FINTECH)
    # Labor: Fijo (150)
    # Credit: Cerrado (70)
    # Capacity: Ajustado (100)
    # Habits: Paz y salvo (200)
    # Wildcard: Postpago nuevo (50)
    # Total: 570
    test_profile("Mid Profile (Fintech)", {
        "labor_type": "fijo",
        "credit_history": "cerrado",
        "capacity_status": "ajustado",
        "payment_habit": "paz y salvo",
        "phone_plan": "postpago nuevo",
        "has_gas_natural": False
    })

    # Case C: Low Profile with Brilla (Should be BRILLA)
    # Labor: Informal (50)
    # Credit: None (50)
    # Capacity: No info (0)
    # Habits: Clean (400) - Maybe they have clean habits but low score otherwise
    # Wildcard: Prepago (0)
    # Total: 500 -> wait, 500 is > 400, so this would be Fintech.
    
    # Let's try a truly low profile
    # Labor: Informal (50)
    # Credit: Reported (Habits=0) -> 0 logic in habits?
    # Actually if habits is "Reported", score is 0 for habits.
    # Total: 50 + 50 + 0 + 0 + 0 = 100.
    test_profile("Low Profile (Brilla Eligible)", {
        "labor_type": "informal",
        "credit_history": "reportado", # This might affect habits logic if not careful, but strict "credit_history" logic adds 50 if "none" or other. 
        # Wait, credit_history logic: "Actual" (100), "Cerrado" (70), Else (50).
        # So "reportado" falls to else (50).
        "capacity_status": "unknown",
        "payment_habit": "reportado", # 0
        "phone_plan": "prepago",
        "has_gas_natural": True
    })

    # Case D: Low Profile NO Brilla (Should be HUMAN)
    test_profile("Low Profile (No Brilla)", {
        "labor_type": "informal",
        "credit_history": "nunca",
        "capacity_status": "unknown",
        "payment_habit": "reportado",
        "phone_plan": "prepago",
        "has_gas_natural": False
    })
