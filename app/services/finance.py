"""
Motor Financiero - Credit Simulation Service
Handles credit simulation and financial calculations for motorcycle purchases.
"""

import logging
from typing import Dict, Any, Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)


class MotorFinanciero:
    """
    Financial engine for credit simulations.
    
    Calculates monthly payments, interest rates, and credit eligibility
    based on user inputs and financial configuration from Firestore.
    """
    
    def __init__(self, db: firestore.Client, config_loader=None):
        """
        Initialize the financial motor.
        
        Args:
            db: Firestore client instance
            config_loader: Optional ConfigLoader instance for dynamic rates
        """
        self._db = db
        self._config_loader = config_loader
        logger.info("💰 MotorFinanciero initialized")
    
    def simular_credito(self, texto: str) -> str:
        """
        Simulate a credit based on user input text.
        
        Args:
            texto: User message containing credit simulation request
        
        Returns:
            Credit simulation response string
        """
        try:
            # Get financial configuration if available
            if self._config_loader:
                financial_config = self._config_loader.get_financial_config()
                tasa_banco = financial_config.get("tasas", {}).get("banco", {}).get("tasa_mensual", 1.87)
                tasa_fintech = financial_config.get("tasas", {}).get("fintech", {}).get("tasa_mensual", 2.20)
            else:
                # Fallback to default rates
                tasa_banco = 1.87
                tasa_fintech = 2.20
            
            # Standard credit simulation response
            response = f"""
🏍️ **Simulación de Crédito - Tienda Las Motos**

Para ofrecerte la mejor opción de financiación, necesito algunos datos:

📋 **Información Requerida**:
1. ¿Qué moto te interesa? (NKD 125, Sport 100, Victory Black, MRX 150)
2. ¿Cuánto puedes dar de inicial?
3. ¿En cuántos meses quieres pagar? (12-48 meses)

💳 **Nuestras Tasas**:
- Banco de Bogotá: {tasa_banco}% mensual (perfil bancario)
- CrediOrbe: {tasa_fintech}% mensual (perfil flexible)
- Crédito Brilla: 1.95% mensual (con servicio de gas)

📱 Para una simulación personalizada, por favor proporciona los datos anteriores.
            """.strip()
            
            logger.info(f"✅ Credit simulation generated for request: {texto[:50]}...")
            return response
            
        except Exception as e:
            logger.error(f"❌ Error in credit simulation: {str(e)}")
            return "Lo siento, hubo un error al procesar tu solicitud de crédito. Por favor intenta nuevamente."
    
    def calcular_cuota(
        self, 
        precio: float, 
        inicial: float, 
        plazo_meses: int, 
        tasa_mensual: float = 1.87
    ) -> Dict[str, Any]:
        """
        Calculate monthly payment for a motorcycle loan.
        
        Args:
            precio: Motorcycle price
            inicial: Down payment
            plazo_meses: Loan term in months
            tasa_mensual: Monthly interest rate (percentage)
        
        Returns:
            Dictionary with payment details
        """
        try:
            capital = precio - inicial
            tasa_decimal = tasa_mensual / 100
            
            # Calculate monthly payment using amortization formula
            if tasa_decimal > 0:
                cuota_mensual = capital * (
                    tasa_decimal * (1 + tasa_decimal) ** plazo_meses
                ) / (
                    (1 + tasa_decimal) ** plazo_meses - 1
                )
            else:
                cuota_mensual = capital / plazo_meses
            
            total_pagar = cuota_mensual * plazo_meses
            total_intereses = total_pagar - capital
            
            return {
                "cuota_mensual": round(cuota_mensual, 2),
                "total_pagar": round(total_pagar, 2),
                "total_intereses": round(total_intereses, 2),
                "capital_financiado": capital,
                "tasa_aplicada": tasa_mensual,
                "plazo_meses": plazo_meses
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating payment: {str(e)}")
            return {
                "error": "Error en el cálculo",
                "mensaje": str(e)
            }
