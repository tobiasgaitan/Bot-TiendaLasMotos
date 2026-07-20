import os
import re
import json
import subprocess
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger("agentic_loop")

TECH_SPEC_TOKENS = {
    "ficha", "tecnica", "técnica", "especificaciones", "caracteristicas",
    "características", "cilindraje", "torque", "motor", "potencia",
    "frenos", "cc", "hp", "nm", "transmision", "transmisión", "peso"
}


def is_tech_spec_query(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    for token in TECH_SPEC_TOKENS:
        if len(token) <= 3:
            if re.search(r'\b' + re.escape(token) + r'\b', text_lower):
                return True
        else:
            if token in text_lower:
                return True
    return False


class AgenticOrchestrator:
    def __init__(self, sandbox_path: str = "./tmp/sandbox-106", max_attempts: int = 5):
        self.sandbox_path = sandbox_path
        self.max_attempts = max_attempts
        self.error_schema_keys = [
            "scenario_key", "input_stimulus", "expected_behavior", 
            "output_obtained", "broken_guardrail", "code_context"
        ]

    async def create_sandbox(self, branch_name: str) -> bool:
        try:
            # cmd split: git worktree add -b {branch_name} {self.sandbox_path} main
            proc = await asyncio.create_subprocess_exec(
                "git", "worktree", "add", "-b", branch_name, self.sandbox_path, "main",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(
                    returncode=proc.returncode,
                    cmd=["git", "worktree", "add", "-b", branch_name, self.sandbox_path, "main"],
                    output=stdout.decode("utf-8", errors="ignore"),
                    stderr=stderr.decode("utf-8", errors="ignore")
                )
            logger.info(f"Worktree creado exitosamente: {stdout.decode('utf-8', errors='ignore').strip()}")
            return True
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.strip() if isinstance(e.stderr, str) else (e.stderr.decode("utf-8", errors="ignore").strip() if e.stderr else "")
            logger.exception(f"Error forense al crear Git Worktree: {err_msg}")
            raise e

    def run_checker(self, bot_response: str, is_catalog_query: bool = False, prospect_data: Dict[str, Any] = None, user_prompt: str = None) -> Dict[str, Any]:
        has_price = bool(re.search(r"\$\d+", bot_response))
        has_image = bool(re.search(r"!\[.*?\]\(.*?\)|\[IMAGE:.*?\]", bot_response))

        has_moto_interest = bool(prospect_data and prospect_data.get("moto_interest"))
        
        is_catalog_query_effective = (
            is_catalog_query
            or is_tech_spec_query(user_prompt or "")
        )
        
        has_ficha = "Ficha Tecnica:" in bot_response if is_catalog_query_effective else True

        # Detección semántica de intenciones de FAQ puras
        is_faq_intent = False
        is_credit_faq_abstract = False
        if user_prompt:
            faq_keywords = [
                "horario", "direccion", "dirección", "ubicacion", "ubicación", "donde estan", "dónde están",
                "donde queda", "dónde queda", "taller", "mantenimiento", "requisitos", "papeles",
                "contacto", "telefono", "teléfono", "pagina", "página", "web", "correo", "email",
                "habeas", "politica", "política", "privacidad", "datos", "legal", "quienes somos",
                "quiénes somos", "nosotros", "pago", "pagar", "efectivo", "tarjeta", "transferencia",
                "nequi", "daviplata", "financiacion", "financiación", "interes", "interés", "banco",
                "cuota", "inicial", "credito", "crédito", "financiar", "mensualidad", "papeles",
                "requisitos", "asesor", "humano", "ayuda", "soporte", "faq", "pregunta", "duda"
            ]
            prompt_lower = user_prompt.lower()
            if any(re.search(rf"\b{kw}\b" if kw.isalnum() else re.escape(kw), prompt_lower) for kw in faq_keywords):
                is_faq_intent = True
            # [BOT-BUILD-REGRESSION-FINANCIAL-AND-FAQ-200]
            # Credit FAQ abstracta: requisitos/documentos SIN cuantia/simulacion.
            # Debe bypasear Visual-Lock incluso con moto_interest presente.
            if is_faq_intent:
                credit_faq_signals = ["requisitos", "papeles", "documentos", "codeudor",
                                      "que necesito", "qu\u00e9 necesito", "que piden", "qu\u00e9 piden",
                                      "que debo", "qu\u00e9 debo",
                                      "historial", "datacredito", "data credito", "reportado", "reporte",
                                      "experiencia crediticia", "necesito historial",
                                      "extranjero", "ppt", "pep", "pasaporte",
                                      "necesito para", "puedo sacar"]
                credit_sim_keywords = ["cuota", "cuanto", "cu\u00e1nto", "inicial de",
                                       "a 24", "a 36", "a 48", "a 12", "simul",
                                       "cuanto qued", "cu\u00e1nto qued"]
                has_credit_faq = any(s in prompt_lower for s in credit_faq_signals)
                has_credit_sim = any(s in prompt_lower for s in credit_sim_keywords)
                is_credit_faq_abstract = has_credit_faq and not has_credit_sim

        bypass_strict = (
            (not is_catalog_query_effective)
            or is_credit_faq_abstract
            or (is_faq_intent and not has_moto_interest)
        )
        
        if bypass_strict:
            # En bypass de FAQ abstracta sin moto de interés asignada,
            # no exigimos precio, imagen, ni tampoco el prefijo Ficha Tecnica.
            # EXPOSE bypass_strict=True para que ai_brain.py pueda forzar
            # is_catalog_query=False y cortar el retry loop sincrónicamente.
            return {"success": True, "bypass_strict": True, "report": {}}
        else:
            # [BOT-QA-HARDENING-126] Visual-Lock íntegro: si hay intención comercial activa (moto_interest),
            # el marcador 'Sin descripción' es un fallback vacío que viola las reglas de PCC Pro.
            # WHY: Si el LLM recibe "Ficha Tecnica: Sin descripción" con una moto de interés en CRM,
            # puede alucinizar especificaciones técnicas para "completar" la ficha, causando Catalog-Lock violation.
            # Con bypass (sin intención comercial), el fallback es aceptable para FAQ/generic queries.
            has_sin_descripcion_fallback = (
                has_moto_interest
                and "Ficha Tecnica: Sin descripción" in bot_response
            )
            if not (has_price and has_image and has_ficha) or has_sin_descripcion_fallback:
                report = {
                    "scenario_key": "CATALOG_VALIDATION_FAIL",
                    "input_stimulus": "Consulta de catálogo de motocicletas",
                    "expected_behavior": "Respuesta con precio ($), imagen Markdown y prefijo Ficha Tecnica:",
                    "output_obtained": bot_response if bot_response else "None / String Vacío",
                    "broken_guardrail": "PRICE_CONSISTENCY_CHECK",
                    "code_context": {
                        "target_file": "app/services/catalog_service.py",
                        "surrounding_code": "def search_items(): ...",
                        "logs_trace": (
                            "PCC Pro Validation Triggered: Visual-Lock SIN_DESCRIPCION_FALLBACK "
                            "[BOT-QA-HARDENING-126]"
                            if has_sin_descripcion_fallback
                            else "PCC Pro Validation Triggered: Assertion Error"
                        )
                    }
                }
                return {"success": False, "report": report}

        
        return {"success": True, "report": {}}

    async def destroy_sandbox(self, branch_name: str) -> None:
        try:
            if os.path.exists(self.sandbox_path):
                proc1 = await asyncio.create_subprocess_exec(
                    "git", "worktree", "remove", "--force", self.sandbox_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout1, stderr1 = await proc1.communicate()
                if proc1.returncode != 0:
                    logger.error(f"Fallo al remover worktree: {stderr1.decode('utf-8', errors='ignore').strip()}")

                proc2 = await asyncio.create_subprocess_exec(
                    "git", "branch", "-D", branch_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout2, stderr2 = await proc2.communicate()
                if proc2.returncode != 0:
                    logger.error(f"Fallo al remover rama: {stderr2.decode('utf-8', errors='ignore').strip()}")

                logger.info("Sandbox efímero destruido físicamente de forma limpia.")
        except Exception as e:
            logger.error(f"Fallo crítico en el proceso de limpieza forense: {e}")

if __name__ == "__main__":
    print("AgenticOrchestrator: CLI Ready")

