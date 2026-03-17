"""
Cerebro IA - AI Brain Service (v2.7 - Hotfix 127)
Estado: GEMINI 2.5 FLASH + STOP-GATE AUTO-MODE
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
        self.tools = self._create_tools()
        
        if VERTEX_AI_AVAILABLE:
            try:
                vertexai.init(project="tiendalasmotos", location="us-central1")
                # Confirmado: Gemini 2.5 Flash es el modelo vigente según tu documentación
                self._model = GenerativeModel(
                    "gemini-2.5-flash", 
                    tools=[self.tools] if self.tools else []
                )
                logger.info("🧠 CerebroIA: Motor Gemini 2.5 Flash Online")
            except Exception as e:
                logger.error(f"❌ Error Init: {str(e)}")
                self._model = None

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

    def _create_tools(self) -> Optional[Tool]:
        if not VERTEX_AI_AVAILABLE: return None
        try:
            h = FunctionDeclaration(name="trigger_human_handoff", description="Escala a humano", parameters={"type": "object", "properties": {"reason": {"type": "string", "enum": ["user_explicit_request"]}}})
            cat = FunctionDeclaration(name="search_catalog", description="Busca motos en el catálogo de Auteco", parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]})
            cred = FunctionDeclaration(name="calculate_credit_score", description="Inicia estudio de crédito financiero", parameters={"type": "object", "properties": {"ocupacion": {"type": "string"}}, "required": ["ocupacion"]})
            return Tool(function_declarations=[h, cat, cred])
        except: return None

    def _generate_with_retry(self, texto: str, context: str, prospect_data: Optional[Dict[str, Any]] = None, history: list = [], skip_greeting: bool = False) -> str:
        if not self._model: return self._fallback_response(texto)
        
        # STOP-GATE DINÁMICO
        moto_ok = prospect_data.get("moto_confirmada") is True if prospect_data else False
        allowed = ["search_catalog", "trigger_human_handoff"]
        if moto_ok: allowed.append("calculate_credit_score")
        
        # CAMBIO VITAL: Mode.AUTO permite que la IA responda texto cuando ya terminó de usar herramientas
        t_conf = ToolConfig(function_calling_config=ToolConfig.FunctionCallingConfig(
            mode=ToolConfig.FunctionCallingConfig.Mode.AUTO, 
            allowed_function_names=allowed
        ))

        instr = self._get_current_instruction()
        prompt = f"{instr}\n\nContexto: {context}\nUsuario: {texto}\nJuan Pablo:"

        for att in range(3):
            try:
                contents = []
                for m in history[-6:]:
                    role = "user" if m['role'] == 'user' else "model"
                    contents.append(Content(role=role, parts=[Part.from_text(str(m.get('content', '')))]))
                contents.append(Content(role="user", parts=[Part.from_text(prompt)]))

                res = self._model.generate_content(contents=contents, generation_config=GenerationConfig(temperature=0.2), tool_config=t_conf)

                # Bucle de herramientas aumentado a 5 turnos para mayor fluidez
                for _ in range(5):
                    if not res.candidates: break
                    can = res.candidates[0]
                    calls = [p.function_call for p in can.content.parts if p.function_call]
                    
                    # Si ya no hay más llamadas, devolvemos el texto final
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
                            # Respuesta más rica para que la IA no repita la búsqueda
                            if items:
                                txt = f"RESULTADOS CATÁLOGO: Encontré la {items[0]['name']} a {items[0]['formatted_price']}. Imagen: {items[0].get('image_url', 'N/A')}. Ficha: {items[0].get('specs', 'N/A')}"
                            else:
                                txt = "No encontré ese modelo exacto en el inventario actual."
                            r_parts.append(Part.from_function_response(name=fc.name, response={"content": txt}))
                    
                    contents.append(Content(role="user", parts=r_parts))
                    res = self._model.generate_content(contents=contents, tool_config=t_conf)
                
                # Si salimos del bucle y tenemos texto, lo enviamos
                if res.text: return res.text.strip()

            except Exception as e:
                logger.error(f"❌ Error en Hotfix 127: {e}")
                time.sleep(1)
        return self._fallback_response(texto)

    def generate_summary(self, conversation_text: str, **kwargs) -> Dict[str, Any]:
        """Resumen blindado contra argumentos extra"""
        if not self._model: return {"summary": "", "extracted": {}}
        try:
            res = self._model.generate_content(f"Resume y genera JSON: {conversation_text}", generation_config=GenerationConfig(response_mime_type="application/json"))
            return json.loads(res.text)
        except: return {"summary": "Charla en curso", "extracted": {}}

    def _fallback_response(self, texto: str, history: list = []) -> str:
        return "¡Qué pena! Se me cruzaron los cables un segundo. 😅 ¿Me repites lo último para asesorarte bien?"