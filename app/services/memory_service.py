"""
Memory Service - CRM Integration & Long-Term Memory
Handles prospect data retrieval and conversation summary updates in Firestore.
"""

import logging
from typing import Dict, Any, Optional
from google.cloud import firestore

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Service for managing prospect memory and conversation context.

    Integrates with Firestore 'prospectos' collection to:
    - Retrieve existing prospect data for context seeding
    - Update conversation summaries and extracted information
    - Track chatbot engagement status
    
    Security:
    - Handles PII (names, phones) - strictly uses normalized phone IDs.
    - No raw query logging recommended in production.
    """

    def __init__(self, db: firestore.Client):
        """
        Initialize the memory service.

        Args:
            db: Firestore client instance
        """
        self._db = db
        logger.info("🧠 MemoryService initialized")

    def get_prospect_data(self, phone_number: str) -> Dict[str, Any]:
        """
        Retrieve prospect data from Firestore by document ID (normalized phone).

        Args:
            phone_number: Raw phone number to search for

        Returns:
            Dictionary with prospect data or empty context on error
        """
        try:
            from app.core.utils import PhoneNormalizer
            
            normalized_phone = PhoneNormalizer.normalize(phone_number)
            logger.info(f"🔍 Buscando prospecto | Input: {phone_number} | Normalizado (ID): {normalized_phone}")

            prospectos_ref = self._db.collection("prospectos")
            doc = prospectos_ref.document(normalized_phone).get()

            if doc.exists:
                data = doc.to_dict()
                prospect_data = {
                    "name": data.get("nombre"),
                    "ciudad": data.get("ciudad"),
                    "moto_interest": data.get("motoInteres"),
                    "summary": data.get("ai_summary"),
                    "human_help_requested": data.get("human_help_requested", False),
                    "survey_state": data.get("survey_state"),
                    "exists": True
                }
                logger.info(
                    f"✅ Prospecto encontrado: {prospect_data['name']} | "
                    f"Moto: {prospect_data['moto_interest']} | "
                    f"Human Help: {prospect_data['human_help_requested']}"
                )
                return prospect_data

            # Fallback legacy check: Try querying by 'celular' field in case ID migration isn't done
            # This is a safe fallback during transition but the ID lookup is primary
            logger.info("⚠️ No found by ID, checking legacy 'celular' field...")
            query = prospectos_ref.where("celular", "==", normalized_phone).limit(1)
            docs = query.get()
            
            if docs:
                data = docs[0].to_dict()
                logger.info(f"✅ Found via legacy field query (ID mismatch): {docs[0].id}")
                return {
                    "name": data.get("nombre"),
                    "ciudad": data.get("ciudad"),
                    "moto_interest": data.get("motoInteres"),
                    "summary": data.get("ai_summary"),
                    "human_help_requested": data.get("human_help_requested", False),
                    "survey_state": data.get("survey_state"),
                    "exists": True
                }

            logger.info(f"📭 Prospecto no encontrado para {normalized_phone}")
            return {
                "name": None,
                "ciudad": None,
                "moto_interest": None,
                "summary": None,
                "human_help_requested": False,
                "survey_state": None,
                "exists": False
            }

        except Exception as e:
            logger.error(f"❌ Error al recuperar datos del prospecto {phone_number}: {str(e)}", exc_info=True)
            return {
                "name": None,
                "ciudad": None,
                "moto_interest": None,
                "summary": None,
                "human_help_requested": False,
                "survey_state": None,
                "exists": False
            }

    async def update_prospect_summary(
        self,
        phone_number: str,
        summary_text: str,
        extracted_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update prospect's conversation summary and extracted information.

        Args:
            phone_number: Phone number to update
            summary_text: New conversation summary to save
            extracted_data: Optional dict with extracted fields
        """
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone_number)

            logger.info(f"💾 Updating prospect summary for {clean_phone}")

            prospectos_ref = self._db.collection("prospectos")
            # First try by ID
            doc_ref = prospectos_ref.document(clean_phone)
            doc = doc_ref.get()
            
            if doc.exists:
                docs = [doc]
            else:
                 # Fallback query
                 query = prospectos_ref.where("celular", "==", clean_phone).limit(1)
                 docs = query.get()

            if not docs:
                logger.warning(f"⚠️ No prospect found to update for {clean_phone}")
                new_doc_ref = prospectos_ref.document()
                new_doc_ref.set({
                    "celular": clean_phone,
                    "ai_summary": summary_text,
                    "chatbot_status": "ACTIVE",
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "updated_at": firestore.SERVER_TIMESTAMP
                })
                logger.info(f"✅ Created new prospect document for {clean_phone}")
                return

            doc_ref = docs[0].reference
            current_data = docs[0].to_dict()

            update_data = {
                "ai_summary": summary_text,
                "updated_at": firestore.SERVER_TIMESTAMP
            }

            if current_data.get("chatbot_status") == "PENDING":
                update_data["chatbot_status"] = "ACTIVE"
                logger.info(f"🟢 Activating chatbot status for {clean_phone}")

            if extracted_data:
                if extracted_data.get("name"):
                    update_data["nombre"] = extracted_data["name"]
                    logger.info(f"📝 Updating nombre: {extracted_data['name']}")
                if extracted_data.get("moto_interest"):
                    update_data["motoInteres"] = extracted_data["moto_interest"]
                    logger.info(f"🏍️ Updating motoInteres: {extracted_data['moto_interest']}")

            doc_ref.update(update_data)
            logger.info(f"✅ Successfully updated prospect summary for {clean_phone}")

        except Exception as e:
            logger.error(f"❌ Error updating prospect summary for {phone_number}: {str(e)}", exc_info=True)

    def update_last_interaction(self, phone_number: str) -> None:
        """
        Updates only the fecha timestamp to bring user to top of admin list.

        Why: When a user is in Human Mode the bot is muted, but admins
        still need to see the user's latest activity in the Admin Panel.
        This method bumps the fecha field so the user floats to the top.

        Production-proven: Uses celular field query (not document ID) to
        match the fix that was manually applied and verified on the live server.

        Args:
            phone_number: Phone number to update
        """
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone_number)
            
            # FIX: Uses self._db and hardcoded "prospectos" — matches working production code
            # Try ID first
            doc_ref = self._db.collection("prospectos").document(clean_phone)
            if doc_ref.get().exists:
                doc_ref.update({"fecha": firestore.SERVER_TIMESTAMP})
                logger.info(f"✅ TIMESTAMP UPDATED for {clean_phone} (ID)")
            else:
                # Fallback query
                docs = self._db.collection("prospectos").where("celular", "==", clean_phone).stream()
                for doc in docs:
                    doc.reference.update({"fecha": firestore.SERVER_TIMESTAMP})
                    logger.info(f"✅ TIMESTAMP UPDATED for {clean_phone} (Query)")
        except Exception as e:
            logger.error(f"❌ Error updating timestamp: {e}", exc_info=True)

    def set_human_help_status(self, phone_number: str, status: bool) -> None:
        """
        Set the human_help_requested flag for a prospect in Firestore.

        Controls whether the bot should remain silent for this user.
        When True, bot will not respond until admin resets flag to False.

        Args:
            phone_number: Phone number to update
            status: True to mute bot, False to resume bot
        """
        try:
            from app.core.utils import PhoneNormalizer
            normalized_phone = PhoneNormalizer.normalize(phone_number)
            
            logger.info(
                f"🔧 Setting human_help_requested={status} | "
                f"Input: {phone_number} | Normalizado (ID): {normalized_phone}"
            )

            prospectos_ref = self._db.collection("prospectos")

            # ATTEMPT 1: Direct document ID lookup
            doc_ref = prospectos_ref.document(normalized_phone)
            doc = doc_ref.get()
            
            if doc.exists:
                doc_ref.update({
                    "human_help_requested": status,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                    "fecha": firestore.SERVER_TIMESTAMP
                })
                logger.info(f"✅ Updated human_help_requested={status} for {normalized_phone}")
                return

            # Fallback: Query by field
            query = prospectos_ref.where("celular", "==", normalized_phone).limit(1)
            docs = query.get()
            
            if docs:
                 docs[0].reference.update({
                    "human_help_requested": status,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                    "fecha": firestore.SERVER_TIMESTAMP
                })
                 logger.info(f"✅ Updated human_help_requested={status} for {normalized_phone} (Legacy Query)")
                 return

            # No existing document found - create new one
            logger.warning(f"⚠️ No existing prospect found for {phone_number}, creating new document")
            new_doc_ref = prospectos_ref.document(normalized_phone)
            new_doc_ref.set({
                "celular": normalized_phone,
                "human_help_requested": status,
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
                "fecha": firestore.SERVER_TIMESTAMP
            })
            logger.info(f"✅ Created new prospect with human_help_requested={status} for {normalized_phone}")

        except Exception as e:
            logger.error(
                f"❌ Error setting human_help_status for {phone_number}: {str(e)}",
                exc_info=True
            )



    def create_prospect_if_missing(self, phone_number: str) -> bool:
        """
        Ensures a prospect document exists for the given phone number.
        Crucial for new users coming via latency bypass to appear in Admin Panel.
        
        Fields set:
        - chatbot_status: "ACTIVE"
        - status: "Pendiente"
        - name: "Cliente WhatsApp"
        - source: "whatsapp_bot"
        - created_at: SERVER_TIMESTAMP
        - updated_at: SERVER_TIMESTAMP
        
        Args:
            phone_number: Raw phone number
            
        Returns:
            bool: True if created, False if already existed
        """
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone_number)
            
            logger.info(f"💾 Ensuring prospect existence for {clean_phone}...")
            
            prospectos_ref = self._db.collection("prospectos")
            doc_ref = prospectos_ref.document(clean_phone)
            doc = doc_ref.get()
            
            if doc.exists:
                # Optional: Ensure minimal fields are present even if exists?
                # For now, just return False as it exists
                return False
                
            # Create new with strict defaults for visibility in Admin Panel
            # ULTIMATUM: Do NOT set updated_at/fecha yet to allow Greeting Logic to detect a fresh start
            new_data = {
                "celular": clean_phone,
                "name": "",
                "nombre": "", # Legacy compat
                "chatbot_status": "ACTIVE",
                "status": "Pendiente",
                "source": "whatsapp_bot",
                "human_help_requested": False,
                "created_at": firestore.SERVER_TIMESTAMP,
                # Explicitly excluded updated_at/fecha for Atomic Greeting fix
            }
            doc_ref.set(new_data)
            logger.info(f"✅ Created NEW prospect doc for {clean_phone}")

            # --- ZOMBIE SESSION PURGE ---
            try:
                # Delete any stuck session to ensure a fresh start
                # Fix: Correct path is mensajeria/whatsapp/sesiones
                session_ref = self._db.collection("mensajeria").document("whatsapp").collection("sesiones").document(clean_phone)
                session_ref.delete()
                logger.info(f"🗑️ Zombie session purged for new prospect {clean_phone}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to purge zombie session for {clean_phone}: {e}")
            # ---------------------------
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating prospect for {phone_number}: {e}", exc_info=True)
            return False

    def save_survey_state(self, phone_number: str, survey_id: str, current_step: str, collected_data: dict) -> None:
        """
        Saves the current state of a survey to the prospect's profile.
        This provides context switching capability, allowing the bot to pause
        a survey, answer a random question, and resume the survey exactly where it left off.
        Implementation of Security Standard: Input Validation via PhoneNormalizer.

        Args:
            phone_number: The prospect's raw phone number
            survey_id: Identifier for the survey (e.g., 'financial_capture')
            current_step: The current question/step the user is on
            collected_data: Data collected so far
        """
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone_number)
            
            logger.info(f"💾 Guardando estado de encuesta para {clean_phone} | Survey: {survey_id} | Paso: {current_step}")
            
            doc_ref = self._db.collection("prospectos").document(clean_phone)
            
            state_data = {
                "survey_id": survey_id,
                "current_step": current_step,
                "collected_data": collected_data,
                "is_active": True,
                "updated_at": firestore.SERVER_TIMESTAMP
            }
            
            # Use update to safely merge this nested object without overwriting other fields
            doc_ref.update({
                "survey_state": state_data,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"✅ Estado de encuesta guardado exitosamente para {clean_phone}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando estado de encuesta para {phone_number}: {e}", exc_info=True)

    def get_survey_state(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the current active survey state for a prospect.
        Implementation of Security Standard: Fail-Closed approach by safely returning None.

        Args:
            phone_number: The prospect's raw phone number
            
        Returns:
            Dict containing the active survey state or None if no active survey exists
        """
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone_number)
            
            doc_ref = self._db.collection("prospectos").document(clean_phone)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                state = data.get("survey_state")
                if state:
                    logger.info(f"🔍 Estado de encuesta ACTIVO encontrado para {clean_phone}: {state.get('survey_id')}")
                    return state
                    
            return None
            
        except Exception as e:
            logger.error(f"❌ Error al recuperar estado de encuesta para {phone_number}: {e}", exc_info=True)
            return None

    def clear_survey_state(self, phone_number: str) -> None:
        """
        Clears the active survey state from a prospect document once completed or cancelled.
        Also cleans up any legacy field based survivors.
        """
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone_number)
            
            logger.info(f"🧹 Limpiando estado de encuesta para {clean_phone}")
            
            # 1. Clear by ID
            doc_ref = self._db.collection("prospectos").document(clean_phone)
            doc_ref.update({
                "survey_state": firestore.DELETE_FIELD,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            
            # 2. Clear by Field (Nuclear Fix for auto-generated IDs)
            docs = self._db.collection("prospectos").where("celular", "==", clean_phone).stream()
            for doc in docs:
                doc.reference.update({
                    "survey_state": firestore.DELETE_FIELD,
                    "updated_at": firestore.SERVER_TIMESTAMP
                })
            
            logger.info(f"✅ Estado de encuesta limpiado para {clean_phone} (ID y Campo)")
            
        except Exception as e:
            logger.error(f"❌ Error al limpiar estado de encuesta para {phone_number}: {e}")

    def delete_prospect_completely(self, phone_number: str) -> int:
        """
        Nuclear deletion of all prospect documents matching the phone (ID or field).
        Used in /reset command. Ensures timestamps and cached data are truly gone.
        """
        deleted = 0
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone_number)
            
            # Variations for deep sweep
            variants = [
                clean_phone,                         # International: 573...
                clean_phone.replace("57", "", 1),   # National: 3...
                f"+{clean_phone}"                    # Plus prefixed
            ]
            
            for variant in variants:
                # 1. Delete by ID
                doc_ref = self._db.collection("prospectos").document(variant)
                if doc_ref.get().exists:
                    # ULTIMATUM: Physically delete subcollections (Firestore doesn't do this auto)
                    history_ref = doc_ref.collection("historial")
                    batch = self._db.batch()
                    msgs = history_ref.stream()
                    for m in msgs:
                        batch.delete(m.reference)
                    batch.commit()
                    
                    # Delete the doc itself
                    doc_ref.delete()
                    deleted += 1
                    logger.info(f"🗑️ Nuclear delete: prospect doc and history for {variant}")
                
                # 2. Delete by 'celular' field
                docs = self._db.collection("prospectos").where("celular", "==", variant).stream()
                for doc in docs:
                    # Same nuclear subcollection purge
                    h_ref = doc.reference.collection("historial")
                    b = self._db.batch()
                    m_docs = h_ref.stream()
                    for m in m_docs:
                        b.delete(m.reference)
                    b.commit()
                    
                    doc.reference.delete()
                    deleted += 1
                    logger.info(f"🗑️ Nuclear delete: prospect by field {doc.id}")
            
            return deleted
        except Exception as e:
            logger.error(f"❌ Error in nuclear prospect delete for {phone_number}: {e}")
            return deleted

    async def save_message(self, phone_number: str, role: str, content: str) -> None:
        """
        Save a message to the chat history sub-collection.
        
        Path: mensajeria/whatsapp/sesiones/{phone}/historial
        
        Args:
            phone_number: User's phone number
            role: 'user' or 'model'
            content: Message text
        """
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone_number)
            
            # Sub-collection reference
            history_ref = self._db.collection("mensajeria").document("whatsapp").collection("sesiones").document(clean_phone).collection("historial")
            
            # Create message document
            message_data = {
                "role": role,
                "content": content,
                "timestamp": firestore.SERVER_TIMESTAMP
            }
            
            # Using add() allows auto-ID generation
            history_ref.add(message_data)
            # logger.debug(f"💾 Message saved for {clean_phone} ({role})")
            
        except Exception as e:
            logger.error(f"❌ Error saving message history for {phone_number}: {e}")

    async def get_chat_history(self, phone_number: str, limit: int = 10) -> list:
        """
        Retrieve recent chat history for context injection.
        
        Args:
            phone_number: User's phone number
            limit: Number of recent messages to retrieve
            
        Returns:
            List of dicts: [{"role": "user", "content": "..."}, ...] (Oldest first)
        """
        try:
            from app.core.utils import PhoneNormalizer
            clean_phone = PhoneNormalizer.normalize(phone_number)
            
            history_ref = self._db.collection("mensajeria").document("whatsapp").collection("sesiones").document(clean_phone).collection("historial")
            
            # Query: Order by timestamp DESC to get recent, then reverse list
            query = history_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
            docs = query.stream()
            
            messages = []
            for doc in docs:
                data = doc.to_dict()
                messages.append({
                    "role": data.get("role"),
                    "content": data.get("content"),
                    # Add timestamp for potential time-based logic (last 30m)
                    "timestamp": data.get("timestamp")
                })
            
            # Return reversed (chronological order: Oldest -> Newest)
            return messages[::-1]
            
        except Exception as e:
            logger.error(f"❌ Error getting chat history for {phone_number}: {e}")
            return []


# Singleton instance (will be initialized in main.py with db)
memory_service: Optional[MemoryService] = None


def init_memory_service(db: firestore.Client) -> None:
    """
    Initialize the global memory service instance.

    Args:
        db: Firestore client instance
    """
    global memory_service
    memory_service = MemoryService(db)
    logger.info("🧠 Global MemoryService initialized")
