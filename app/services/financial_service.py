"""
Financial Service
Core decision engine for credit scoring, routing, and simulation.
v1.5.0 - Consolidated Service Layer (Parity v1.4.0)
"""

import logging
import re
from typing import Dict, Any, List, Optional, Union
from app.services.config_service import config_service
from app.services.scoring_service import scoring_service

logger = logging.getLogger(__name__)

class FinancialService:
    """
    Service for calculating credit scores, determining financing strategies,
    and performing loan simulations with matrix-aware parity.
    """

    def __init__(self):
        """Initialize with dependencies."""
        self._config_service = config_service
        self._scoring_service = scoring_service
        logger.info("💰 FinancialService initialized (v1.5.0)")

    @property
    def link_brilla(self) -> str:
        """Get Brilla link from configuration."""
        # WHY [BOT-ARQ-E2E-095]: Blindado con try/except para que un documento
        # 'partners' vacío o ausente en Firestore no colapse el runtime antes
        # de emitir trazas a Langfuse (Zero-Silent-Failures).
        try:
            partners = self._config_service.get_partners_config()
            return partners.get("link_brilla", "#") if partners else "#"
        except Exception as e:
            logger.exception(
                f"[BOT-ARQ-E2E-095] Fallo al obtener link_brilla de partners config: {e}"
            )
            return "#"

    def calculate_payment(
        self, 
        precio: float, 
        inicial: float, 
        plazo_meses: int, 
        entidad: str = "Brilla de Gases",
        moto_cc: float = 0.0,
        category: str = "motos"
    ) -> Dict[str, Any]:
        """
        Calculate monthly payment with Matrix-Aware Parity (v1.4.0).
        Target: Apache 160 -> $589.787 (24m, 1.5M init).
        """
        try:
            monto_base = precio - inicial
            
            # --- PHASE 1: CONFIG RETRIEVAL ---
            entity_config = self._config_service.get_financial_entity_config(entidad)
            row = self._get_matrix_row(entidad, moto_cc, category)
            
            # Factor Extraction
            factor = 0.0
            if row and "factors" in row:
                factors_map = row.get("factors", {})
                factor_val = factors_map.get(str(plazo_meses)) or factors_map.get(int(plazo_meses))
                if factor_val:
                    factor = float(factor_val)
            
            row_fng = row.get("fngRate") if row else None
            root_fng_rate = float(entity_config.get("fngRate", 20.66))
            fng_to_apply = float(row_fng) if row_fng is not None else root_fng_rate
            
            # --- PHASE 2: CAPITALIZATION ---
            row_reg = row.get("registrationCreditGeneral") if row else None
            entity_reg = entity_config.get("registro") if entity_config else 0
            registro = float(row_reg if row_reg is not None else (entity_reg or 0))
            
            if entidad in ["Brilla de Gases", "Brilla"]:
                # Precision milimétrica de calculator.ts para Brilla de Gases
                import math
                def js_round(val: float) -> int:
                    return math.floor(val + 0.5)

                cc_val = math.floor(float(moto_cc))
                
                # Rule: if cylinder capacity <= 125 cc, registration cost to finance is strictly 780000 COP,
                # otherwise take the corresponding value from matrix/global params.
                if cc_val <= 125:
                    reg_cost = 780000.0
                else:
                    reg_cost = float(self._config_service.get_registration_cost(cc=cc_val, category=category))
                
                # Reconstruct catalog price (full price including registration)
                assetPrice = precio + reg_cost
                
                # Check if registration is financed (only up to 125 cc)
                financeDocs = (cc_val <= 125)
                docsTotal = reg_cost if financeDocs else 0.0
                
                # Next.js pipeline: p1_base = assetPrice - inicial + docsTotal
                p1_base = assetPrice - inicial + docsTotal
                
                brillaManagementRate = float(entity_config.get("brillaManagementRate", 0))
                vGestion = js_round(p1_base * (brillaManagementRate / 100))
                
                p2_intermediate = p1_base + vGestion
                
                coverageRate = float(entity_config.get("coverageRate", 4))
                vCobertura = js_round(p2_intermediate * (coverageRate / 100))
                
                cuota_aval_mensual = js_round(vCobertura / 12.0)
                
                P_final = p2_intermediate
            else:
                capital_inicial = round(monto_base + registro, 0)
                
                fng_rate = fng_to_apply
                fng_cost = round(capital_inicial * (fng_rate / 100), 0)
                
                mgmt_rate = float(entity_config.get("brillaManagementRate", 0))
                mgmt_cost = round((capital_inicial + fng_cost) * (mgmt_rate / 100), 0)
                
                P_final = round(capital_inicial + fng_cost + mgmt_cost, 0)
                
                cov_rate = float(entity_config.get("coverageRate", 4))
                base_aval = P_final
                cov_cost = round(base_aval * (cov_rate / 100), 0)
                cuota_aval_mensual = round(cov_cost / 12, 0) if cov_cost > 0 else 0
            
            # --- PHASE 3: CALCULATION ---
            seguro_vida = float(entity_config.get("life_insurance_monthly", 15000))                
            if factor > 0:
                if entidad in ["Brilla de Gases", "Brilla"]:
                    basePmt = P_final * factor
                    cuota_mensual = js_round(basePmt + seguro_vida + cuota_aval_mensual)
                else:
                    cuota_mensual = round((round(P_final, 0) * factor) + seguro_vida, 0)
                uso_matriz = True
            else:
                rate = float(row.get("interestRate") if row else entity_config.get("interest_rate", 2.5))
                monthly_rate = rate / 100
                f = (monthly_rate * (1 + monthly_rate) ** plazo_meses) / ((1 + monthly_rate) ** plazo_meses - 1)
                if entidad in ["Brilla de Gases", "Brilla"]:
                    basePmt = P_final * f
                    cuota_mensual = js_round(basePmt + seguro_vida + cuota_aval_mensual)
                else:
                    cuota_mensual = round((P_final * f) + seguro_vida + cuota_aval_mensual, 0)
                uso_matriz = False
            
            return {
                "cuota_mensual": float(cuota_mensual),
                "total_pagar": float(cuota_mensual * plazo_meses),
                "capital_financiado": float(P_final),
                "seguro_vida": float(seguro_vida),
                "cuota_aval": float(cuota_aval_mensual),
                "plazo_meses": plazo_meses,
                "entidad": entidad,
                "uso_matriz": uso_matriz
            }
        except Exception as e:
            # WHY [BOT-FINANCE-ERR-094]: Zero-Silent-Failures — registrar traza forense completa
            # para que Langfuse capture el span. NO se silencia el fallo original.
            logger.exception(
                f"[BOT-FINANCE-ERR-094] Fallo en calculate_payment | "
                f"entidad={entidad}, plazo={plazo_meses}, precio={precio}, inicial={inicial} | "
                f"Error: {e}"
            )
            
            # gRPC or NoneType collection failure check
            err_msg = str(e).lower()
            if (
                "nonetype" in err_msg
                or "collection" in err_msg
                or "grpc" in err_msg
                or isinstance(e, AttributeError)
            ):
                raise RuntimeError(
                    f"CRITICAL: Financial gRPC or collection NoneType failure. Cannot mask error: {e}"
                ) from e

            # Fallback defensivo: Amortización Básica con tasa default.
            # Garantiza retorno coherente (cuota_mensual > 0) en ausencia de config de Firestore.
            try:
                monto_base = max(precio - inicial, 0.0)
                seguro_vida = self._get_insurance_monthly(entidad, monto_base)
                rate = 1.95 / 100  # Tasa NMV default Crédito Brilla
                f = (rate * (1 + rate) ** plazo_meses) / ((1 + rate) ** plazo_meses - 1)
                cuota = round((monto_base * f) + seguro_vida, 0)
                return {
                    "cuota_mensual": float(cuota),
                    "total_pagar": float(cuota * plazo_meses),
                    "capital_financiado": float(monto_base),
                    "seguro_vida": float(seguro_vida),
                    "cuota_aval": 0.0,
                    "plazo_meses": plazo_meses,
                    "entidad": entidad,
                    "uso_matriz": False,
                    "error_matriz": str(e)
                }
            except Exception as inner_e:
                # WHY: Segunda barrera forense — si el fallback mismo falla (ej. monto_base negativo),
                # se registra con contexto completo. PROHIBIDO silenciar este nivel.
                logger.exception(
                    f"[BOT-FINANCE-ERR-094] Fallo en fallback de calculate_payment | "
                    f"entidad={entidad}, plazo={plazo_meses} | inner_error={inner_e}"
                )
                return {
                    "cuota_mensual": 0.0,
                    "total_pagar": 0.0,
                    "capital_financiado": 0.0,
                    "seguro_vida": 0.0,
                    "cuota_aval": 0.0,
                    "plazo_meses": plazo_meses,
                    "entidad": entidad,
                    "uso_matriz": False,
                    "error": str(e),
                    "inner_error": str(inner_e)
                }

    def _get_matrix_row(self, entity_id: str, moto_cc: float, category: str = "motos") -> Optional[Dict[str, Any]]:
        """Lookup the matching row in the financial matrix."""
        matrix = self._config_service.get_financial_matrix(entity_id)
        if not matrix: return None
        matching_rows = []
        import math
        cc_val = math.floor(float(moto_cc))
        for row in matrix:
            min_cc = math.floor(float(row.get("minCC", 0)))
            max_cc = math.floor(float(row.get("maxCC", 9999)))
            if min_cc <= cc_val <= max_cc:
                matching_rows.append(row)
        if not matching_rows: return None
        matching_rows.sort(key=lambda x: float(x.get("minCC", 0)), reverse=True)
        return matching_rows[0]

    def _get_insurance_monthly(self, entity_id: str, financed_amount: float) -> float:
        """Calculate monthly life insurance based on entity configuration."""
        try:
            entity_config = self._config_service.get_financial_entity_config(entity_id)
            if "lifeInsuranceValue" in entity_config:
                return float(entity_config.get("lifeInsuranceValue", 0))
            
            fin_config = self._config_service.get_financial_config()
            mode = fin_config.get("life_insurance_mode", "fixed")
            if mode == "rate":
                rate = float(fin_config.get("life_insurance_rate", 0.000806))
                return financed_amount * rate
            else:
                return float(fin_config.get("life_insurance_monthly", 15000))
        except Exception as e:
            logger.warning(f"⚠️ [FINANCIAL_SERVICE] Error calculating life insurance for {entity_id}, falling back to 15000.0: {e}", exc_info=True)
            return 15000.0 # Baseline fallback

    # Alias for legacy compatibility
    calcular_cuota = calculate_payment

    def evaluate_profile(self, profile_data: Optional[Dict[str, Any]] = None, entidad: Optional[str] = None, reportes: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Evaluate financial profile and determine best strategy (SSOT).
        Supports both dict input and direct keyword arguments.

        WHY [BOT-ARQ-E2E-095]: El bloque de acceso a 'partners' está blindado con
        try/except + logger.exception para garantizar que un documento ausente o
        vacío en Firestore no colapse el agentic loop antes de emitir trazas a
        Langfuse. Si la configuración falla, se usa '#' como fallback de link_url.
        """
        data = profile_data or kwargs
        # Capture from parameters if not present in profile_data/kwargs
        entidad = entidad or data.get("entidad")
        reportes = reportes or data.get("reportes")
        
        logger.info(f"Evaluating profile with explicit entidad: {entidad}, reportes: {reportes}")

        # [BOT-QA-REVISION-099] Align parameters to EXTRACTION_SCHEMA strict keys: 'ocupacion' and 'datacredito'
        ocupacion = data.get("ocupacion", data.get("ocupacion_y_contrato", data.get("labor_type", "")))
        datacredito = data.get("datacredito", data.get("historial_datacredito", data.get("credit_history", "")))

        score = self._scoring_service.calculate_score(
            ocupacion_y_contrato=ocupacion,
            historial_datacredito=datacredito,
            ingresos_demostrables=str(data.get("ingresos_demostrables", data.get("income", ""))),
            plan_celular=data.get("plan_celular", data.get("phone_plan", ""))
        )
        
        strategy_info = self._scoring_service.determine_strategy(
            score=score,
            tiene_gas_natural=data.get("tiene_gas_natural", data.get("has_gas_natural", False)),
            historial_datacredito=datacredito,
            mora_y_paz_salvo=data.get("mora_y_paz_salvo", "")
        )
        
        # [BOT-ARQ-E2E-095] Blindaje de partners: si Firestore devuelve {} o falla,
        # se registra traza forense y se usa fallback '#' para no colapsar el runtime.
        link_url = "#"
        try:
            partners = self._config_service.get_partners_config()
            if partners and strategy_info.get("link_key"):
                link_url = partners.get(strategy_info["link_key"], "#")
        except Exception as e:
            logger.exception(
                f"[BOT-ARQ-E2E-095] Fallo al obtener partners config en evaluate_profile. "
                f"Usando link_url='#' como fallback. entity={strategy_info.get('entity')}, "
                f"link_key={strategy_info.get('link_key')} | Error: {e}"
            )
        
        requires_documents = False
        if strategy_info.get("entity") in ["Brilla de Gases", "Brilla"]:
            link_url = None
            requires_documents = True

        return {
            "score": score,
            "strategy": strategy_info["strategy"],
            "entity": strategy_info["entity"],
            "rate_key": strategy_info["rate_key"],
            "link_url": link_url,
            "requires_aval": strategy_info["requires_aval"],
            "is_fallback": strategy_info.get("is_fallback", False),
            "requires_documents": requires_documents,
            "explanation": f"Basado en tu perfil (Score: {score}), la mejor opción es {strategy_info.get('entity', 'N/A')}.",
            "entidad": entidad,
            "reportes": reportes
        }

    # Alias for legacy compatibility
    evaluar_perfil = evaluate_profile

    def simulate_credit(self, text: str, catalog: List[Dict]) -> str:
        """
        Simulate a credit based on user input text (Robust extraction).
        """
        try:
            # Extract entities
            moto_obj = self._extract_moto(text, catalog)
            inicial = self._extract_money(text)
            
            # Logic flow based on extracted data
            if moto_obj and inicial > 0:
                return self._generate_full_simulation_response(moto_obj, inicial)
            
            elif moto_obj:
                return f"""
🏍️ **Simulación para {moto_obj.get('name', 'tu moto')}**

El precio de referencia es ${moto_obj.get('price', 0):,.0f}.

💰 **¿Cuánto te gustaría dar de inicial?**
Por ejemplo: "Doy 1 millón" o "Tengo 500mil".
                """.strip()
                
            elif inicial > 0:
                formatted_inicial = f"${inicial:,.0f}"
                return f"""
💰 Entendido, tienes una inicial de **{formatted_inicial}**.

🏍️ **¿Para qué moto te gustaría hacer la simulación?**
(Ej: NKD 125, Sport 100, Victory Black, MRX 150)
                """.strip()
                
            else:
                return self._generate_generic_response()
            
        except Exception as e:
            logger.error(f"❌ Error in credit simulation: {str(e)}")
            return "Lo siento, hubo un error al procesar tu solicitud de crédito. Por favor intenta nuevamente indicando la moto y la inicial."

    def _generate_generic_response(self) -> str:
        """Return generic response when no entities are detected."""
        try:
            financial_config = self._config_service.get_financial_config()
        except Exception as e:
            logger.exception(f"[BOT-ARQ-E2E-095] Fallo al obtener financial_config en _generate_generic_response: {e}")
            financial_config = {}
        tasa_banco = financial_config.get("tasa_nmv_banco", 1.87)
        tasa_brilla = 1.95  # Crédito Brilla rate
        
        # [BOT-ARQ-E2E-095] Blindaje de partners: fallback seguro si Firestore vacío.
        link_brilla = "#"
        try:
            partners_config = self._config_service.get_partners_config()
            link_brilla = partners_config.get("link_brilla", "#") if partners_config else "#"
        except Exception as e:
            logger.exception(f"[BOT-ARQ-E2E-095] Fallo al obtener partners_config en _generate_generic_response: {e}")
            
        return f"""
🏍️ **Simulación de Crédito - Tienda Las Motos**

Para ofrecerte la mejor opción de financiación, necesito algunos datos:

📋 **Información Requerida**:
1. ¿Qué moto te interesa? (Ej: NKD 125, Sport 100)
2. ¿Cuánto puedes dar de inicial?

💳 **Nuestras Tasas**:
- Banco de Bogotá: {tasa_banco}% mensual (perfil bancario)
- Crédito Brilla: {tasa_brilla}% mensual (con servicio de gas) [Más info]({link_brilla})

📱 **Ejemplo**: "Quiero la NKD 125 y tengo 1 millón de inicial"
        """.strip()

    def _extract_moto(self, text: str, catalog: List[Dict]) -> Optional[Dict]:
        """Extract motorcycle object from text using catalog matching."""
        if not catalog: return None
        text_lower = text.lower()
        best_match = None
        max_len = 0
        
        for moto in catalog:
            moto_id = moto.get('id', '').lower()
            moto_name = moto.get('name', '').lower()
            
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
        """Extract monetary value from text (v1.4.0 robust)."""
        text_lower = text.lower()
        try:
            clean_text = text_lower.replace('$', '').replace('.', '').replace(',', '')
            
            millones_match = re.search(r'(\d+)\s*(?:millones|millon|millón)', clean_text)
            if millones_match: return float(millones_match.group(1)) * 1_000_000
            
            if "un millón" in text_lower or "un millon" in text_lower: return 1_000_000.0

            mil_match = re.search(r'(\d+)\s*(?:mil|k)', clean_text)
            if mil_match: return float(mil_match.group(1)) * 1_000
                
            context_match = re.search(r'(?:inicial|cuota|pie|tengo|doy)\s*(?:de)?\s*\$?\s*([\d\.,]+)', text_lower)
            if context_match:
                val_str = context_match.group(1).replace('.', '').replace(',', '')
                if val_str.isdigit(): return float(val_str)

            numbers = re.findall(r'\d+', clean_text)
            for num in numbers:
                val = float(num)
                if val >= 100_000: return val
            return 0.0
        except Exception as e:
            logger.warning(f"⚠️ [FINANCIAL_SERVICE] Error parsing inicial text '{text_lower}': {e}", exc_info=True)
            return 0.0

    def _generate_full_simulation_response(self, moto: Dict, inicial: float) -> str:
        """Generate full simulation response with parity v1.4.0."""
        precio_moto = float(moto.get('price', 0))
        nombre_moto = moto.get('name', 'Moto')
        
        try:
            cc_raw = moto.get('cc') or moto.get('displacement') or moto.get('cilindraje') or 0
            moto_cc = float(re.sub(r'[^\d.]', '', str(cc_raw))) if cc_raw else 0.0
        except: moto_cc = 0.0
            
        category = moto.get('category', 'motos')
        if precio_moto <= 0: return f"Lo siento, no tengo el precio para la {nombre_moto}."
            
        loan_amount = precio_moto - inicial
        if loan_amount <= 0: return f"¡Genial! Con esa inicial cubres el valor total de la {nombre_moto}."
            
        entidad_default = "Brilla de Gases"
        tasa_mensual = 1.95
        
        plan_24 = self.calculate_payment(precio_moto, inicial, 24, entidad=entidad_default, moto_cc=moto_cc, category=category)
        plan_36 = self.calculate_payment(precio_moto, inicial, 36, entidad=entidad_default, moto_cc=moto_cc, category=category)
        plan_48 = self.calculate_payment(precio_moto, inicial, 48, entidad=entidad_default, moto_cc=moto_cc, category=category)
        
        return f"""
🏍️ **Simulación para {nombre_moto}**

💰 **Valor Moto:** ${precio_moto:,.0f}
💵 **Inicial:** ${inicial:,.0f}
📉 **Saldo a financiar:** ${loan_amount:,.0f}

**Opciones de Cuota Mensual** (Aprox.*):
🗓️ **24 meses:** ${plan_24.get('cuota_mensual', 0):,.0f} / mes
🗓️ **36 meses:** ${plan_36.get('cuota_mensual', 0):,.0f} / mes
🗓️ **48 meses:** ${plan_48.get('cuota_mensual', 0):,.0f} / mes

_*Cálculo basado en tasa de {tasa_mensual}% MV. Incluye SOAT y Matrícula._

📱 ¿Te gustaría iniciar el estudio de crédito? Responde **SÍ** para continuar.
        """.strip()

    # Alias for legacy compatibility
    simular_credito = simulate_credit

# Global singleton instance
financial_service = FinancialService()
