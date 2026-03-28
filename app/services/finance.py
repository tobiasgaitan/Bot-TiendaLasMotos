"""
Motor Financiero - Credit Simulation Service
Handles credit simulation and financial calculations for motorcycle purchases.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Union

from google.cloud import firestore

from app.services.scoring_service import scoring_service
from app.services.config_service import config_service

logger = logging.getLogger(__name__)


class MotorFinanciero:
    """
    Financial engine for credit simulations.
    
    Calculates monthly payments, interest rates, and credit eligibility
    based on user inputs and financial configuration from Firestore.
    """
    
    def __init__(self, db: firestore.Client, config_service=None):
        """
        Initialize the financial motor.
        
        Args:
            db: Firestore client instance
            config_service: ConfigService instance for dynamic parameters
        """
        self._db = db
        # v1.3.1: Use injected service or global singleton (ConfigService)
        from app.services.config_service import config_service as global_config
        self._config_service = config_service or global_config
        self._scoring_service = scoring_service
        logger.info("💰 MotorFinanciero initialized")

    @property
    def link_brilla(self) -> str:
        """Get Brilla link from configuration."""
        if self._config_service:
            partners = self._config_service.get_partners_config()
            return partners.get("link_brilla", "#")
        return "#"

    def evaluar_perfil(
        self, 
        ocupacion_y_contrato: str, 
        ingresos_demostrables: str, 
        historial_datacredito: str,
        mora_y_paz_salvo: str,
        gastos_vivienda: str,
        tiene_gas_natural: bool,
        plan_celular: str
    ) -> Dict[str, Any]:
        """
        Evaluate financial profile and determine best strategy.
        
        Args:
            ocupacion_y_contrato: Contract type
            ingresos_demostrables: Income level
            historial_datacredito: Payment habit
            mora_y_paz_salvo: Arrears context
            gastos_vivienda: Housing expenses
            tiene_gas_natural: Has natural gas bill
            plan_celular: Mobile plan type
            
        Returns:
            Dictionary with score, strategy, and recommended entity
        """
        # Calculate Score
        score = self._scoring_service.calculate_score(
            ocupacion_y_contrato=ocupacion_y_contrato, 
            historial_datacredito=historial_datacredito, 
            ingresos_demostrables=ingresos_demostrables
        )
        
        # Determine Strategy
        strategy_info = self._scoring_service.determine_strategy(
            score=score,
            tiene_gas_natural=tiene_gas_natural,
            historial_datacredito=historial_datacredito,
            mora_y_paz_salvo=mora_y_paz_salvo
        )
        
        # Fetch Link
        link_key = strategy_info.get("link_key")
        link_url = "#"
        requires_documents = False
        
        if self._config_service and link_key:
            partners = self._config_service.get_partners_config()
            link_url = partners.get(link_key, "#")
            
        entity = strategy_info["entity"]
        
        # Brilla Exception (Document capture instead of URL redirect)
        if entity in ["Brilla de Gases", "Brilla"] or link_key == "link_brilla":
            link_url = None
            requires_documents = True
        
        return {
            "score": score,
            "strategy": strategy_info["strategy"],
            "entity": entity,
            "rate_key": strategy_info["rate_key"],
            "link_url": link_url,
            "requires_aval": strategy_info["requires_aval"],
            "is_fallback": strategy_info.get("is_fallback", False),
            "requires_documents": requires_documents,
            "explanation": f"Basado en tu perfil (Score: {score}), la mejor opción es {entity}."
        }
    
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
        tasa_banco = 1.87
        tasa_fintech = 2.22
        link_brilla = "#"
        
        if self._config_service:
            financial_config = self._config_service.get_financial_config()
            if financial_config:
                tasa_banco = financial_config.get("tasa_nmv_banco", 1.87)
                tasa_fintech = financial_config.get("tasa_nmv_fintech", 2.22)
            
            # Aliados links
            partners_config = self._config_service.get_partners_config()
            if partners_config:
                link_brilla = partners_config.get("link_brilla", "#")
            
        return f"""
🏍️ **Simulación de Crédito - Tienda Las Motos**

Para ofrecerte la mejor opción de financiación, necesito algunos datos:

📋 **Información Requerida**:
1. ¿Qué moto te interesa? (Ej: NKD 125, Sport 100)
2. ¿Cuánto puedes dar de inicial?

