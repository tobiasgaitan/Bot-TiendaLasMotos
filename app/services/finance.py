"""
Motor Financiero - Credit Simulation Service
Handles credit simulation and financial calculations for motorcycle purchases.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Union

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
    
    def simular_credito(self, texto: str, motor_ventas: Optional[Any] = None) -> str:
        """
        Simulate a credit based on user input text.
        
        Args:
            texto: User message containing credit simulation request
            motor_ventas: Optional MotorVentas instance to access catalog
        
        Returns:
            Credit simulation response string
        """
        try:
            # Get catalog if available
            catalog = []
            if motor_ventas:
                # Access private attribute directly if getter not available or just access internal list
                # Assuming MotorVentas has _catalog or a method to get it
                if hasattr(motor_ventas, '_catalog'):
                    catalog = motor_ventas._catalog
                elif hasattr(motor_ventas, 'get_catalog'):
                    catalog = motor_ventas.get_catalog()
            
            # Extract entities
            moto_obj = self._extract_moto(texto, catalog)
            inicial = self._extract_money(texto)
            
            # Logic flow based on extracted data
            if moto_obj and inicial > 0:
                # Perfect case: We have both moto and initial payment
                return self._generar_simulacion_completa(moto_obj, inicial)
            
            elif moto_obj:
                # We have moto but no initial payment
                # We could assume 0 or ask for it. Let's ask for it or assume a standard % if we want to be proactive.
                # For now, let's just ask specifically for the initial payment contextually
                return f"""
🏍️ **Simulación para {moto_obj.get('name', 'tu moto')}**

El precio de referencia es ${moto_obj.get('price', 0):,.0f}.

💰 **¿Cuánto te gustaría dar de inicial?**
Por ejemplo: "Doy 1 millón" o "Tengo 500mil".
                """.strip()
                
            elif inicial > 0:
                # We have initial payment but no moto
                formatted_inicial = f"${inicial:,.0f}"
                return f"""
💰 Entendido, tienes una inicial de **{formatted_inicial}**.

🏍️ **¿Para qué moto te gustaría hacer la simulación?**
(Ej: NKD 125, Sport 100, Victory Black, MRX 150)
                """.strip()
                
            else:
                # Extracted nothing specific, show generic menu
                return self._respuesta_generica()
            
        except Exception as e:
            logger.error(f"❌ Error in credit simulation: {str(e)}")
            return "Lo siento, hubo un error al procesar tu solicitud de crédito. Por favor intenta nuevamente indicando la moto y la inicial."
    
    def _respuesta_generica(self) -> str:
        """Return generic response when no entities are detected."""
        if self._config_loader:
            financial_config = self._config_loader.get_financial_config()
            tasa_banco = financial_config.get("tasas", {}).get("banco", {}).get("tasa_mensual", 1.87)
            tasa_fintech = financial_config.get("tasas", {}).get("fintech", {}).get("tasa_mensual", 2.20)
        else:
            tasa_banco = 1.87
            tasa_fintech = 2.20
            
        return f"""
🏍️ **Simulación de Crédito - Tienda Las Motos**

Para ofrecerte la mejor opción de financiación, necesito algunos datos:

📋 **Información Requerida**:
1. ¿Qué moto te interesa? (Ej: NKD 125, Sport 100)
2. ¿Cuánto puedes dar de inicial?

💳 **Nuestras Tasas**:
- Banco de Bogotá: {tasa_banco}% mensual (perfil bancario)
- CrediOrbe: {tasa_fintech}% mensual (perfil flexible)
- Crédito Brilla: 1.95% mensual (con servicio de gas)

