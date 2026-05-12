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

        # --- CRITERIO 5: One-Question-Rule (Heuristic) ---
        # Count question marks. Max 1.
        if ai_response.count("?") > 1:
            return False, "C5_ONE_QUESTION_RULE: La respuesta contiene más de una pregunta."

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
        # Detect placeholders that shouldn't be there
        placeholder_pattern = r'\$X[\.X]+'
        if re.search(placeholder_pattern, text):
            return False, "Se detectó un placeholder financiero ($X.XXX)."
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
