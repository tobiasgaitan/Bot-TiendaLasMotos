"""
Cerebro IA - AI Brain Service (v2.8 - Hotfix 128)
Estado: GEMINI 2.5 FLASH + DYNAMIC TOOL FILTERING (Blindado contra Error 400)
"""

import logging
import os
import time
import json
import re
from typing import Optional, Dict, Any
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable, InvalidArgument

logger = logging.getLogger(__name__)

try:
    import vertexai
    from vertexai.generative_models import (
        GenerativeModel, Tool, FunctionDeclaration, Content, Part, GenerationConfig, ToolConfig
    )
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False

class CerebroIA:
    def __init__(self, config_loader=None, catalog_service=None):
        self.config_loader = config_loader
        self.catalog_service = catalog_service
        self.motor_financiero = None 
        self._model = None
        # Definimos las declaraciones de funciones por separado para usarlas dinámicamente
        self.declarations = self._get_function_declarations()
        
        if VERTEX_AI_AVAILABLE:
            try:
                vertexai.init(project="tiendalasmotos", location="us-central1")
                # Inicializamos el modelo base (se actualizará en cada llamada)
                self._model_name = "gemini-2.5-flash"
                logger.info(f"🧠 CerebroIA: Motor {self._model_name} configurado para 2026")
            except Exception as e:
                logger.error(f"❌ Error Init: {str(e)}")

    def _get_function_declarations(self) -> Dict[str, FunctionDeclaration]:
        """Define todas las herramientas disponibles en el sistema."""
        return {
            "trigger_human_handoff": FunctionDeclaration(
                name="trigger_human_handoff", 
                description="Escala a humano si el usuario lo pide explícitamente.",
                parameters={"type": "object", "properties": {"reason": {"type": "string", "enum": ["user_explicit_request"]}}}
            ),
            "search_catalog": FunctionDeclaration(
                name="search_catalog", 
                description="Busca motos en el catálogo de Auteco Las Motos.",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
            ),
            "calculate_credit_score": FunctionDeclaration(
                name="calculate_credit_score", 
                description="Inicia el estudio de crédito financiero.",
                parameters={"type": "object", "properties": {"ocupacion": {"type": "string"}}, "required": ["ocupacion"]}
            )
        }

    def _get_current_instruction(self) -> str:
        if self.config_loader:
            try:
                p = self.config_loader.get_juan_pablo_personality()
                return p.get("system_instruction", "")
            except: pass
        from app.core.prompts import JUAN_PABLO_SYSTEM_INSTRUCTION
        return JUAN_PABLO_SYSTEM_INSTRUCTION

    def pensar_respuesta(self, texto: str, context: str = "", prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        resp = self._generate_with_retry(texto, context, prospect_data, history, skip_greeting)
        if resp and not resp.startswith("HANDOFF_TRIGGERED:"):
             return self.clean_parrot_phrases(resp)
        return resp

    @staticmethod
    def clean_parrot_phrases(text: str) -> str:
        f = [r"¡?Claro que sí!?", r"Claro,", r"¡?Excelente!?", r"¡?Perfecto!?", r"¡?Entendido!?"]
        c = text
        for p in f: c = re.sub(r"^\s*" + p + r"[\s,.]*", "", c, flags=re.IGNORECASE).strip()
        if c and c[0].islower(): c = c[0].upper() + c[1:]
        return c

    def _generate_with_retry(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        if not VERTEX_AI_AVAILABLE: return self._fallback_response(texto)
        
        # --- STOP-GATE DINÁMICO (LA SOLUCIÓN AL ERROR 400) ---
        # En lugar de usar allowed_function_names, filtramos qué funciones le enviamos al modelo
        moto_ok = prospect_data.get("moto_confirmada") is True if prospect_data else False
        
        active_declarations = [self.declarations["search_catalog"], self.declarations["trigger_human_handoff"]]
        if moto_ok:
            active_declarations.append(self.declarations["calculate_credit_score"])
        
        # Creamos el objeto Tool solo con las funciones permitidas
        dynamic_tool = Tool(function_declarations=active_declarations)
        
        # Mode.AUTO ahora funcionará porque NO le pasamos allowed_function_names
        t_conf = ToolConfig(function_calling_config=ToolConfig.FunctionCallingConfig(
            mode=ToolConfig.FunctionCallingConfig.Mode.AUTO
        ))

        instr = self._get_current_instruction()
        prompt = f"{instr}\n\nContexto: {context}\nUsuario: {texto}\nJuan Pablo:"

        # Re-inicializamos el modelo para este request con las herramientas filtradas
        model = GenerativeModel(self._model_name, tools=[dynamic_tool])

        for att in range(3):
            try:
                contents = []
                for m in history[-6:]:
                    role = "user" if m['role'] == 'user' else "model"
                    contents.append(Content(role=role, parts=[Part.from_text(str(m.get('content', '')))]))
                contents.append(Content(role="user", parts=[Part.from_text(prompt)]))

                res = model.generate_content(
                    contents=contents, 
                    generation_config=GenerationConfig(temperature=0.2), 
                    tool_config=t_conf
                )

                for _ in range(5):
                    if not res.candidates: break
                    can = res.candidates[0]
                    calls = [p.function_call for p in can.content.parts if p.function_call]
                    
                    if not calls: 
                        if res.text: return res.text.strip()
                        break

                    contents.append(can.content)
                    r_parts = []
                    for fc in calls:
                        if fc.name == "trigger_human_handoff": return "HANDOFF_TRIGGERED:user_request"
                        if fc.name == "search_catalog":
                            q = fc.args.get("query", texto)
                            items = self.catalog_service.search_items(q) if self.catalog_service else []
                            txt = f"RESULTADOS: Encontré la {items[0]['name']} a {items[0]['formatted_price']}." if items else "No hay stock."
                            r_parts.append(Part.from_function_response(name=fc.name, response={"content": txt}))
                    
                    contents.append(Content(role="user", parts=r_parts))
                    res = model.generate_content(contents=contents, tool_config=t_conf)
                
                if res.text: return res.text.strip()

            except Exception as e:
                logger.error(f"❌ Error en Hotfix 128: {e}")
                time.sleep(1)
        return self._fallback_response(texto)

    def generate_summary(self, conversation_text: str, **kwargs) -> Dict[str, Any]:
        if not VERTEX_AI_AVAILABLE: return {"summary": "", "extracted": {}}
        try:
            model = GenerativeModel(self._model_name)
            res = model.generate_content(f"Extrae JSON de: {conversation_text}", generation_config=GenerationConfig(response_mime_type="application/json"))
            return json.loads(res.text)
        except: return {"summary": "Charla activa", "extracted": {}}

    def _fallback_response(self, texto: str, history: list = []) -> str:
        return "¡Qué pena! Se me cruzaron los cables un segundo. 😅 ¿Me repites lo último?"