💳 **Nuestras Tasas**:
- Banco de Bogotá: {tasa_banco}% mensual (perfil bancario)
- CrediOrbe: {tasa_fintech}% mensual (perfil flexible)
- Crédito Brilla: 1.95% mensual (con servicio de gas) [Más info]({link_brilla})

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
        """
        precio_moto = float(moto.get('price', 0))
        nombre_moto = moto.get('name', 'Moto')
        moto_cc = float(moto.get('displacement', 0))
        category = moto.get('category', 'motos')
        
        if precio_moto <= 0:
            return f"Lo siento, no tengo el precio actualizado para la {nombre_moto}. Por favor consulta con un asesor."
            
        loan_amount = precio_moto - inicial
        
        if loan_amount <= 0:
            return f"¡Genial! Con esa inicial de ${inicial:,.0f} cubres el valor total de la {nombre_moto} (${precio_moto:,.0f}). ¡Sería una venta de contado!"
            
        # [SSOT] Mandatory v1.3.1: Use Crediorbe for proactive simulation
        entidad_default = "Crediorbe"
        tasa_mensual = 2.22 
        
        if self._config_service:
             fin_config = self._config_service.get_financial_config()
             tasa_mensual = fin_config.get("tasa_nmv_fintech", 2.22)
        
        # Calculate options using the new matrix-aware method
        plan_24 = self.calcular_cuota(precio_moto, inicial, 24, tasa_mensual, entidad=entidad_default, moto_cc=moto_cc, category=category)
        plan_36 = self.calcular_cuota(precio_moto, inicial, 36, tasa_mensual, entidad=entidad_default, moto_cc=moto_cc, category=category)
        plan_48 = self.calcular_cuota(precio_moto, inicial, 48, tasa_mensual, entidad=entidad_default, moto_cc=moto_cc, category=category)
        
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

_*Cálculo basado en matriz de factores de **{entidad_default}** (Tasa {tasa_mensual}% MV). (incluye SOAT y Matrícula). Sujeto a estudio de crédito._

📱 ¿Te gustaría iniciar el estudio de crédito para esta opción? Responde **SÍ** para continuar.
        """.strip()
    
    def _get_matrix_row(self, entity_id: str, moto_cc: float, category: str = "motos") -> Optional[Dict[str, Any]]:
        """
        Lookup the matching row in the financial matrix.
        """
        matrix = self._config_service.get_financial_matrix(entity_id)
        if not matrix:
            return None
            
        # Filter by category and find the row with the largest minCC <= moto_cc
        matching_rows = [
            row for row in matrix 
            if row.get("category") == category and float(row.get("minCC", 0)) <= moto_cc
        ]
        
        if not matching_rows:
            return None
            
        # Sort by minCC descending to get the best fit
        matching_rows.sort(key=lambda x: float(x.get("minCC", 0)), reverse=True)
        return matching_rows[0]

    def _get_insurance_monthly(self, entity_id: str, financed_amount: float) -> float:
        """
        Calculate monthly life insurance based on entity and config.
        """
        # [SSOT] Baseline: Crediorbe = $0, others = from matrix/global_params
        normalized_id = entity_id.lower()
        
        # Mandatory Guardrail: Crediorbe default insurance is $0
        if "crediorbe" in normalized_id:
            return 0.0
            
        if self._config_service:
            fin_config = self._config_service.get_financial_config()
            mode = fin_config.get("life_insurance_mode", "fixed")
            
            if mode == "rate":
                rate = float(fin_config.get("life_insurance_rate", 0.000806))
                return financed_amount * rate
            else:
                return float(fin_config.get("life_insurance_monthly", 0))
                
        return 0.0

    def calcular_cuota(
        self, 
        precio: float, 
        inicial: float, 
        plazo_meses: int, 
        tasa_mensual: float = 2.22,
        entidad: str = "Crediorbe",
        moto_cc: float = 0.0,
        category: str = "motos"
    ) -> Dict[str, Any]:
        """
        Calculate monthly payment using the Financial Matrix (v1.3.1).
        If matrix is unavailable, falls back to French Amortization.
        """
        try:
            monto_base = precio - inicial
            
            # 1. Try Matrix-based calculation (Layered Capitalization)
            row = self._get_matrix_row(entidad, moto_cc, category)
            
            if row and "factors" in row:
                factor = row.get("factors", {}).get(str(plazo_meses))
                if factor:
                    # Apply Layered Capitalization (Following calculator.ts)
                    registro = float(row.get("registrationCreditGeneral", 0))
                    fng_rate = float(row.get("fngRate", 0))
                    management_fixed = float(row.get("managementFixed", 0))
                    coverage_fixed = float(row.get("coverageFixed", 0))
                    
                    # Capital = (Base + Registro + FNG + Gestion + Cobertura)
                    fng_cost = monto_base * (fng_rate / 100)
                    capital_financiado = monto_base + registro + fng_cost + management_fixed + coverage_fixed
                    
                    cuota_mensual_base = capital_financiado * float(factor)
                    seguro_vida = self._get_insurance_monthly(entidad, capital_financiado)
                    
                    cuota_mensual = cuota_mensual_base + seguro_vida
                    
                    return {
                        "cuota_mensual": round(cuota_mensual, 2),
                        "total_pagar": round(cuota_mensual * plazo_meses, 2),
                        "capital_financiado": round(capital_financiado, 2),
                        "seguro_vida": round(seguro_vida, 2),
                        "plazo_meses": plazo_meses,
                        "entidad": entidad,
                        "usó_matriz": True
                    }

            # 2. Fallback to Standard French Amortization
            tasa_decimal = tasa_mensual / 100
            if tasa_decimal > 0:
                base = 1 + tasa_decimal
                cuota_mensual_base = (monto_base * tasa_decimal) / (1 - (base ** -plazo_meses))
            else:
                cuota_mensual_base = monto_base / plazo_meses
            
            seguro_vida = self._get_insurance_monthly(entidad, monto_base)
            cuota_mensual = cuota_mensual_base + seguro_vida
            
            return {
                "cuota_mensual": round(cuota_mensual, 2),
                "total_pagar": round(cuota_mensual * plazo_meses, 2),
                "capital_financiado": monto_base,
                "seguro_vida": seguro_vida,
                "plazo_meses": plazo_meses,
                "entidad": entidad,
                "usó_matriz": False
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating payment: {str(e)}")
            return {"error": "Error en el cálculo", "mensaje": str(e)}
