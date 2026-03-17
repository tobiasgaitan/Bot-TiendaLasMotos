"""
Cerebro IA - AI Brain Service
Handles intelligent responses using Google Gemini AI for general inquiries.
"""

import logging
import os
import time
import json
import re
from typing import Optional, Dict, Any
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InvalidArgument

logger = logging.getLogger(__name__)

# Try to import Vertex AI
try:
    import vertexai
    from vertexai.generative_models import (
        GenerativeModel,
        Tool,
        FunctionDeclaration,
        Content,
        Part,
        GenerationConfig,
        ToolConfig
    )
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("⚠️  Vertex AI not available, using fallback responses")


class CerebroIA:
    def __init__(self, config_loader=None, catalog_service=None):
        self.config_loader = config_loader
        self.catalog_service = catalog_service
        self.motor_financiero = None 
        self._model = None
        self.tools = self._create_tools()
        
        if VERTEX_AI_AVAILABLE:
            try:
                vertexai.init(project="tiendalasmotos", location="us-central1")
                # Cambiado a 'gemini-1.5-flash-002' para evitar el error 404 de versión
                self._model = GenerativeModel(
                    "gemini-1.5-flash-002", 
                    tools=[self.tools] if self.tools else []
                )
                logger.info("🧠 CerebroIA initialized with Gemini 1.5 Flash (Stable)")
            except Exception as e:
                logger.error(f"❌ Error initializing Vertex AI: {str(e)}")
                self._model = None

    def _get_current_instruction(self) -> str:
        if self.config_loader:
            try:
                personality = self.config_loader.get_juan_pablo_personality()
                return personality.get("system_instruction", "")
            except: pass
        from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
        return JUAN_PABLO_SYSTEM_INSTRUCTION
    
    def _determine_funnel_phase(self, prospect_data: Optional[Dict[str, Any]]) -> str:
        if not prospect_data: return "PHASE_1_PROFILING"
        if prospect_data.get("habeas_data_accepted") is True: return "PHASE_3_CREDIT_PROFILING"
        
        has_name = bool(prospect_data.get("name") or prospect_data.get("nombre"))
        has_city = bool(prospect_data.get("ciudad"))
        moto_confirmada = prospect_data.get("moto_confirmada") is True
        is_credit = prospect_data.get("payment_method") == "credito"

        if has_name and has_city and moto_confirmada and is_credit:
            return "PHASE_2_HABEAS_DATA"
        return "PHASE_1_PROFILING"

    def pensar_respuesta(self, texto: str, context: str = "", prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        raw_response = self._generate_with_retry(texto, context, prospect_data, history, skip_greeting)
        if raw_response and not raw_response.startswith("HANDOFF_TRIGGERED:"):
             return self.clean_parrot_phrases(raw_response)
        return raw_response

    @staticmethod
    def clean_parrot_phrases(text: str) -> str:
        forbidden = [r"¡?Claro que sí!?", r"Claro,", r"¡?Excelente!?", r"¡?Perfecto!?", r"¡?Entendido!?"]
        cleaned = text
        for phrase in forbidden:
            cleaned = re.sub(r"^\s*" + phrase + r"[\s,.]*", "", cleaned, flags=re.IGNORECASE).strip()
        if cleaned and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned

    def _create_tools(self) -> Optional[Tool]:
        if not VERTEX_AI_AVAILABLE: return None
        try:
            handoff = FunctionDeclaration(name="trigger_human_handoff", description="Escala a humano", parameters={"type": "object", "properties": {"reason": {"type": "string", "enum": ["user_explicit_request"]}}})
            catalog = FunctionDeclaration(name="search_catalog", description="Busca motos", parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})
            credit = FunctionDeclaration(name="calculate_credit_score", description="Estudio de crédito", parameters={"type": "object", "properties": {"ocupacion": {"type": "string"}}, "required": ["ocupacion"]})
            return Tool(function_declarations=[handoff, catalog, credit])
        except: return None

    def _generate_with_retry(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        if not self._model: return self._fallback_response(texto)
        
        # --- STOP-GATE CONFIG ---
        moto_confirmada = prospect_data.get("moto_confirmada") is True if prospect_data else False
        allowed = ["search_catalog", "trigger_human_handoff"]
        if moto_confirmada: allowed.append("calculate_credit_score")
        
        t_config = ToolConfig(function_calling_config=ToolConfig.FunctionCallingConfig(
            mode=ToolConfig.FunctionCallingConfig.Mode.ANY,
            allowed_function_names=allowed
        ))

        phase = self._determine_funnel_phase(prospect_data)
        instruction = self._get_current_instruction()
        
        prompt = f"{instruction}\n\nFase: {phase}\nContexto: {context}\nUsuario: {texto}\nJuan Pablo:"

        for attempt in range(3):
            try:
                # Mapeo manual de historial
                contents = []
                for m in history[-6:]:
                    role = "user" if m['role'] == 'user' else "model"
                    contents.append(Content(role=role, parts=[Part.from_text(str(m.get('content', '')))]))
                contents.append(Content(role="user", parts=[Part.from_text(prompt)]))

                # Generación con ToolConfig corregido
                response = self._model.generate_content(
                    contents=contents,
                    generation_config=GenerationConfig(temperature=0.2),
                    tool_config=t_config
                )

                # Bucle de herramientas (Maneja múltiples llamadas)
                for _ in range(3):
                    if not response.candidates: break
                    candidate = response.candidates[0]
                    calls = [p.function_call for p in candidate.content.parts if p.function_call]
                    
                    if not calls: return response.text.strip() if response.text else self._fallback_response(texto)

                    contents.append(candidate.content)
                    res_parts = []
                    for fc in calls:
                        if fc.name == "trigger_human_handoff": return "HANDOFF_TRIGGERED:user_request"
                        if fc.name == "search_catalog":
                            q = fc.args.get("query", texto)
                            items = self.catalog_service.search_items(q) if self.catalog_service else []
                            txt = f"Encontré: {items[0]['name']} - {items[0]['formatted_price']}" if items else "No hay stock."
                            res_parts.append(Part.from_function_response(name=fc.name, response={"content": txt}))
                    
                    contents.append(Content(role="user", parts=res_parts))
                    response = self._model.generate_content(contents=contents, tool_config=t_config)

            except (ResourceExhausted, ServiceUnavailable): time.sleep(2**attempt)
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                break
        return self._fallback_response(texto)

    def detect_sentiment(self, text: str) -> str:
        return "NEUTRAL" # Simplificado para estabilidad

    def generate_summary(self, conversation_text: str, last_bot_question: str = "") -> Dict[str, Any]:
        """RESTAURADO: Extrae datos para Firestore"""
        if not self._model: return {"summary": "", "extracted": {}}
        try:
            prompt = f"Resume y extrae JSON de: {conversation_text}"
            res = self._model.generate_content(prompt, generation_config=GenerationConfig(response_mime_type="application/json"))
            return json.loads(res.text)
        except:
            return {"summary": "Conversación en curso", "extracted": {}}

    def _fallback_response(self, texto: str, history: list = []) -> str:
        return "¡Qué pena! Se me quedó colgado el sistema del concesionario un segundo. 😅 ¿Me lo repites?"