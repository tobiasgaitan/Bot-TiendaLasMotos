"""
Cerebro IA - AI Brain Service
Handles intelligent responses using Google Gemini AI for general inquiries.
"""

import logging
import os
from typing import Optional, Dict, Any

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
        ToolConfig # HOTFIX #121: Requerido para el Stop-Gate
    )
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logger.warning("⚠️  Vertex AI not available, using fallback responses")


class CerebroIA:
    """
    AI Brain for intelligent conversation handling.
    """
    
    def __init__(self, config_loader=None, catalog_service=None):
        self.config_loader = config_loader
        self.catalog_service = catalog_service
        self.motor_financiero = None 
        self._model = None
        self.tools = self._create_tools()
        
        if VERTEX_AI_AVAILABLE:
            try:
                vertexai.init(project="tiendalasmotos", location="us-central1")
                self._model = GenerativeModel(
                    "gemini-1.5-flash", # Ajustado a 1.5 por estabilidad en Prod
                    tools=[self.tools] if self.tools else []
                )
                logger.info(f"🧠 CerebroIA initialized with Gemini 1.5 Flash")
            except Exception as e:
                logger.error(f"❌ Error initializing Vertex AI: {str(e)}")
                self._model = None

    def _get_current_instruction(self) -> str:
        if self.config_loader:
            try:
                personality = self.config_loader.get_juan_pablo_personality()
                instruction = personality.get("system_instruction", "")
                if instruction: return instruction
            except Exception: pass
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
        import re
        forbidden = [r"¡?Claro que sí!?", r"Claro,", r"¡?Claro!?", r"¡?Excelente!?", r"¡?Perfecto!?", r"¡?Entendido!?", r"¡?Qué bien!?", r"¡?Buen día!?"]
        cleaned = text
        for phrase in forbidden:
            cleaned = re.sub(r"^\s*" + phrase + r"[\s,.]*", "", cleaned, flags=re.IGNORECASE).strip()
        if cleaned and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
        return cleaned

    def _create_tools(self) -> Optional[Tool]:
        if not VERTEX_AI_AVAILABLE: return None
        try:
            handoff_function = FunctionDeclaration(
                name="trigger_human_handoff",
                description="Escala a humano si el usuario lo pide explícitamente.",
                parameters={"type": "object", "properties": {"reason": {"type": "string", "enum": ["user_explicit_request"]}}, "required": ["reason"]}
            )
            catalog_function = FunctionDeclaration(
                name="search_catalog",
                description="Busca motos en el catálogo. OBLIGATORIO si el usuario menciona una moto o necesidad.",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
            )
            credit_function = FunctionDeclaration(
                name="calculate_credit_score",
                description="Calcula el perfil crediticio. SOLO USAR si moto_confirmada es True.",
                parameters={"type": "object", "properties": {"ingresos": {"type": "string"}}, "required": ["ingresos"]}
            )
            return Tool(function_declarations=[handoff_function, catalog_function, credit_function])
        except Exception: return None

    def _generate_with_retry(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        """
        MODIFICACIÓN PUSH #121: Uso de generate_content + ToolConfig (Opción B)
        """
        if not self._model: return self._fallback_response(texto, history)
        
        import time
        from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InvalidArgument

        # --- [STOP-GATE LOGIC] ---
        moto_confirmada = prospect_data.get("moto_confirmada") is True if prospect_data else False
        allowed_tools = ["search_catalog", "trigger_human_handoff"]
        if moto_confirmada:
            allowed_tools.append("calculate_credit_score")
        
        # Este es el candado dinámico que fallaba en send_message
        config_stop_gate = ToolConfig(
            function_calling_config=ToolConfig.FunctionCallingConfig(
                mode=ToolConfig.FunctionCallingConfig.Mode.ANY,
                allowed_function_names=allowed_tools
            )
        )

        phase = self._determine_funnel_phase(prospect_data)
        funnel_instruction = f"[FASE: {phase}] Prioriza confirmar el interés antes de pedir más datos."

        for attempt in range(3):
            try:
                # Construimos el Prompt XML
                user_name = prospect_data.get("name") or prospect_data.get("nombre") or "prospecto"
                full_prompt = f"{self._get_current_instruction()}\n\nNombre Usuario: {user_name}\nContexto: {context}\nFase: {phase}\nUsuario: {texto}\nJuan Pablo:"

                # Preparamos el historial en formato Content para generate_content
                contents = []
                for msg in history[-6:]: # Tomamos los últimos 6 mensajes para contexto
                    role = "user" if msg['role'] == 'user' else "model"
                    contents.append(Content(role=role, parts=[Part.from_text(str(msg.get('content', '')))]))
                
                # Añadimos el mensaje actual con el prompt enriquecido
                contents.append(Content(role="user", parts=[Part.from_text(full_prompt)]))

                # --- LLAMADA CORREGIDA (Opción B) ---
                response = self._model.generate_content(
                    contents=contents,
                    generation_config=GenerationConfig(temperature=0.2),
                    tool_config=config_stop_gate # Aquí ya no da error
                )

                # --- BUCLE DE HERRAMIENTAS ---
                turns = 0
                while turns < 3:
                    if not response.candidates: break
                    
                    candidate = response.candidates[0]
                    function_calls = [p.function_call for p in candidate.content.parts if p.function_call]
                    
                    if not function_calls:
                        return response.text.strip() if response.text else self._fallback_response(texto, history)

                    # Si hay llamadas, las procesamos y respondemos al modelo
                    contents.append(candidate.content) # Añadimos la intención del modelo
                    response_parts = []

                    for fc in function_calls:
                        if fc.name == "trigger_human_handoff": return "HANDOFF_TRIGGERED:user_request"
                        
                        # Ejecución de catálogo
                        if fc.name == "search_catalog":
                            q = fc.args.get("query", texto)
                            res = "No encontré resultados."
                            if self.catalog_service:
                                matches = self.catalog_service.search_items(q)
                                if matches:
                                    res = f"Encontré: {matches[0]['name']} a {matches[0]['formatted_price']}. URL: {matches[0].get('image_url','')}"
                            
                            response_parts.append(Part.from_function_response(name=fc.name, response={"content": res}))

                    # Enviamos los resultados de las herramientas de vuelta
                    contents.append(Content(role="user", parts=response_parts))
                    response = self._model.generate_content(contents=contents, tool_config=config_stop_gate)
                    turns += 1

            except (ResourceExhausted, ServiceUnavailable):
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"❌ Error en Hotfix #121: {e}")
                break
        
        return self._fallback_response(texto, history)

    def _fallback_response(self, texto: str, history: list = []) -> str:
        return "¡Qué pena! Se me quedó colgado el sistema del concesionario un segundo y no me cargó tu mensaje. 😅 ¿Me lo repites para seguir ayudándote?"