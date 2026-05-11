"""
Survey Service
Handles the financial survey flow with "Smart Retry" logic (2-Strike Rule).
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from google.cloud import firestore
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

        if status == "SURVEY_STEP_0_NAME":
            # Validation: Non-empty
            if len(message_text.strip()) > 1:
                name = message_text.strip()
                is_valid = True
                answers["nombre"] = name
                
                # Dynamic personalization
                title, first_name = self._get_name_title(name)
                
                next_status = "SURVEY_STEP_1_AUTH"
                response_text = (
                    f"Mucho gusto, {title} {first_name}. Para poder revisar tus opciones de financiamiento y continuar con la simulación, "
                    "¿autorizas el tratamiento de tus datos personales? Puedes consultar nuestra política en el enlace que te enviaré a continuación. (Responde Sí o No)"
                )

        elif status == "SURVEY_STEP_1_AUTH":
            # Validation: Boolean-ish
            if self._is_boolean_answer(text_lower):
                is_valid = True
                consent = self._parse_boolean(text_lower)
                if consent:
                    next_status = "SURVEY_STEP_2_CITY"
                    response_text = (
                        "¡Excelente! ¿En qué ciudad te encuentras ubicado?"
                    )
                else:
                    # Explicit Denial: Exit Survey & Purge
                    logger.info(f"🚫 User denied Habeas Data for {phone}. Exiting survey.")
                    await self._update_session(db_client, phone, {"status": "IDLE", "answers": {}, "retry_count": 0})
                    return (
                        "Entiendo perfectamente. Por políticas de seguridad y privacidad, "
                        "no podemos realizar el estudio de crédito sin tu autorización de datos. 🛡️\n\n"
                        "Si cambias de opinión, solo escribe **'crédito'** de nuevo. ¿En qué más te puedo ayudar?"
                    )
            else:
                is_valid = False

        elif status == "SURVEY_STEP_2_CITY":
            # Validation: Non-empty
            if len(message_text.strip()) > 1:
                is_valid = True
                answers["ciudad"] = message_text
                next_status = "SURVEY_STEP_3_LABOR"
                response_text = (
                    "3️⃣ Cuéntame: ¿Cuál es tu ocupación actual y qué tipo de contrato tienes? "
                    "(Ej: Empleado Indefinido, Independiente, etc.)"
                )

        elif status == "SURVEY_STEP_3_LABOR":
            # Validation: Just needs to be non-empty text
            if len(message_text.strip()) > 1:
                is_valid = True
                answers["labor_type"] = message_text
                next_status = "SURVEY_STEP_4_INCOME"
                response_text = (
                    "4️⃣ ¿Cuáles son tus ingresos mensuales totales? "
                    "(Escribe solo el número, sin puntos. Ej: 1500000)"
                )

        elif status == "SURVEY_STEP_4_INCOME":
            # Validation: Must extract digits
            clean_income = "".join(filter(str.isdigit, message_text))
            if clean_income and len(clean_income) > 4: # At least 5 digits (10,000)
                is_valid = True
                answers["income"] = int(clean_income)
                next_status = "SURVEY_STEP_5_HISTORY"
                response_text = (
                    "5️⃣ ¿Cómo ha sido tu comportamiento con créditos anteriores? "
                    "(Ej: Al día, Reportado, Nunca he tenido)"
                )
            else:
                is_valid = False # Input didn't look like money

        elif status == "SURVEY_STEP_5_HISTORY":
            # Validation: Non-empty
            if len(message_text.strip()) > 1:
                is_valid = True
                answers["credit_history"] = message_text
                answers["payment_habit"] = message_text # Dual purpose
                next_status = "SURVEY_STEP_6_GAS"
                response_text = "6️⃣ ¿Tienes servicio de Gas Natural a tu nombre? (Responde Sí o No)"

        elif status == "SURVEY_STEP_6_GAS":
            # Validation: Boolean-ish
            if self._is_boolean_answer(text_lower):
                is_valid = True
                has_gas = self._parse_boolean(text_lower)
                answers["has_gas_natural"] = has_gas
                next_status = "SURVEY_STEP_7_MOBILE"
                response_text = "7️⃣ ¿Tienes un plan de celular Postpago? (Responde Sí o No)"
            else:
                is_valid = False

        elif status == "SURVEY_STEP_7_MOBILE":
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
                
                if status == "SURVEY_STEP_0_NAME":
                    return (
                        "No pude procesar tu respuesta. 😅 ¿Podrías decirme tu **nombre completo** para empezar?"
                    )
                
                if status == "SURVEY_STEP_1_AUTH":
                    return (
                        "No pude procesar tu respuesta. 😅 "
                        "Para continuar, ¿autorizas el tratamiento de tus datos personales? "
                        "Puedes consultar nuestra política en el enlace que te enviaré a continuación. (Responde Sí o No)"
                    )
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

        # Update Prospect document with flags and new info
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone)
            prospect_ref = db_client.collection("prospectos").document(clean_phone)
            # Fetch current data to preserve other fields if set() is used, or just use update()
            prospect_ref.update({
                "nombre": answers.get("nombre", ""),
                "ciudad": answers.get("ciudad", ""),
                "chatbot_status": "survey_completed",
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(f"✅ Prospect {phone} updated with Name: {answers.get('nombre')} and City: {answers.get('ciudad')}")
        except Exception as e:
            logger.error(f"❌ Error updating prospect {phone} on survey finalization: {e}")

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

    async def delete_session(self, db_client, phone):
        """
        Nuclear wipe of sessions collection. 
        Searches by ID variants and by fields (celular, telefono).
        """
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone)
            
            # clear_survey_state() REMOVED (Sprint 1) — SurveyService methods are gone.
            # Survey state is no longer tracked in MemoryService.


            # 2. DELETE BY ID VARIANTS
            variants = list(set([phone, clean_phone, phone.replace("57", "", 1)]))
            for pid in variants:
                doc_ref = db_client.collection("mensajeria").document("whatsapp").collection("sesiones").document(pid)
                if doc_ref.get().exists:
                    # Recursive history wipe
                    hist = doc_ref.collection("historial").limit(50).stream()
                    for h in hist: h.reference.delete()
                    doc_ref.delete()
                    logger.info(f"🗑️ Deleted session by ID: {pid}")

            # 3. DELETE BY FIELD (The Ghost Hunter)
            # Query documents where 'celular' or 'telefono' matches ANY variant
            field_variants = list(set([phone, clean_phone, phone.replace("57", "", 1)]))
            for field in ["celular", "telefono"]:
                for val in field_variants:
                    docs = (
                        db_client.collection("mensajeria")
                        .document("whatsapp")
                        .collection("sesiones")
                        .where(field, "==", val)
                        .stream()
                    )
                    for doc in docs:
                        # Recursive history wipe for found docs
                        try:
                            hist = doc.reference.collection("historial").limit(50).stream()
                            for h in hist: h.reference.delete()
                        except: pass
                        doc.reference.delete()
                        logger.info(f"🗑️ Deleted session by FIELD {field}={val}: {doc.id}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error during absolute nuclear wipe for {phone}: {e}")
            return False

    async def _update_session(self, db_client, phone, data):

        """Helper to update Firestore session and prospect survey_state."""
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone)
            
            # 1. Update Session Document (Legacy/Router Sync)
            doc_ref = (
                db_client.collection("mensajeria")
                .document("whatsapp")
                .collection("sesiones")
                .document(clean_phone)
            )
            data["last_interaction"] = datetime.now(timezone.utc)
            doc_ref.set(data, merge=True)

            # Survey state sync REMOVED (Sprint 1) — save_survey_state/clear_survey_state
            # were deleted from MemoryService when SurveyService was removed.
            # The LLM now handles all Phase 3 state via Firestore prompt context.

        except Exception as e:
            logger.error(f"Error updating session/prospect state: {e}")

    def _is_boolean_answer(self, text: str) -> bool:
        """Check if text looks like a boolean answer."""
        valid_words = ["si", "sí", "no", "yes", "claro", "obvio", "tengo", "nunca", "jamasser"] # added robust list
        return any(w in text for w in valid_words)

    def _parse_boolean(self, text: str) -> bool:
        """Parse text to boolean."""
        positives = ["si", "sí", "yes", "claro", "obvio", "tengo"]
        return any(w in text for w in positives)

    def _get_name_title(self, full_name: str) -> tuple:
        """Determines title (Señor/Señora) and extracts first name."""
        first_name = full_name.split()[0] if full_name else ""
        if not first_name: return "Señor", ""
        
        # Simple heuristic: ends with 'a' -> Señora
        if first_name.lower().endswith('a'):
            return "Señora", first_name
        return "Señor", first_name

# Singleton instance
survey_service = SurveyService()
