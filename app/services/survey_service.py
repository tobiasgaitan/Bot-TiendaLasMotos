"""
Survey Service
Handles the financial survey flow with "Smart Retry" logic (2-Strike Rule).
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.services.finance import MotorFinanciero
from app.services.financial_service import financial_service

logger = logging.getLogger(__name__)

class SurveyService:
    """
    Manages the state machine for the financial survey.
    
    Features:
    - Immediate Exit: 'asesor', 'ayuda' triggers immediate handoff.
    - Smart Retry (2-Strikes):
        - Strike 1: Ask for clarification.
        - Strike 2: Auto-handoff to human.
    """

    HANDOFF_KEYWORDS = [
        "asesor", "humano", "persona", "alguien real", "jefe", "gerente", 
        "reclamo", "queja", "ayuda", "no entiendo"
    ]

    STRIKE_1_MSG = (
        "Disculpa, no entendí bien tu respuesta en este contexto. 🤔 "
        "¿Podrías explicármelo de otra forma o elegir una de las opciones?"
    )

    STRIKE_2_MSG = (
        "HANDOFF_TRIGGERED:Veo que no nos estamos entendiendo y no quiero hacerte perder tiempo. 😅 "
        "Voy a pedirle ayuda a un compañero del equipo para que revise tu caso. 🙋‍♂️ Dame un momento."
    )

    def __init__(self):
        self.financial_service = financial_service

    async def handle_survey_step(
        self,
        db_client: Any,
        phone: str,
        message_text: str,
        current_session: Dict[str, Any],
        motor_finanzas: MotorFinanciero,
    ) -> str:
        """
        Process a survey step with validations and retry logic.
        
        Returns:
            str: Response message to user. If it starts with "HANDOFF_TRIGGERED:", 
                 the caller should initiate human handoff.
        """
        status = current_session.get("status", "IDLE")
        answers = current_session.get("answers", {})
        retry_count = current_session.get("retry_count", 0)
        text_lower = message_text.lower()

        # 1. IMMEDIATE EXIT CHECK
        if any(k in text_lower for k in self.HANDOFF_KEYWORDS):
            logger.info(f"🚨 Survey Immediate Exit triggered by '{message_text}'")
            return f"HANDOFF_TRIGGERED:User requested help inside survey ('{message_text}')"

        # 2. VALIDATION & LOGIC PER STEP
        next_status = None
        response_text = ""
        is_valid = False

        if status == "SURVEY_STEP_1_LABOR":
            # Validation: Just needs to be non-empty text
            if len(message_text.strip()) > 1:
                is_valid = True
                answers["labor_type"] = message_text
                next_status = "SURVEY_STEP_2_INCOME"
                response_text = (
                    "2️⃣ ¿Cuáles son tus ingresos mensuales totales? "
                    "(Escribe solo el número, sin puntos. Ej: 1500000)"
                )
        
        elif status == "SURVEY_STEP_2_INCOME":
            # Validation: Must extract digits
            clean_income = "".join(filter(str.isdigit, message_text))
            if clean_income and len(clean_income) > 4: # At least 5 digits (10,000)
                is_valid = True
                answers["income"] = int(clean_income)
                next_status = "SURVEY_STEP_3_HISTORY"
                response_text = (
                    "3️⃣ ¿Cómo ha sido tu comportamiento con créditos anteriores? "
                    "(Ej: Excelente, Reportado, Nunca he tenido)"
                )
            else:
                is_valid = False # Input didn't look like money

        elif status == "SURVEY_STEP_3_HISTORY":
            # Validation: Non-empty
            if len(message_text.strip()) > 1:
                is_valid = True
                answers["credit_history"] = message_text
                answers["payment_habit"] = message_text # Dual purpose
                next_status = "SURVEY_STEP_4_GAS"
                response_text = "4️⃣ ¿Tienes servicio de Gas Natural a tu nombre? (Responde Sí o No)"

        elif status == "SURVEY_STEP_4_GAS":
            # Validation: Boolean-ish
            if self._is_boolean_answer(text_lower):
                is_valid = True
                has_gas = self._parse_boolean(text_lower)
                answers["has_gas_natural"] = has_gas
                next_status = "SURVEY_STEP_5_POSTPAID"
                response_text = "5️⃣ ¿Tienes un plan de celular Postpago? (Responde Sí o No)"
            else:
                is_valid = False

        elif status == "SURVEY_STEP_5_POSTPAID":
            # Validation: Boolean-ish
            if self._is_boolean_answer(text_lower):
                is_valid = True
                is_postpaid = self._parse_boolean(text_lower)
                answers["phone_plan"] = "Postpago" if is_postpaid else "Prepago"
                
                # --- FINALIZE ---
                return await self._finalize_survey(db_client, phone, answers)
            else:
                is_valid = False

        # 3. HANDLE VALIDATION RESULT
        if is_valid:
            # Success: Reset count, advance step
            await self._update_session(db_client, phone, {
                "status": next_status,
                "answers": answers,
                "retry_count": 0 # Reset!
            })
            return response_text
        else:
            # Failure: Smart Retry Logic
            if retry_count == 0:
                # Strike 1
                logger.info(f"⚠️ Survey Strike 1 for {phone} at {status}")
                await self._update_session(db_client, phone, {"retry_count": 1})
                return self.STRIKE_1_MSG
            else:
                # Strike 2 (>= 1)
                logger.warning(f"🚨 Survey Strike 2 for {phone} at {status} -> Handoff")
                # Reset session so they aren't stuck in survey for the human
                await self._update_session(db_client, phone, {
                    "status": "PAUSED", # Or IDLE, but PAUSED blocks bot
                    "retry_count": 0
                })
                # The caller (router) will handle the "HANDOFF_TRIGGERED:" prefix
                return self.STRIKE_2_MSG

    async def _finalize_survey(self, db_client, phone, answers):
        """Calculate score and return final strategy."""
        profile = {
            "labor_type": answers.get("labor_type"),
            "income": answers.get("income"),
            "payment_habit": answers.get("payment_habit"),
            "credit_history": answers.get("credit_history"),
            "has_gas_natural": answers.get("has_gas_natural"),
            "phone_plan": answers.get("phone_plan")
        }
        
        try:
            decision = self.financial_service.evaluate_profile(profile)
            strategy = decision["strategy"]
            action = decision["action_type"]
            payload = decision["payload"]
        except Exception as e:
            logger.error(f"❌ Error evaluating profile: {e}")
            return "HANDOFF_TRIGGERED:Error calculating score"

        # Clear session
        await self._update_session(db_client, phone, {
            "status": "IDLE", 
            "answers": {},
            "retry_count": 0
        })

        if action == "REDIRECT":
            entity_name = "Banco de Bogotá" if strategy == "BANCO" else "CrediOrbe"
            return (
                f"¡Listo! Según tu perfil, tu mejor opción es con **{entity_name}**.\n\n"
                f"Dale clic aquí para la aprobación inmediata: {payload}"
            )
        elif action == "CAPTURE_DATA":
             return (
                "¡Te tengo buenas noticias! Podemos intentarlo por el cupo **Brilla**.\n\n"
                "Por favor envíame una foto de tu **recibo de gas** y tu **cédula** para avanzar."
            )
        else:
            # Human fallback
            return (
                "Tu caso es especial. Te voy a pasar con un asesor humano para que lo revise personalmente."
            )

    async def _update_session(self, db_client, phone, data):
        """Helper to update Firestore session."""
        try:
            doc_ref = (
                db_client.collection("mensajeria")
                .document("whatsapp")
                .collection("sesiones")
                .document(phone)
            )
            data["last_interaction"] = datetime.now(timezone.utc)
            doc_ref.set(data, merge=True)
        except Exception as e:
            logger.error(f"Error updating session: {e}")

    def _is_boolean_answer(self, text: str) -> bool:
        """Check if text looks like a boolean answer."""
        valid_words = ["si", "sí", "no", "yes", "claro", "obvio", "tengo", "nunca", "jamasser"] # added robust list
        return any(w in text for w in valid_words)

    def _parse_boolean(self, text: str) -> bool:
        """Parse text to boolean."""
        positives = ["si", "sí", "yes", "claro", "obvio", "tengo"]
        return any(w in text for w in positives)

# Singleton instance
survey_service = SurveyService()
