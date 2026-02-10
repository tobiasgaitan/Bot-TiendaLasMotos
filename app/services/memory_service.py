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
        Retrieve prospect data from Firestore by document ID (phone number).
        
        The database stores prospects with phone numbers as document IDs.
        Uses multi-attempt strategy to handle different phone formats:
        1. Direct ID lookup with normalized phone
        2. Colombia prefix (57) stripped lookup
        
        Args:
            phone_number: Phone number to search for (e.g., "573192564288", "+573192564288", "3192564288")
        
        Returns:
            Dictionary with keys:
            - name: Prospect's name (from 'nombre' field)
            - moto_interest: Motorcycle of interest (from 'motoInteres' field)
            - summary: Previous conversation summary (from 'ai_summary' field)
            - exists: Boolean indicating if prospect was found
        
        Example:
            >>> data = memory_service.get_prospect_data("573192564288")
            >>> print(data)
            {
                "name": "Capitán Victoria",
                "moto_interest": "Victory Black",
                "summary": "Cliente VIP interesado en Victory Black",
                "exists": True
            }
        """
        try:
            # STEP 1: Normalize input - strip spaces, dashes, and +
            normalized_phone = phone_number.replace("+", "").replace(" ", "").replace("-", "").strip()
            
            logger.info(f"🔍 Buscando prospecto | Input: {phone_number} | Normalizado: {normalized_phone}")
            
            prospectos_ref = self._db.collection("prospectos")
            
            # ATTEMPT 1: Direct document ID lookup with normalized phone
            logger.info(f"🔍 Buscando ID: {normalized_phone}")
            doc = prospectos_ref.document(normalized_phone).get()
            
            if doc.exists:
                data = doc.to_dict()
                
                prospect_data = {
                    "name": data.get("nombre"),
                    "moto_interest": data.get("motoInteres"),
                    "summary": data.get("ai_summary"),
                    "exists": True
                }
                
                logger.info(
                    f"✅ Prospecto encontrado: {prospect_data['name']} | "
                    f"Moto de interés: {prospect_data['moto_interest']} | "
                    f"Tiene resumen: {prospect_data['summary'] is not None}"
                )
                
                return prospect_data
            
            # ATTEMPT 2: Strip Colombia prefix (57) and try again
            if normalized_phone.startswith("57") and len(normalized_phone) > 10:
                short_phone = normalized_phone[2:]  # Remove "57" prefix
                logger.info(f"🔄 Intento secundario ID: {short_phone}")
                
                doc = prospectos_ref.document(short_phone).get()
                
                if doc.exists:
                    data = doc.to_dict()
                    
                    prospect_data = {
                        "name": data.get("nombre"),
                        "moto_interest": data.get("motoInteres"),
                        "summary": data.get("ai_summary"),
                        "exists": True
                    }
                    
                    logger.info(
                        f"✅ Prospecto encontrado: {prospect_data['name']} | "
                        f"Moto de interés: {prospect_data['moto_interest']} | "
                        f"Tiene resumen: {prospect_data['summary'] is not None}"
                    )
                    
                    return prospect_data
            
            # No match found
            logger.info(
                f"📭 Prospecto no encontrado para {phone_number} | "
                f"Intentos: [{normalized_phone}, {normalized_phone[2:] if normalized_phone.startswith('57') and len(normalized_phone) > 10 else 'N/A'}]"
            )
            return {
                "name": None,
                "moto_interest": None,
                "summary": None,
                "exists": False
            }
            
        except Exception as e:
            logger.error(f"❌ Error al recuperar datos del prospecto {phone_number}: {str(e)}", exc_info=True)
            # Return empty context on error to prevent blocking conversation
            return {
                "name": None,
                "moto_interest": None,
                "summary": None,
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
        
        Updates the Firestore document with:
        - New conversation summary (ai_summary field)
        - Extracted structured data (nombre, motoInteres) if provided
        - Chatbot status activation (PENDING -> ACTIVE)
        
        Args:
            phone_number: Phone number to update
            summary_text: New conversation summary to save
            extracted_data: Optional dict with extracted fields:
                - name: Extracted name (updates 'nombre')
                - moto_interest: Extracted motorcycle interest (updates 'motoInteres')
        
        Example:
            >>> await memory_service.update_prospect_summary(
            ...     "3227303760",
            ...     "Cliente preguntó por financiación de Viva R",
            ...     {"name": "Carlos", "moto_interest": "Viva R"}
            ... )
        """
        try:
            # Clean phone number
            clean_phone = phone_number.replace("+", "").replace("57", "", 1) if phone_number.startswith("+57") else phone_number.replace("+", "")
            
            logger.info(f"💾 Updating prospect summary for {clean_phone}")
            
            # Find the prospect document
            prospectos_ref = self._db.collection("prospectos")
            query = prospectos_ref.where("celular", "==", clean_phone).limit(1)
            docs = query.get()
            
            if not docs:
                logger.warning(f"⚠️ No prospect found to update for {clean_phone}")
                # Create new prospect document if doesn't exist
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
            
            # Update existing document
            doc_ref = docs[0].reference
            current_data = docs[0].to_dict()
            
            # Prepare update data
            update_data = {
                "ai_summary": summary_text,
                "updated_at": firestore.SERVER_TIMESTAMP
            }
            
            # Update chatbot_status if currently PENDING
            if current_data.get("chatbot_status") == "PENDING":
                update_data["chatbot_status"] = "ACTIVE"
                logger.info(f"🟢 Activating chatbot status for {clean_phone}")
            
            # Update extracted data if provided
            if extracted_data:
                if extracted_data.get("name"):
                    update_data["nombre"] = extracted_data["name"]
                    logger.info(f"📝 Updating nombre: {extracted_data['name']}")
                
                if extracted_data.get("moto_interest"):
                    update_data["motoInteres"] = extracted_data["moto_interest"]
                    logger.info(f"🏍️ Updating motoInteres: {extracted_data['moto_interest']}")
            
            # Perform update with merge
            doc_ref.update(update_data)
            
            logger.info(f"✅ Successfully updated prospect summary for {clean_phone}")
            
        except Exception as e:
            logger.error(f"❌ Error updating prospect summary for {phone_number}: {str(e)}", exc_info=True)


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
