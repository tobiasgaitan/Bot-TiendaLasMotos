"""
Memory Service - CRM Integration & Long-Term Memory
Handles prospect data retrieval and conversation summary updates in Firestore.
"""

import logging
from typing import Dict, Any, Optional
from google.cloud import firestore
from app.core.utils import PhoneNormalizer

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

    def _find_prospect_ref(self, phone_number: str) -> Optional[firestore.DocumentReference]:
        """
        Private helper to find a prospect reference by ID or legacy celular field.
        
        Logic:
        1. Normalize phone.
        2. Check if a document with that ID exists.
        3. If not, query by 'celular' field.
        
        Returns: DocumentReference if found, else None.
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            prospectos_ref = self._db.collection("prospectos")
            
            # 1. Try by ID
            doc_ref = prospectos_ref.document(clean_phone)
            if doc_ref.get().exists:
                return doc_ref
            
            # 2. Try by field query
            query = prospectos_ref.where("celular", "==", clean_phone).limit(1)
            docs = query.get()
            if docs:
                return docs[0].reference
                
            return None
        except Exception as e:
            logger.error(f"❌ Error in _find_prospect_ref for {phone_number}: {e}")
            return None

    def get_prospect_data(self, phone_number: str) -> Dict[str, Any]:
        """
        Retrieve prospect data from Firestore by document ID (normalized phone).

        Args:
            phone_number: Raw phone number to search for

        Returns:
            Dictionary with prospect data or empty context on error
        """
        try:
            doc_ref = self._find_prospect_ref(phone_number)
            
            if doc_ref:
                doc = doc_ref.get()
                data = doc.to_dict()
                prospect_data = {
                    "name": data.get("nombre"),
                    "ciudad": data.get("ciudad"),
                    "moto_interest": data.get("motoInteres"),
                    "moto_confirmada": data.get("moto_confirmada", False),
                    "payment_method": data.get("forma_pago"),
                    "summary": data.get("ai_summary"),
                    "human_help_requested": data.get("human_help_requested", False),
                    "survey_state": data.get("survey_state"),
                    "exists": True,
                    "habeas_data_sent": data.get("habeas_data_sent", False),
                    "habeas_data_accepted": data.get("habeas_data_accepted", False)
                }
                logger.info(
                    f"✅ Prospecto encontrado: {prospect_data['name']} | "
                    f"Moto: {prospect_data['moto_interest']} | "
                    f"Human Help: {prospect_data['human_help_requested']}"
                )
                return prospect_data

            logger.info(f"📭 Prospecto no encontrado para {phone_number}")
            return {
                "name": None, "ciudad": None, "moto_interest": None,
                "payment_method": None, "summary": None,
                "human_help_requested": False, "survey_state": None, "exists": False,
                "habeas_data_sent": False, "habeas_data_accepted": False
            }

        except Exception as e:
            logger.error(f"❌ Error al recuperar datos del prospecto {phone_number}: {str(e)}", exc_info=True)
            return {
                "name": None, "ciudad": None, "moto_interest": None,
                "payment_method": None, "summary": None,
                "human_help_requested": False, "survey_state": None, "exists": False,
                "habeas_data_sent": False, "habeas_data_accepted": False
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
            clean_phone = PhoneNormalizer.normalize(phone_number)
            logger.info(f"💾 Updating prospect summary for {clean_phone}")

            doc_ref = self._find_prospect_ref(phone_number)
            
            if not doc_ref:
                logger.warning(f"⚠️ No prospect found to update for {clean_phone}")
                new_doc_ref = self._db.collection("prospectos").document(clean_phone)
                new_doc_ref.set({
                    "celular": clean_phone,
                    "ai_summary": summary_text,
                    "chatbot_status": "ACTIVE",
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "updated_at": firestore.SERVER_TIMESTAMP
                })
                logger.info(f"✅ Created new prospect document for {clean_phone}")
                return

            doc = doc_ref.get()
            current_data = doc.to_dict()

            update_data = {
                "ai_summary": summary_text,
                "updated_at": firestore.SERVER_TIMESTAMP
            }

            if current_data.get("chatbot_status") == "PENDING":
                update_data["chatbot_status"] = "ACTIVE"
                logger.info(f"🟢 Activating chatbot status for {clean_phone}")

            # POR QUÉ: Mantener sincronización viva entre la charla de IA y los campos duros de la BD.
            # LÓGICA DE NEGOCIO: Si el LLM detecta que el cliente mencionó su ciudad o método de pago
            # orgánicamente, persistimos esto para que el motor determinista del embudo pueda avanzar.
            if extracted_data:
                # REGLA DE SEGURIDAD (QA Baseline): No permitir que valores nulos o vacíos sobrescriban datos válidos.
                def is_valid(val):
                    if val is None: return False
                    s_val = str(val).strip().lower()
                    return s_val not in ["", "null", "none", "n/a", "undefined"]

                if is_valid(extracted_data.get("name")):
                    update_data["nombre"] = extracted_data["name"]
                    logger.info(f"📝 Updating nombre: {extracted_data['name']}")
                
                if is_valid(extracted_data.get("moto_interest")):
                    update_data["motoInteres"] = extracted_data["moto_interest"]
                    logger.info(f"🏍️ Updating motoInteres: {extracted_data['moto_interest']}")
                
                if extracted_data.get("moto_confirmada") is not None:
                    update_data["moto_confirmada"] = extracted_data["moto_confirmada"]
                    logger.info(f"✅ Updating moto_confirmada: {extracted_data['moto_confirmada']}")
                
                if is_valid(extracted_data.get("moto_competidor")):
                    update_data["moto_competidor"] = extracted_data["moto_competidor"]
                    logger.info(f"🏎️ Updating moto_competidor: {extracted_data['moto_competidor']}")

                if is_valid(extracted_data.get("moto_auteco")):
                    update_data["moto_auteco"] = extracted_data["moto_auteco"]
                    logger.info(f"🛵 Updating moto_auteco: {extracted_data['moto_auteco']}")
                
                if is_valid(extracted_data.get("city")):
                    update_data["ciudad"] = extracted_data["city"]
                    logger.info(f"🌆 Updating ciudad: {extracted_data['city']}")
                
                if is_valid(extracted_data.get("payment_method")):
                    update_data["forma_pago"] = extracted_data["payment_method"]
                    logger.info(f"💳 Updating forma_pago: {extracted_data['payment_method']}")
                    
                if is_valid(extracted_data.get("ocupacion")):
                    update_data["ocupacion"] = extracted_data["ocupacion"]
                    logger.info(f"💼 Updating ocupacion: {extracted_data['ocupacion']}")
                
                if is_valid(extracted_data.get("datacredito")):
                    update_data["datacredito"] = extracted_data["datacredito"]
                    logger.info(f"🏦 Updating datacredito: {extracted_data['datacredito']}")
                
                if is_valid(extracted_data.get("vivienda")):
                    update_data["vivienda"] = extracted_data["vivienda"]
                    logger.info(f"🏠 Updating vivienda: {extracted_data['vivienda']}")
                
                if is_valid(extracted_data.get("ingresos")):
                    update_data["ingresos"] = extracted_data["ingresos"]
                    logger.info(f"💵 Updating ingresos: {extracted_data['ingresos']}")
                
                if is_valid(extracted_data.get("gastos")):
                    update_data["gastos"] = extracted_data["gastos"]
                    logger.info(f"💸 Updating gastos: {extracted_data['gastos']}")
                
                if is_valid(extracted_data.get("gas_natural")):
                    # For boolean, we just need to make sure it's not None
                    if extracted_data.get("gas_natural") is not None:
                        update_data["gas_natural"] = extracted_data["gas_natural"]
                        logger.info(f"🔥 Updating gas_natural: {extracted_data['gas_natural']}")
                
                if is_valid(extracted_data.get("plan_celular")):
                    update_data["plan_celular"] = extracted_data["plan_celular"]
                    logger.info(f"📱 Updating plan_celular: {extracted_data['plan_celular']}")

                if extracted_data.get("habeas_data_sent") is not None:
                    update_data["habeas_data_sent"] = extracted_data["habeas_data_sent"]
                    logger.info(f"📜 Updating habeas_data_sent: {extracted_data['habeas_data_sent']}")
                
                if extracted_data.get("habeas_data_accepted") is not None:
                    update_data["habeas_data_accepted"] = extracted_data["habeas_data_accepted"]
                    logger.info(f"✅ Updating habeas_data_accepted: {extracted_data['habeas_data_accepted']}")

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
            doc_ref = self._find_prospect_ref(phone_number)
            if doc_ref:
                doc_ref.update({"fecha": firestore.SERVER_TIMESTAMP})
                logger.info(f"✅ TIMESTAMP UPDATED for {phone_number}")
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
            logger.info(f"🔧 Setting human_help_requested={status} for {phone_number}")

            doc_ref = self._find_prospect_ref(phone_number)
            
            if doc_ref:
                doc_ref.update({
                    "human_help_requested": status,
                    "updated_at": firestore.SERVER_TIMESTAMP,
                    "fecha": firestore.SERVER_TIMESTAMP
                })
                logger.info(f"✅ Updated human_help_requested={status} for {phone_number}")
                return

            # No existing document found - create new one
            normalized_phone = PhoneNormalizer.normalize(phone_number)
            logger.warning(f"⚠️ No existing prospect found for {phone_number}, creating new document")
            new_doc_ref = self._db.collection("prospectos").document(normalized_phone)
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

    def delete_prospect_completely(self, phone_number: str) -> int:
        """
        Nuclear wipe of a prospect and their history.
        Used by the /reset command to allow a fresh start.
        
        Args:
            phone_number: Raw phone number to wipe
            
        Returns:
            int: Number of items deleted (prospect doc + variants)
        """
        try:
            deleted = 0
            clean_phone = PhoneNormalizer.normalize(phone_number)
            
            # 1. Targeted Delete using Centralized Helper
            doc_ref = self._find_prospect_ref(phone_number)
            if doc_ref:
                # Nuclear subcollection purge
                history_ref = doc_ref.collection("historial")
                batch = self._db.batch()
                msgs = history_ref.stream()
                for m in msgs:
                    batch.delete(m.reference)
                batch.commit()
                
                # Delete the doc itself
                doc_ref.delete()
                deleted += 1
                logger.info(f"🗑️ Nuclear delete: prospect doc and history for {phone_number}")

            # 2. Variant Cleanup (Safety sweep for variants not caught by helper)
            variants = [
                clean_phone,                         # International: 573...
                clean_phone.replace("57", "", 1),   # National: 3...
                f"+{clean_phone}"                    # Plus prefixed
            ]
            
            for variant in variants:
                # Delete by ID variants
                v_ref = self._db.collection("prospectos").document(variant)
                v_doc = v_ref.get()
                if v_doc.exists:
                    # History purge
                    h_ref = v_ref.collection("historial")
                    b = self._db.batch()
                    for m in h_ref.stream():
                        b.delete(m.reference)
                    b.commit()
                    v_ref.delete()
                    deleted += 1
                    logger.info(f"🗑️ Nuclear delete: variant ID {variant}")
                
                # Delete by 'celular' field variants
                docs = self._db.collection("prospectos").where("celular", "==", variant).stream()
                for doc in docs:
                    # Nuclear subcollection purge
                    h_ref = doc.reference.collection("historial")
                    b = self._db.batch()
                    for m in h_ref.stream():
                        b.delete(m.reference)
                    b.commit()
                    
                    doc.reference.delete()
                    deleted += 1
                    logger.info(f"🗑️ Nuclear delete: variant field match {doc.id}")
            
            return deleted
        except Exception as e:
            logger.error(f"❌ Error in nuclear prospect delete for {phone_number}: {e}", exc_info=True)
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
