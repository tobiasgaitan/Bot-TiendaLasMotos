"""
Memory Service - CRM Integration & Long-Term Memory
v9.6.0 - GSD Standard Compatibility (Linear Blocking)

CHANGELOG v9.6.0:
  - Renamed self.db → self._db (tests access memory_service._db)
  - Added _merge_extracted_data() with "null"/whitespace sanitization (test_memory_merge contract)
  - Added create_prospect_if_missing() with zombie session purge (test_reset_flow contract)
  - Added _find_prospect_ref() for get_prospect_data indirection (test_read_asymmetry contract)
  - Rewrote clear_memory() with real batch delete (test_memory_stream_coverage contract)
  - Preserved merge_data() and create_prospect() as aliases for backward compat
"""

import logging
from typing import Dict, Any, Optional, List
from google.cloud import firestore
from app.core.utils import PhoneNormalizer

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Sentinel values treated as "no data" by _merge_extracted_data
# ──────────────────────────────────────────────────────────────────────
_INVALID_SENTINELS = {"null", "none", "n/a", "undefined"}

# Canonical latch fields — once True, they must never revert to False
_LATCH_TRUE_FIELDS = frozenset({"habeas_data", "habeas_data_sent"})


class MemoryService:
    def __init__(self, db: firestore.AsyncClient):
        # WHY _db: tests (test_read_asymmetry, test_reset_flow) wire mocks via
        # memory_service._db.collection.side_effect — the underscore is contractual.
        self._db = db
        self.collection_name = "prospectos"
        logger.info("🧠 MemoryService v9.6.0: Modo de Compatibilidad Total")

    # ──────────────────────────────────────────────────────────────────
    # Pure helpers (sync) — called by tests directly
    # ──────────────────────────────────────────────────────────────────

    def is_valid(self, data: Any) -> bool:
        """Helper exigido por test_is_valid_helper_logic."""
        if not data or not isinstance(data, dict):
            return False
        return any(v is not None and v != "" for v in data.values())

    @staticmethod
    def _is_field_valid(value: Any) -> bool:
        """
        Determines if a single extracted value should be accepted into the merge.

        WHY: AI extraction can produce literal "null", whitespace-only strings,
        or empty strings — all must be rejected to protect existing Firestore data.
        """
        if value is None:
            return False
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "" or stripped.lower() in _INVALID_SENTINELS:
                return False
        # Booleans, numbers, non-empty strings pass
        return True

    def _merge_extracted_data(
        self, current_data: Dict[str, Any], incoming_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge logic for AI-extracted fields into existing Firestore document.

        Contract (test_memory_merge.py):
          - PRESERVE_IF_HISTORIC_VALID: None/empty/"null"/whitespace in incoming
            does NOT overwrite existing valid data. The merged dict only contains
            keys from incoming that passed _is_field_valid.
          - LATCH_TRUE_ONLY: Fields in _LATCH_TRUE_FIELDS that are already True
            in current_data MUST NOT revert to False.
          - Output contains ONLY incoming keys that survived validation + any
            latched fields. It does NOT echo back current_data keys untouched.

        Returns:
            Dict with only the validated incoming fields (plus latched overrides).
        """
        merged: Dict[str, Any] = {}
        if not incoming_data:
            return merged

        for key, value in incoming_data.items():
            # ── Latch check: once True, stays True ──
            if key in _LATCH_TRUE_FIELDS and current_data.get(key) is True:
                merged[key] = True
                continue

            # ── Field validity gate ──
            if not self._is_field_valid(value):
                continue

            merged[key] = value

        return merged

    # Backward-compat alias used by update_prospect_summary
    def merge_data(self, current_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy alias — delegates to _merge_extracted_data."""
        return self._merge_extracted_data(current_data, new_data)

    # ──────────────────────────────────────────────────────────────────
    # Firestore reference helpers (async)
    # ──────────────────────────────────────────────────────────────────

    async def get_ref(self, phone_number: str):
        """Returns DocumentReference for the prospect."""
        clean_phone = PhoneNormalizer.normalize(phone_number)
        return self._db.collection(self.collection_name).document(clean_phone)

    async def _find_prospect_ref(self, phone_number: str):
        """
        Indirection layer for get_prospect_data.

        WHY: test_read_asymmetry.py mocks this method to bypass the full
        Firestore query chain and inject controlled doc snapshots.
        """
        return await self.get_ref(phone_number)

    # ──────────────────────────────────────────────────────────────────
    # CRUD operations (async, linear blocking — NO create_task)
    # ──────────────────────────────────────────────────────────────────

    async def save_message(self, phone_number: str, role: str, content: str) -> None:
        """Persist a single chat message to mensajeria/whatsapp/sesiones/{phone}/historial."""
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = self._db.collection("mensajeria").document("whatsapp") \
                .collection("sesiones").document(clean_phone) \
                .collection("historial").document()
            await doc_ref.set({
                "role": role,
                "content": content,
                "timestamp": firestore.SERVER_TIMESTAMP,
            })
        except Exception as e:
            logger.exception(f"❌ save_message failed for {phone_number}: {e}")

    async def get_chat_history(self, phone_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve last N messages from historial, ordered ascending."""
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            docs = self._db.collection("mensajeria").document("whatsapp") \
                .collection("sesiones").document(clean_phone) \
                .collection("historial") \
                .order_by("timestamp", direction=firestore.Query.DESCENDING) \
                .limit(limit).stream()
            history = []
            async for doc in docs:
                history.append(doc.to_dict())
            return history[::-1]
        except Exception as e:
            logger.exception(f"❌ get_chat_history failed for {phone_number}: {e}")
            return []

    async def get_prospect_data(self, phone_number: str) -> Dict[str, Any]:
        """
        Read prospect document from Firestore.

        WHY _find_prospect_ref: allows test_read_asymmetry to inject mocks
        without wiring the full collection().document() chain.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            doc_snap = await doc_ref.get()
            if doc_snap.exists:
                data = doc_snap.to_dict() or {}
                data["exists"] = True
                if "celular" not in data:
                    data["celular"] = doc_ref.id
                return data
            return {"exists": False}
        except Exception as e:
            logger.exception(f"❌ get_prospect_data failed for {phone_number}: {e}")
            return {"exists": False}

    async def create_prospect_if_missing(self, phone_number: str) -> None:
        """
        Idempotent prospect initialization with zombie session purge.

        Contract (test_reset_flow.py, test_read_asymmetry.py):
          - If prospect does NOT exist → create with canonical keys
          - Purge any stale mensajeria session document
          - Canonical keys: habeas_data=False, habeas_data_sent=False,
            servicios_publicos=None, celular=normalized_phone, status=PENDING
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = self._db.collection(self.collection_name).document(clean_phone)
            doc_snap = await doc_ref.get()

            if not doc_snap.exists:
                payload = {
                    "celular": clean_phone,
                    "status": "PENDING", # [SYNC-CRM] Importante para el Dashboard
                    "habeas_data": False,
                    "habeas_data_sent": False,
                    "servicios_publicos": None,
                    "created_at": firestore.SERVER_TIMESTAMP,
                }
                await doc_ref.set(payload)
                logger.info(f"✅ Prospect created for {clean_phone} (Status: PENDING)")

            # Zombie session purge — always attempt
            session_ref = self._db.collection("mensajeria").document("whatsapp") \
                .collection("sesiones").document(clean_phone)
            await session_ref.delete()
        except Exception as e:
            logger.exception(f"❌ create_prospect_if_missing failed for {phone_number}: {e}")

    # Backward-compat alias
    async def create_prospect(self, phone_number: str, data: Dict[str, Any]) -> None:
        """Legacy create method — sets arbitrary data with habeas_data default."""
        try:
            doc_ref = await self.get_ref(phone_number)
            payload = data.copy()
            payload["celular"] = doc_ref.id
            payload["created_at"] = firestore.SERVER_TIMESTAMP
            if "habeas_data" not in payload:
                payload["habeas_data"] = False
            await doc_ref.set(payload)
        except Exception as e:
            logger.exception(f"❌ create_prospect failed for {phone_number}: {e}")

    async def clear_memory(self, phone_number: str) -> bool:
        """
        Batch-delete all historial documents for a phone number.

        Contract (test_memory_stream_coverage.py):
          - Iterate historial via async stream
          - Use Firestore batch with commit every 400 docs
          - Final commit at the end
          - Return True on success
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            history_ref = self._db.collection("mensajeria").document("whatsapp") \
                .collection("sesiones").document(clean_phone) \
                .collection("historial")

            batch = self._db.batch()
            count = 0

            async for doc in history_ref.stream():
                batch.delete(doc.reference)
                count += 1
                if count % 400 == 0:
                    await batch.commit()
                    batch = self._db.batch()

            # Final commit for remaining docs
            await batch.commit()

            logger.info(f"🧹 Memory cleared for {clean_phone}: {count} docs deleted")
            return True
        except Exception as e:
            logger.exception(f"❌ clear_memory failed for {phone_number}: {e}")
            return False

    async def delete_prospect_completely(self, phone_number: str) -> bool:
        """
        Nuclear wipe of a prospect: deletes document, history, and active sessions.
        
        Contract (v9.8.1):
          1. Delete prospect document from 'prospectos' collection.
          2. Clear chat history via clear_memory().
          3. Delete the session document in 'mensajeria/whatsapp/sesiones'.
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            logger.warning(f"☢️ [NUCLEAR RESET] Starting wipe for {clean_phone}")
            
            # 1. Clear History (Historial sub-collection)
            await self.clear_memory(clean_phone)
            
            # 2. Delete Session Document
            session_ref = self._db.collection("mensajeria").document("whatsapp") \
                .collection("sesiones").document(clean_phone)
            await session_ref.delete()
            
            # 3. Delete Prospect Document
            doc_ref = self._db.collection(self.collection_name).document(clean_phone)
            await doc_ref.delete()
            
            logger.info(f"✅ [NUCLEAR RESET] Finished wipe for {clean_phone}")
            return True
        except Exception as e:
            logger.exception(f"❌ delete_prospect_completely failed for {phone_number}: {e}")
            return False

    async def update_prospect_summary(
        self,
        phone_number: str,
        summary_text: str,
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Merge AI-extracted data into prospect and update summary."""
        try:
            doc_ref = await self.get_ref(phone_number)
            doc_snap = await doc_ref.get()
            current_data = doc_snap.to_dict() if doc_snap.exists else {}

            # Use centralized merge logic
            update_payload = self._merge_extracted_data(current_data, extracted_data or {})
            update_payload["ai_summary"] = summary_text
            update_payload["last_updated"] = firestore.SERVER_TIMESTAMP

            await doc_ref.set(update_payload, merge=True)
        except Exception as e:
            logger.exception(f"❌ update_prospect_summary failed for {phone_number}: {e}")

    async def generate_and_update_summary(
        self, 
        phone_number: str, 
        conversation_text: str, 
        ai_brain, 
        last_bot_question: str = ""
    ) -> None:
        """
        Garantía de Verdad (Linear Blocking):
        1. Ejecuta la extracción de la IA (Generate Summary).
        2. Persiste en Firestore inmediatamente.
        """
        try:
            logger.info(f"🧠 [LINEAR BLOCKING] Starting summary generation for {phone_number}...")
            
            # 1. AI Extraction (Async)
            summary_data = await ai_brain.generate_summary(
                conversation_text, 
                last_bot_question=last_bot_question,
                session_id=phone_number
            )
            
            # 2. Firestore Persistence
            await self.update_prospect_summary(
                phone_number, 
                summary_data.get("summary", ""), 
                summary_data.get("extracted", {})
            )
            
            logger.info(f"✅ Successfully updated prospect summary for {phone_number}")
            
        except Exception as e:
            logger.exception(f"❌ [LINEAR BLOCKING] Failed to generate/update summary for {phone_number}: {e}")

    async def transition_to_in_progress(self, phone_number: str) -> bool:
        """
        [ARCH-BULK-META-010] Transición atómica PENDING → IN_PROGRESS con Latch guard.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            doc_snap = await doc_ref.get()
            
            if not doc_snap.exists:
                return False

            current_data = doc_snap.to_dict() or {}
            current_status = current_data.get("status", "")
            
            if current_status != "PENDING":
                logger.info(f"⏭️ [STATE] Prospecto {phone_number} ya está en '{current_status}'. Transición omitida.")
                return False

            await doc_ref.update({
                "status": "IN_PROGRESS",
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            logger.info(f"🟢 [STATE] Prospecto {phone_number}: PENDING → IN_PROGRESS")
            return True

        except Exception as e:
            logger.exception(f"❌ [STATE] Error in transition_to_in_progress for {phone_number}: {e}")
            return False

    async def set_human_help_status(self, phone_number: str, status: bool) -> bool:
        """
        Set the human_help_requested flag. When True, the bot remains silent.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            await doc_ref.update({
                "human_help_requested": status,
                "updated_at": firestore.SERVER_TIMESTAMP
            })
            logger.info(f"✅ Updated human_help_requested={status} for {phone_number}")
            return True
        except Exception as e:
            logger.exception(f"❌ Error setting human_help_status for {phone_number}: {e}")
            return False

    async def update_whatsapp_status(
        self,
        phone_number: str,
        status_value: str,
        wamid: str,
        errors: Optional[List[dict]] = None
    ) -> None:
        """
        Actualiza el sub-campo metadata.whatsapp y campos de nivel superior para el Dashboard.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            
            # Sincronía de nivel superior para el Dashboard CRM
            payload = {
                "metadata.whatsapp.last_status": status_value,
                "metadata.whatsapp.last_status_timestamp": firestore.SERVER_TIMESTAMP,
                "metadata.whatsapp.last_wamid": wamid,
                "whatsapp_delivery_status": status_value, # [SYNC-CRM] Top-level field
            }
            
            if errors:
                payload["metadata.whatsapp.last_error"] = errors
                if isinstance(errors, list) and len(errors) > 0:
                    payload["last_whatsapp_error"] = errors[0].get("message")
            
            await doc_ref.update(payload)
            logger.info(f"✅ [STATUSES] Acuse '{status_value}' registrado para {phone_number}")
        except Exception as e:
            logger.exception(f"❌ [STATUSES] Error actualizando metadata.whatsapp para {phone_number}: {e}")

    async def update_last_interaction(self, phone_number: str) -> None:
        """
        Updates the 'fecha' timestamp to bring user to top of Admin Panel list.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            await doc_ref.update({"fecha": firestore.SERVER_TIMESTAMP})
            logger.info(f"🕐 Updated last interaction timestamp for {phone_number}")
        except Exception as e:
            logger.exception(f"❌ Error updating last interaction for {phone_number}: {e}")


# ──────────────────────────────────────────────────────────────────────
# Module-level singleton (used by routers)
# ──────────────────────────────────────────────────────────────────────
memory_service: Optional[MemoryService] = None


def init_memory_service(db: firestore.AsyncClient) -> None:
    """Initialize the global memory_service singleton."""
    global memory_service
    memory_service = MemoryService(db)
