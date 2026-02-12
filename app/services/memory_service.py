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
                    "moto_interest": data.get("motoInteres"),
                    "summary": data.get("ai_summary"),
                    "human_help_requested": data.get("human_help_requested", False),
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
                    "moto_interest": data.get("motoInteres"),
                    "summary": data.get("ai_summary"),
                    "human_help_requested": data.get("human_help_requested", False),
                    "exists": True
                }

            logger.info(f"📭 Prospecto no encontrado para {normalized_phone}")
            return {
                "name": None,
                "moto_interest": None,
                "summary": None,
                "human_help_requested": False,
                "exists": False
            }

        except Exception as e:
            logger.error(f"❌ Error al recuperar datos del prospecto {phone_number}: {str(e)}", exc_info=True)
            return {
                "name": None,
                "moto_interest": None,
                "summary": None,
                "human_help_requested": False,
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