📱 **Ejemplo**: "Quiero la NKD 125 y tengo 1 millón de inicial"
        """.strip()

    def _extract_moto(self, text: str, catalog: List[Dict]) -> Optional[Dict]:
        """
        Extract motorcycle object from text using catalog matching.
        
        Args:
            text: User input text
            catalog: List of motorcycle dictionaries
            
        Returns:
            Matched motorcycle dictionary or None
        """
        if not catalog:
            return None
            
        text_lower = text.lower()
        best_match = None
        max_len = 0
        
        for moto in catalog:
            # Check ID
            moto_id = moto.get('id', '').lower()
            moto_name = moto.get('name', '').lower()
            
            # Simple containment check
            # We prefer matching the name as it's more likely what user types
            if moto_name and moto_name in text_lower:
                if len(moto_name) > max_len:
                    max_len = len(moto_name)
                    best_match = moto
            elif moto_id and moto_id in text_lower:
                if len(moto_id) > max_len:
                    max_len = len(moto_id)
                    best_match = moto
                    
        return best_match

    def _extract_money(self, text: str) -> float:
        """
        Extract monetary value from text.
        Handles "1 millon", "500 mil", "1.000.000", etc.
        
        Args:
            text: User input text
            
        Returns:
            Float value found or 0 if none
        """
        text_lower = text.lower()
        
        # Helper to convert words to numbers
        try:
            # Remove currency symbols and common noise
            clean_text = text_lower.replace('$', '').replace('.', '').replace(',', '')
            
            # Pattern for "X millones" or "X millón"
            millones_match = re.search(r'(\d+)\s*(?:millones|millon|millón)', clean_text)
            if millones_match:
                return float(millones_match.group(1)) * 1_000_000
            
            # Pattern for "un millón" or "un millon"
            if "un millón" in text_lower or "un millon" in text_lower:
                return 1_000_000.0

            # Pattern for "X mil" or "X k"
            mil_match = re.search(r'(\d+)\s*(?:mil|k)', clean_text)
            if mil_match:
                return float(mil_match.group(1)) * 1_000
                
            # Pattern for raw numbers associated with "inicial", "cuota", "tengo", "doy"
            # Looking for numbers that might be the price (large numbers)
            # Regex to find sequences of digits that might look like money (e.g., 1000000 or 1.000.000)
            # We already removed dots and commas in clean_text
            
            # Find largest number in the text that looks like a payment (e.g. > 10000)
            # We want to avoid capturing "125" from "NKD 125" as money unless it clearly looks like money
            
            # Specific context search first
            # "inicial de X" or "inicial X"
            context_match = re.search(r'(?:inicial|cuota|pie|tengo|doy)\s*(?:de)?\s*\$?\s*([\d\.,]+)', text_lower)
            if context_match:
                val_str = context_match.group(1).replace('.', '').replace(',', '')
                if val_str.isdigit():
                    return float(val_str)

            # Check for large plain numbers if "millon" or "mil" logic didn't catch it
            # But be careful not to catch model numbers like 125, 150, 200
            # Let's say a down payment is usually at least 100,000
            numbers = re.findall(r'\d+', clean_text)
            for num in numbers:
                val = float(num)
                if val >= 100_000: # Threshold to distinguish from CC or model numbers
                    return val
                    
            return 0.0
            
        except Exception as e:
            logger.warning(f"Error extracting money: {e}")
            return 0.0

    def _generar_simulacion_completa(self, moto: Dict, inicial: float) -> str:
        """
        Generate full simulation response.
        
        Args:
            moto: Motorcycle data
            inicial: Initial payment amount
            
        Returns:
            Formatted response string
        """
        precio_moto = float(moto.get('price', 0))
        nombre_moto = moto.get('name', 'Moto')
        
        if precio_moto <= 0:
            return f"Lo siento, no tengo el precio actualizado para la {nombre_moto}. Por favor consulta con un asesor."
            
        loan_amount = precio_moto - inicial
        
        if loan_amount <= 0:
            return f"¡Genial! Con esa inicial de ${inicial:,.0f} cubres el valor total de la {nombre_moto} (${precio_moto:,.0f}). ¡Sería una venta de contado!"
            
        # Default parameters
        tasa_mensual = 2.2 # Fixed as per instructions
        
        # Calculate options
        plan_24 = self.calcular_cuota(precio_moto, inicial, 24, tasa_mensual)
        plan_36 = self.calcular_cuota(precio_moto, inicial, 36, tasa_mensual)
        plan_48 = self.calcular_cuota(precio_moto, inicial, 48, tasa_mensual)
        
        # Safe handling if calculation matched error
        cuota_24 = plan_24.get('cuota_mensual', 0)
        cuota_36 = plan_36.get('cuota_mensual', 0)
        cuota_48 = plan_48.get('cuota_mensual', 0)
        
        return f"""
🏍️ **Simulación para {nombre_moto}**

💰 **Valor Moto:** ${precio_moto:,.0f}
💵 **Inicial:** ${inicial:,.0f}
📉 **Saldo a financiar:** ${loan_amount:,.0f}

**Opciones de Cuota Mensual** (Aprox.*):
🗓️ **24 meses:** ${cuota_24:,.0f} / mes
🗓️ **36 meses:** ${cuota_36:,.0f} / mes
🗓️ **48 meses:** ${cuota_48:,.0f} / mes

_*Cálculo estimado con tasa del {tasa_mensual}% MV. Sujeto a estudio de crédito y políticas de la entidad financiera. No incluye seguro ni matrícula._

📱 ¿Te gustaría iniciar el estudio de crédito para esta opción? Responde **SÍ** para continuar.
        """.strip()
    
    def calcular_cuota(
        self, 
        precio: float, 
        inicial: float, 
        plazo_meses: int, 
        tasa_mensual: float = 2.2
    ) -> Dict[str, Any]:
        """
        Calculate monthly payment for a motorcycle loan.
        Uses Standard French Amortization formula.
        
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
            
            # French Amortization Formula: A = P * (r * (1+r)^n) / ((1+r)^n - 1)
            # Equivalent to: A = P * r / (1 - (1+r)^-n)
            
            if tasa_decimal > 0:
                base = 1 + tasa_decimal
                # Using the form: P * r / (1 - (1+r)^-n) which user requested logic similar to:
                # [Monto_Financiado * Tasa] / [1 - (1 + Tasa)^-Meses]
                
                cuota_mensual = (capital * tasa_decimal) / (1 - (base ** -plazo_meses))
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
