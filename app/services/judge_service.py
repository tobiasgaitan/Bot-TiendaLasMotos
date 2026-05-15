"""
Judge Service (v9.8.0)
=====================
Real-time audit engine for AI responses.
Ensures compliance with 9 critical business criteria (Visual-Lock, Parity, etc.).
"""

import logging
import re
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from app.services.financial_service import financial_service
from app.services.scoring_service import scoring_service
from app.core.config import settings

logger = logging.getLogger(__name__)

# Use the new unified google-genai SDK for semantic auditing
try:
    from google import genai
    from google.genai import types
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    logger.warning("⚠️ google-genai SDK not available for JudgeService semantic audit.")

class JudgeService:
    """
    The 'Matriz de Vida o Muerte' auditor.
    Analyzes AI responses before they reach the user.
    """

    def __init__(self, cerebro_ia=None):
        """
        Initialize with optional CerebroIA for semantic auditing.
        
        Args:
            cerebro_ia: The AI brain instance to reuse its model client.
        """
        self.cerebro_ia = cerebro_ia
        self._model_id = "gemini-2.5-flash"
        self._client = None
        
        if SDK_AVAILABLE:
            try:
                # Optimized for Vertex AI
                self._client = genai.Client(
                    vertexai=True,
                    project="tiendalasmotos",
                    location="us-central1"
                )
                logger.info("⚖️ JudgeService semantic client initialized (v2.5 Flash)")
            except Exception as e:
                logger.error(f"❌ Failed to initialize GenAI Client for Judge: {e}")

    async def analyze_response(
        self, 
        user_input: str, 
        ai_response: str, 
        catalog_context: str = "", 
        financial_context: Dict[str, Any] = None,
        prospect_data: Dict[str, Any] = None,
        history: List[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Main audit entry point. Runs the 9-criteria matrix.
        
        Returns:
            Tuple[bool, str]: (is_approved, rejection_reason)
        """
        prospect_data = prospect_data or {}
        history = history or []
        
        logger.info(f"⚖️ [JUDGE] Starting Audit for response: '{ai_response[:50]}...'")

        # --- CRITERIO 9: City Discovery (Logic) ---
        # Block advance to credit if city is missing.
        is_moving_to_credit = self._detect_credit_advance(ai_response)
        has_city = bool(prospect_data.get("ciudad") or prospect_data.get("city"))
        if is_moving_to_credit and not has_city:
            return False, "C9_CITY_MISSING: El bot intenta avanzar a crédito sin haber preguntado la ciudad."

        # --- CRITERIO 5: Two-Question-Rule (Heuristic) ---
        # Count question marks. Max 2.
        if ai_response.count("?") > 2:
            return False, "C5_TWO_QUESTION_RULE: La respuesta contiene más de dos pregunta."

        # --- CRITERIO 1: Visual-Lock (Heuristic) ---
        # If a bike is mentioned, it must have $ and image link.
        if self._mentions_bike(ai_response):
            if "$" not in ai_response:
                return False, "C1_VISUAL_LOCK: Se mencionó una moto pero falta el precio ($)."
            # Search for Markdown image or custom IMAGE tag
            if not re.search(r'!\[.*?\]\(.*?\)|\[IMAGE:.*?\]', ai_response):
                return False, "C1_VISUAL_LOCK: Se mencionó una moto pero falta el enlace de imagen Markdown."

        # --- CRITERIO 3: Habeas Data Guard (Logic) ---
        # No financial questions if habeas_data_accepted is False.
        habeas_accepted = prospect_data.get("habeas_data_accepted", False)
        if not habeas_accepted and self._is_profiling_attempt(ai_response):
            return False, "C3_HABEAS_DATA_VIOLATION: Intento de perfilamiento financiero sin consentimiento Habeas Data."

        # --- CRITERIO 2: Financial Parity (Math) ---
        # Verification against FinancialService v1.5.0.
        parity_ok, parity_err = self._check_financial_parity(ai_response, prospect_data)
        if not parity_ok:
            return False, f"C2_FINANCIAL_PARITY: {parity_err}"

        # --- CRITERIO 6: Scoring Accuracy (Logic) ---
        # Check if recommended entity matches score.
        scoring_ok, scoring_err = self._check_scoring_consistency(ai_response, prospect_data)
        if not scoring_ok:
            return False, f"C6_SCORING_INCONSISTENCY: {scoring_err}"

        # --- CRITERIO 7: Brilla Protocol (Logic) ---
        # If Brilla, must ask for ID + Gas.
        if "Brilla" in ai_response and not ("cédula" in ai_response.lower() and "gas" in ai_response.lower()):
            if "Crédito Brilla" in ai_response or "financiación Brilla" in ai_response:
                return False, "C7_BRILLA_PROTOCOL: Falta solicitar Cédula y Recibos de Gas para Brilla."

        # --- CRITERIO 8: Conversion Path (Link check) ---
        # Verify links match SSOT and authorized domains.
        links_ok, links_err = self._check_links(ai_response)
        if not links_ok:
            return False, f"C8_CONVERSION_PATH: {links_err}"

        # --- CRITERIO 4: Catalog-Lock (Semantic/LLM) ---
        # Check for hallucinated specs using Gemini 2.5 Flash.
        if self._client and catalog_context:
            catalog_ok, catalog_err = await self._check_catalog_lock_semantic(ai_response, catalog_context)
            if not catalog_ok:
                return False, f"C4_CATALOG_HALLUCINATION: {catalog_err}"

        logger.info("✅ [JUDGE] Response APPROVED.")
        return True, ""

    # --- HELPERS ---

    def _mentions_bike(self, text: str) -> bool:
        keywords = ["TVS", "Victory", "Apache", "Raider", "Sport", "Life", "Stryker"]
        return any(kw.lower() in text.lower() for kw in keywords)

    def _detect_credit_advance(self, text: str) -> bool:
        keywords = ["crédito", "financiar", "cuotas", "mensualidad", "requisitos", "estudio de crédito"]
        return any(kw.lower() in text.lower() for kw in keywords)

    def _is_profiling_attempt(self, text: str) -> bool:
        keywords = ["trabaja", "ingresos", "gana", "datacrédito", "reportado", "vivienda", "arriendo", "celular"]
        return any(kw.lower() in text.lower() for kw in keywords)

    def _check_financial_parity(self, text: str, prospect_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        C2 — Financial Parity (Math v2.0).
        Validates quoted amounts against FinancialService.calculate_payment.
        WHY: The previous implementation only caught literal '$X.XXX' placeholders.
             A hallucinated quote like '$9.999.999' would pass unchecked.
        """
        # --- Guard 1: Detect raw placeholders ($X.XXX) ---
        if re.search(r'\$X[\.X]+', text):
            return False, "Se detectó un placeholder financiero ($X.XXX)."

        # --- Guard 2: Cross-validation against FinancialService ---
        # Only activate when we have the financial context required for computation.
        financial_context = prospect_data.get("financial_context", {})
        precio = financial_context.get("precio")
        inicial = financial_context.get("inicial")
        plazo_meses = financial_context.get("plazo_meses")

        if not (precio and inicial and plazo_meses):
            # Cannot validate without financial context — pass through.
            return True, ""

        try:
            # Extract all monetary amounts in the format $X.XXX.XXX or $X.XXX
            # Matches: $589.787 / $1.250.000 / $589,787 (Colombian notation)
            amount_matches = re.findall(
                r'\$([\d]{1,3}(?:[.,]\d{3})+)',
                text
            )
            if not amount_matches:
                return True, ""

            # Normalize extracted amounts to float (handle both dot and comma separators)
            extracted_amounts = []
            for raw in amount_matches:
                # Remove thousands separators (both . and ,) — Colombian format uses '.'
                normalized = raw.replace('.', '').replace(',', '')
                try:
                    extracted_amounts.append(float(normalized))
                except ValueError:
                    continue

            # Compute the canonical expected quote from FinancialService
            result = financial_service.calculate_payment(
                precio=float(precio),
                inicial=float(inicial),
                plazo_meses=int(plazo_meses)
            )
            expected_cuota = result.get("cuota_mensual", 0)

            if expected_cuota <= 0:
                # Calculation failed or returned zero — cannot validate, pass through.
                return True, ""

            # Check if ANY of the extracted amounts deviates > 1% from the expected quote.
            # We use a tolerance window: the bot may present multi-plan quotes (24/36/48m),
            # so we only flag if the extracted amount is in the cuota range (not a price).
            MARGIN_PCT = 1.0
            # A cuota is typically < 15% of the motorcycle price.
            # We use the price from context to bound the cuota range.
            precio_float = float(precio)
            MAX_CUOTA_BOUND = precio_float * 0.20  # No cuota should exceed 20% of price
            MIN_CUOTA_BOUND = expected_cuota * 0.05  # Floor: 5% of expected (catches very low)

            deviating = []
            for amount in extracted_amounts:
                # Skip amounts that clearly represent the moto price itself
                if amount > MAX_CUOTA_BOUND:
                    # BUT if it's still way too high (e.g. $9.999.999 on a $11M bike),
                    # flag it since no cuota should equal or exceed the price.
                    if amount >= precio_float * 0.80:
                        deviating.append((amount, 999.0))  # Sentinel: extreme deviation
                    continue
                # Skip amounts that are clearly too low to be cuotas
                if amount < MIN_CUOTA_BOUND:
                    continue
                deviation_pct = abs(amount - expected_cuota) / expected_cuota * 100
                if deviation_pct > MARGIN_PCT:
                    deviating.append((amount, deviation_pct))


            if deviating:
                worst = max(deviating, key=lambda x: x[1])
                logger.warning(
                    f"⚖️ [C2] Parity failure: amount=${worst[0]:,.0f} "
                    f"vs expected=${expected_cuota:,.0f} "
                    f"(deviation={worst[1]:.2f}%)"
                )
                return False, (
                    f"Cuota citada (${worst[0]:,.0f}) difiere en {worst[1]:.1f}% "
                    f"del cálculo real (${expected_cuota:,.0f}). "
                    f"Plazo: {plazo_meses}m."
                )

        except Exception as e:
            # MANDATO Zero-Silent-Failures: log completo del error, no silenciar.
            logger.exception(f"❌ [C2] Error during financial parity cross-validation: {e}")
            # On unexpected error, pass through to avoid false positives.
            return True, ""

        return True, ""

    def _check_scoring_consistency(self, text: str, prospect_data: Dict[str, Any]) -> Tuple[bool, str]:
        extracted = prospect_data.get("extracted", {})
        ocupacion = extracted.get("ocupacion", "informal")
        habit = extracted.get("datacredito", "sin experiencia")
        ingresos = extracted.get("ingresos", "minimo")
        
        score = scoring_service.calculate_score(ocupacion, habit, ingresos)
        
        if score < 400 and "Banco" in text:
            return False, f"Perfil insuficiente para Banco (Score {score})."
        return True, ""

    def _check_links(self, text: str) -> Tuple[bool, str]:
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
        for url in urls:
            if "autecomobility.com" in url or "mercadolibre" in url:
                return False, f"URL no autorizada detectada: {url}"
        return True, ""

    async def _check_catalog_lock_semantic(self, text: str, catalog_context: str) -> Tuple[bool, str]:
        if not self._client:
            return True, ""
            
        prompt = f"""
        Actúa como un Auditor de Calidad para Tienda Las Motos.
        Tu misión es detectar si el bot ha inventado o alucinado especificaciones técnicas.
        
        CATÁLOGO (VERDAD ABSOLUTA):
        {catalog_context}
        
        RESPUESTA DEL BOT:
        {text}
        
        REGLA DE ORO:
        - Si el bot menciona una moto de COMPETENCIA (ej. Boxer, NKD, Pulsar) para ofrecer un equivalente de nuestro catálogo, ES VÁLIDO y debe ser APPROVED siempre que la moto ofrecida tenga el término de competencia en sus etiquetas 'searchBy'.
        - Ejemplo: Si el catálogo muestra que 'TVS Sport 100' tiene 'boxer' en 'searchBy', y el bot dice 'No manejo la Boxer pero tengo la TVS Sport', es APPROVED.
        - Si el bot menciona CC, frenos (ABS/Disco), potencia (HP), torque (NM) o peso que NO están en el catálogo o son diferentes para nuestras motos, responde: REJECTED: [Motivo]
        - Si la respuesta es consistente, ofrece un equivalente válido o no menciona especificaciones, responde: APPROVED
        
        Respuesta:
        """
        
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_id,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.0)
            )
            result = response.text.strip()
            if "REJECTED" in result:
                return False, result.replace("REJECTED:", "").replace("REJECTED", "").strip()
            return True, ""
        except Exception as e:
            logger.error(f"❌ Semantic Audit Error: {e}")
            return True, ""

# Singleton for easy access
judge_service = JudgeService()
