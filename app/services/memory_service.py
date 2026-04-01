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

    async def get_prospect_data(self, phone_number: str) -> Dict[str, Any]:
        """
        Garantía de Verdad (Linear Blocking): Recupera datos frescos del prospecto.
        """
        import asyncio
        return await asyncio.to_thread(self._get_prospect_data_sync, phone_number)

    def _get_prospect_data_sync(self, phone_number: str) -> Dict[str, Any]:
        """
        Internal sync retrieval for Firestore.
        """
        try:
            doc_ref = self._find_prospect_ref(phone_number)
            if doc_ref:
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    prospect_data = {
                        "nombre": data.get("nombre") or data.get("name") or "",
                        "ciudad": data.get("ciudad") or data.get("city") or "",
                        "moto_interest": data.get("moto_interest"), # Unified nomenclature
                        "moto_confirmada": data.get("moto_confirmada", False),
                        "forma_pago": data.get("forma_pago") or data.get("payment_method") or "",
                        "summary": data.get("ai_summary"),
                        "human_help_requested": data.get("human_help_requested", False),
                        "survey_state": data.get("survey_state"),
                        "exists": True,
                        "habeas_data_sent": data.get("habeas_data_sent", False),
                        "habeas_data_accepted": data.get("habeas_data_accepted", False),
                        "total_tokens_consumed": data.get("total_tokens_consumed", 0),
                        "session_cost_usd": data.get("session_cost_usd", 0.0)
                    }
                    return prospect_data
            
            return {
                "nombre": "", "ciudad": "", "moto_interest": "",
                "forma_pago": "", "summary": "",
                "human_help_requested": False, "survey_state": None, "exists": False,
                "habeas_data_sent": False, "habeas_data_accepted": False,
                "total_tokens_consumed": 0, "session_cost_usd": 0.0
            }
        except Exception as e:
            logger.error(f"❌ Error in _get_prospect_data_sync for {phone_number}: {e}")
            return {"exists": False}

    async def generate_and_update_summary(self, phone_number: str, conversation_text: str, ai_brain, last_bot_question: str = "") -> None:
        """
        Garantía de Verdad (Linear Blocking):
        1. Ejecuta la extracción de la IA (Generate Summary).
        2. Espera el resultado.
        3. Persiste en Firestore inmediatamente.
        4. Loguea la confirmación antes de permitir el siguiente paso.
        """
        try:
            logger.info(f"🧠 [LINEAR BLOCKING] Starting summary generation for {phone_number}...")
            
            # --- INYECCIÓN DE CONTEXTO PREVIO (JSON Voorhees v6.6.6) ---
            prospect_data = await self.get_prospect_data(phone_number)
            moto_interest_prev = prospect_data.get("moto_interest", "") if prospect_data else ""

            # 1. AI Extraction (Async)
            summary_data = await ai_brain.generate_summary(
                conversation_text, 
                last_bot_question=last_bot_question,
                session_id=phone_number,
                previous_moto_interest=moto_interest_prev
            )
            
            # 2. Firestore Persistence (Async wrapper)
            await self.update_prospect_summary(
                phone_number, 
                summary_data.get("summary", ""), 
                summary_data.get("extracted", {})
            )
            
            logger.info(f"✅ Successfully updated prospect summary for {phone_number}")
            
        except Exception as e:
            logger.error(f"❌ [LINEAR BLOCKING] Failed to generate/update summary: {e}")

    async def update_prospect_summary(self, phone_number: str, summary_text: str, extracted_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Updates the conversation summary and merges extracted PII data into Firestore.
        
        Args:
            phone_number: Phone number to update
            summary_text: New conversation summary to save
            extracted_data: Optional dict with extracted fields
        """
        import asyncio
        await asyncio.to_thread(self._update_prospect_summary_sync, phone_number, summary_text, extracted_data)

    def _update_prospect_summary_sync(self, phone_number: str, summary_text: str, extracted_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Internal sync update for Firestore.
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

            # 1. Base update data
            update_data = {
                "ai_summary": summary_text,
                "updated_at": firestore.SERVER_TIMESTAMP
            }

            if current_data.get("chatbot_status") == "PENDING":
                update_data["chatbot_status"] = "ACTIVE"
                logger.info(f"🟢 Activating chatbot status for {clean_phone}")

            # 2. MERGE STRATEGY (Non-Destructive PII Fusion)
            if extracted_data:
                # Smart Unwrapping: Accept both nested and flat formats
                clean_data = extracted_data.get("extracted") or extracted_data if isinstance(extracted_data, dict) else {}
                
                merged_fields = self._merge_extracted_data(current_data, clean_data)
                
                # ROI Telemetry injection from AI Brain
                telemetry = extracted_data.get("telemetry") if isinstance(extracted_data, dict) else None
                if telemetry:
                    added_tokens = telemetry.get("tokens", 0)
                    added_cost = telemetry.get("cost", 0.0)
                    update_data["total_tokens_consumed"] = current_data.get("total_tokens_consumed", 0) + added_tokens
                    update_data["session_cost_usd"] = current_data.get("session_cost_usd", 0.0) + added_cost
                    logger.info(f"📊 [TELEMETRY] Added {added_tokens} tokens (${added_cost:.6f} USD) to session ROI.")

                if merged_fields:
                    update_data.update(merged_fields)
                    logger.info(f"🧬 Merged {len(merged_fields)} fields using Non-Destructive strategy")

            logger.info(f"💾 [MEMORY DUMP] Final payload to Firestore for {clean_phone}: {update_data}")
            doc_ref.update(update_data)
            logger.info(f"✅ Successfully updated prospect summary for {clean_phone}")

        except Exception as e:
            logger.error(f"❌ Error updating prospect summary for {phone_number}: {str(e)}", exc_info=True)

    def _merge_extracted_data(self, current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies Non-Destructive Merge Strategy with Nomenclature Translation.
        
        Rules:
        - TRANSLATION: Maps AI (English) keys to Firestore (Legacy Spanish/CamelCase) keys.
        - PRESERVE_IF_HISTORIC_VALID: Incoming null/empty does NOT overwrite existing valid data.
        - LATCH_TRUE_ONLY: Boolean flags cannot transition from True to False.
        """
        merged = {}
        
        # MAPA DE TRADUCCIÓN OBLIGATORIO: AI_Key -> Firestore_Legacy_Key
        field_mapping = {
            "nombre": "nombre",
            "ciudad": "ciudad",
            "moto_interest": "moto_interest", # Unified
            "moto_ofrecida": "moto_ofrecida",  # Renamed from moto_offered
            "forma_pago": "forma_pago",
            "ocupacion": "ocupacion",
            "datacredito": "datacredito",
            "vivienda": "vivienda",
            "ingresos": "ingresos",
            "gastos": "gastos",
            "moto_competidor": "moto_competidor",
            "moto_auteco": "moto_auteco",
            "moto_aceptada": "moto_aceptada",
            "moto_confirmada": "moto_confirmada", # New field for v6.6.2
            "total_tokens_consumed": "total_tokens_consumed",
            "session_cost_usd": "session_cost_usd",
            "doc_cedula_url": "doc_cedula_url",      # v6.7.x
            "doc_recibo_gas_url": "doc_recibo_gas_url", # v6.7.x
            "doc_cedula": "doc_cedula",              # v6.7.x
            "doc_recibo_gas": "doc_recibo_gas"       # v6.7.x
        }

        def is_valid(val):
            if val is None: return False
            if isinstance(val, bool): return True
            s_val = str(val).strip().lower()
            return s_val not in ["", "null", "none", "n/a", "undefined"]

        # 1. Map and Merge String/Content Fields
        for ai_key, db_key in field_mapping.items():
            new_val = incoming.get(ai_key)
            existing_val = current.get(db_key)
            
            if is_valid(new_val):
                merged[db_key] = new_val  # PERSISTENCIA EN LLAVE CORRECTA
            elif is_valid(existing_val):
                pass # Preserve historic valid data

        # 2. Boolean/Latch Fields (LATCH_TRUE_ONLY)
        latch_fields = ["habeas_data_sent", "habeas_data_accepted", "moto_confirmada", "gas_natural"]
        for field in latch_fields:
            new_val = incoming.get(field)
            existing_val = current.get(field, False)
            
            if new_val is not None:
                if existing_val and not new_val:
                    merged[field] = True
                else:
                    merged[field] = new_val

        return merged

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
                "nombre": "",
                "ciudad": "",
                "moto_interest": "", # Mandatory Key Alignment
                "forma_pago": "",
                "chatbot_status": "ACTIVE",
                "status": "Pendiente",
                "source": "whatsapp_bot",
                "human_help_requested": False,
                "habeas_data_sent": False,
                "habeas_data_accepted": False,
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

    def _delete_collection_batched(self, collection_ref, batch_size=400):
        """
        Helper to delete all documents in a collection or subcollection using batches.
        Firestore limit is 500 per batch. We use 400 for safety.
        """
        total_deleted = 0
        while True:
            docs = list(collection_ref.limit(batch_size).stream())
            if not docs:
                break
                
            batch = self._db.batch()
            count = 0
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
            
            batch.commit()
            total_deleted += count
            
            if count < batch_size:
                break
        return total_deleted

    async def delete_prospect_completely(self, phone_number: str) -> int:
        """
        Nuclear wipe of a prospect and their history.
        Used by the /reset command to allow a fresh start.
        Handles Firestore batch limits for long histories.
        
        Args:
            phone_number: Raw phone number to wipe
            
        Returns:
            int: Number of items deleted (prospect doc + variants + history)
        """
        import asyncio
        return await asyncio.to_thread(self._delete_prospect_completely_sync, phone_number)

    def _delete_prospect_completely_sync(self, phone_number: str) -> int:
        """
        Internal sync implementation of nuclear wipe.
        """
        try:
            deleted = 0
            clean_phone = PhoneNormalizer.normalize(phone_number)

            # --- 1. PURGE MENSAJERIA SESSIONS (AI History) ---
            try:
                session_ref = self._db.collection("mensajeria").document("whatsapp").collection("sesiones").document(clean_phone)
                history_ref = session_ref.collection("historial")
                
                # Purge history subcollection with batches
                count = self._delete_collection_batched(history_ref)
                
                # Delete the session document itself
                session_ref.delete()
                deleted += count + 1
                logger.info(f"🗑️ Nuclear delete: mensajeria sessions purged for {clean_phone} ({count} msgs)")
            except Exception as e:
                logger.warning(f"⚠️ Failed to purge mensajeria session for {clean_phone}: {e}")
            
            # --- 2. PURGE PROSPECT DATA (CRM) ---
            # Targeted Delete using Centralized Helper
            doc_ref = self._find_prospect_ref(phone_number)
            if doc_ref:
                # Nuclear subcollection purge with batches
                history_ref = doc_ref.collection("historial")
                count = self._delete_collection_batched(history_ref)
                
                # Delete the doc itself
                doc_ref.delete()
                deleted += count + 1
                logger.info(f"🗑️ Nuclear delete: prospect doc and history for {phone_number}")

            # --- 3. VARIANT CLEANUP ---
            variants = [
                clean_phone,                         # International: 573...
                clean_phone.replace("57", "", 1),   # National: 3...
                f"+{clean_phone}"                    # Plus prefixed
            ]
            
            for variant in variants:
                # Delete by ID variants
                v_ref = self._db.collection("prospectos").document(variant)
                if v_ref.get().exists:
                    # History purge
                    h_ref = v_ref.collection("historial")
                    count = self._delete_collection_batched(h_ref)
                    v_ref.delete()
                    deleted += count + 1
                    logger.info(f"🗑️ Nuclear delete: variant ID {variant} and {count} history msgs")
                
                # Delete by 'celular' field variants
                docs = list(self._db.collection("prospectos").where("celular", "==", variant).stream())
                for doc in docs:
                    # Nuclear subcollection purge
                    h_ref = doc.reference.collection("historial")
                    count = self._delete_collection_batched(h_ref)
                    doc.reference.delete()
                    deleted += count + 1
                    logger.info(f"🗑️ Nuclear delete: variant field match {doc.id} and {count} history msgs")
            
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


    async def clear_memory(self, phone_number: str) -> bool:
        """
        Nivel 5: Borrado total del historial de chat en mensajeria y memoria de IA.
        
        Args:
            phone_number: User's phone to clear.
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            history_ref = self._db.collection("mensajeria").document("whatsapp").collection("sesiones").document(clean_phone).collection("historial")
            
            # Batch delete
            batch = self._db.batch()
            docs = history_ref.stream()
            count = 0
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                if count >= 400: # Firestore limit
                    batch.commit()
                    batch = self._db.batch()
                    count = 0
            batch.commit()
            
            logger.info(f"🧠 AI Memory cleared for {clean_phone}")
            return True
        except Exception as e:
            logger.error(f"❌ Error clearing memory for {phone_number}: {e}")
            return False

# Singleton instance (will be initialized in main.py with db)
memory_service: Optional["MemoryService"] = None

def init_memory_service(db: firestore.Client) -> None:
    """
    Initialize the global memory service instance.

    Args:
        db: Firestore client instance
    """
    global memory_service
    memory_service = MemoryService(db)
    logger.info("🧠 Global MemoryService initialized")
