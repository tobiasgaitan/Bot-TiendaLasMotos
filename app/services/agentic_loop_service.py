import os
import re
import json
import subprocess
import logging
import asyncio
from typing import Dict, Any, Optional

from app.services.credit_faq_taxonomy import is_abstract_credit_faq

logger = logging.getLogger("agentic_loop")

TECH_SPEC_TOKENS = {
    "ficha", "tecnica", "técnica", "especificaciones", "caracteristicas",
    "características", "cilindraje", "torque", "motor", "potencia",
    "frenos", "cc", "hp", "nm", "transmision", "transmisión", "peso",
    # [BOT-BUILD-BUGFIX-MULTIMODAL-CAPTION-01] Léxico técnico coloquial (dominio CO).
    # Todos > 3 chars ⇒ el matcher de subcadena gobierna; el guard de tokens cortos
    # con \b queda intacto (test_is_tech_spec_query_no_false_positive_short_tokens).
    # Degradación benigna documentada: un falso positivo solo AÑADE la ficha a una
    # respuesta que ya presenta una moto; jamás silencia información.
    "cambios", "velocidad", "marchas", "encendido", "arranque",
    "inyeccion", "inyección", "carburador", "alimentacion", "alimentación",
    "tablero", "suspension", "suspensión", "tanque", "freno",
    "chasis", "llanta", "consumo"
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

    def run_checker(self, bot_response: str, is_catalog_query: bool = False, prospect_data: Dict[str, Any] = None, user_prompt: str = None, trace_id: Optional[str] = None) -> Dict[str, Any]:
        def _raw_purchase_intent(text: str) -> bool:
            if not text:
                return False
            return bool(re.search(
                r"\b(quisiera|quiero|busco|buscar|comprar|compro|adquirir|ver|una moto|motos|"
                r"doble prop[oó]sito|enduro|trocha|campo|deportiva|scooter|moped|autom[aá]tica|"
                r"se[ñn]oritera|calle|trabajo|cu[aá]l moto|estoy interesad[oa]|"
                r"me interesa|me gustar[íi]a)\b",
                text.lower(),
            ))

        has_price = bool(re.search(r"\$\d+", bot_response))
        has_image = bool(re.search(r"!\[.*?\]\(.*?\)|\[IMAGE:.*?\]", bot_response))

        has_moto_interest = bool(prospect_data and prospect_data.get("moto_interest"))

        # Detección semántica de intenciones de FAQ puras
        # [BOT-BUILD-REGRESSION-TRIAGE-COMPETENCIA-CUOTA-203]
        # SSOT: la clasificación de FAQ crediticia abstracta se evalúa ANTES y
        # de forma INDEPENDIENTE de las palabras clave genéricas de FAQ. Esto
        # evita que un token como "datacredito" o "reportado" quede atrapado
        # dentro del anidamiento `if is_faq_intent:` y nunca active el bypass.
        is_credit_faq_abstract = is_abstract_credit_faq(user_prompt)

        # [BOT-BUILD-DRIFT-CANON-016-C] Intención de compra: señales léxicas explícitas,
        # pero anuladas cuando el usuario está haciendo una FAQ crediticia abstracta
        # (preserva PINs 1588-1696: "quiero saber requisitos" no es compra).
        raw_purchase = _raw_purchase_intent(user_prompt or "")
        is_purchase_intent = raw_purchase and not is_credit_faq_abstract

        is_catalog_query_effective = (
            is_catalog_query
            or is_tech_spec_query(user_prompt or "")
            or is_purchase_intent
        )

        has_ficha = "Ficha Tecnica:" in bot_response if is_catalog_query_effective else True

        is_faq_intent = False
        if user_prompt:
            faq_keywords = [
                "horario", "direccion", "dirección", "ubicacion", "ubicación", "donde estan", "dónde están",
                "donde queda", "dónde queda", "taller", "mantenimiento", "requisitos", "papeles",
                "contacto", "telefono", "teléfono", "pagina", "página", "web", "correo", "email",
                "habeas", "politica", "política", "privacidad", "datos", "legal", "quienes somos",
                "quiénes somos", "nosotros", "pago", "pagar", "efectivo", "tarjeta", "transferencia",
                "nequi", "daviplata", "financiacion", "financiación", "interes", "interés", "banco",
                "cuota", "inicial", "credito", "crédito", "financiar", "mensualidad", "papeles",
                "requisitos", "fiador", "fiadores", "aval", "avales",
                "asesor", "humano", "ayuda", "soporte", "faq", "pregunta", "duda"
            ]
            prompt_lower = user_prompt.lower()
            generic_faq_match = any(
                re.search(rf"\b{kw}\b" if kw.isalnum() else re.escape(kw), prompt_lower)
                for kw in faq_keywords
            )
            is_faq_intent = generic_faq_match or is_credit_faq_abstract

        bypass_strict = (
            (not is_catalog_query_effective)
            or is_credit_faq_abstract
            or (is_faq_intent and not has_moto_interest)
        ) and not is_purchase_intent

        # [BOT-BUILD-BUFFER-PCC-076 / Fix B] PHASE_2_HABEAS_DATA post-habeas con
        # identidad pendiente: la instruccion de fase prohibe explicitamente
        # incluir precios ($) e imagenes (![]). El validador PCC estricto
        # ($ + imagen + Ficha) es incompatible con ese contrato, asi que se
        # fuerza bypass, pero SOLO cuando la respuesta es una pregunta legitima
        # de recoleccion de identidad (evita dejar pasar respuestas con oferta).
        pd = prospect_data or {}
        identity_pending_post_habeas = (
            pd.get("habeas_data_accepted") is True
            and (
                not (pd.get("nombre") or "").strip()
                or not (pd.get("ciudad") or "").strip()
            )
        )

        def _is_identity_collection_prompt(response: str) -> bool:
            if not response or "?" not in response:
                return False
            lowered = response.lower()
            if not (pd.get("ciudad") or "").strip() and any(
                kw in lowered for kw in ("ciudad", "donde", "ubicado", "vives", "escribes", "ubicacion", "ubicación")
            ):
                return True
            if not (pd.get("nombre") or "").strip() and any(
                kw in lowered for kw in ("nombre", "llamas", "como te llamas", "tu nombre")
            ):
                return True
            return False

        if identity_pending_post_habeas and _is_identity_collection_prompt(bot_response):
            return {"success": True, "bypass_strict": True, "report": {}}

        phone = (prospect_data or {}).get("phone") or "unknown"
        logger.info(
            f"🔍 [PCC-FORENSIC] turn_id={trace_id!r} phone={phone} "
            f"has_price={has_price} has_image={has_image} has_ficha={has_ficha} "
            f"bypass_strict={bypass_strict} is_catalog_query_effective={is_catalog_query_effective} "
            f"is_purchase_intent={is_purchase_intent} raw_purchase={raw_purchase} "
            f"response_len={len(bot_response) if bot_response else 0}"
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

