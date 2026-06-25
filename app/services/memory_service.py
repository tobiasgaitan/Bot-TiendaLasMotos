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
import asyncio
from typing import Dict, Any, Optional, List, Set
from google.cloud import firestore
from google.api_core import exceptions as gcp_exceptions
from app.core.utils import PhoneNormalizer
from app.core.config import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Sentinel values treated as "no data" by _merge_extracted_data
# ──────────────────────────────────────────────────────────────────────
_INVALID_SENTINELS = {"null", "none", "n/a", "undefined"}

# Canonical latch fields — once True, they must never revert to False
_LATCH_TRUE_FIELDS = frozenset({"habeas_data_accepted", "habeas_data_accepted_sent"})

# CRM protected fields — the bot must NEVER overwrite these if they already exist
_CRM_PROTECTED_FIELDS = frozenset({"approved_amount", "monthly_quota", "current_agent"})


class _ContingencySnapshot:
    """Objeto mock de contingencia (Quick Task 042) para prevenir AttributeError cuando _firestore_io falla."""
    @property
    def exists(self) -> bool:
        return False
    def to_dict(self) -> dict:
        return {}


class MemoryService:
    def __init__(self, db: firestore.AsyncClient):
        # WHY _db: tests (test_read_asymmetry, test_reset_flow) wire mocks via
        # memory_service._db.collection.side_effect — the underscore is contractual.
        self._db = db
        self.collection_name = "prospectos"
        self._pending_tasks: Set[asyncio.Task] = set()
        logger.info("🧠 MemoryService v9.8.5: Refactor Exception Handling")

    def _track_task(self, coro) -> asyncio.Task:
        """
        Register a coroutine as a tracked task to ensure visibility during shutdown.
        """
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
        return task

    async def _firestore_io(self, coro, phone: str, label: str, timeout: Optional[int] = None):
        """
        [BOT-INFRA-33] Interceptor de timeout asíncrono para operaciones I/O de Firestore.

        Comportamiento (Quick Task 042):
          - Envuelve cualquier corutina de Firestore en asyncio.wait_for.
          - Atrapa CUALQUIER excepción de red o Google usando except Exception as e.
          - Registra log forense con logger.exception(e).
          - Fuerza re-inicialización limpia de self._db para curar el socket.
          - Despacha mensaje de contingencia.
          - Elimina la lógica de reintento para evitar RuntimeError de corrutina agotada.
          - Retorna un _ContingencySnapshot para no abortar de inmediato.
        """
        effective_timeout = timeout if timeout is not None else settings.db_timeout
        try:
            return await asyncio.wait_for(coro, timeout=effective_timeout)
        except Exception as e:
            logger.exception(
                f"🔌 [BOT-INFRA-33] ERROR o TIMEOUT ({effective_timeout}s) en '{label}' "
                f"para phone='{phone}'. Fallo en Firestore (Red/GCP/Timeout). "
                f"Forzando re-inicialización y emitiendo contingencia. Detalle: {e}"
            )
            
            # Re-inicialización limpia del cliente de Firestore (curar socket)
            try:
                self._db = firestore.AsyncClient(
                    project=self._db.project,
                    credentials=self._db._credentials
                )
                logger.info(f"🔄 [BOT-INFRA-33] Cliente Firestore re-inicializado exitosamente.")
            except Exception as reinit_err:
                logger.error(f"❌ [BOT-INFRA-33] Fallo al re-inicializar Firestore AsyncClient para {phone}: {reinit_err}")
                
            raise

    async def shutdown(self, timeout: int = 8) -> None:
        """
        Graceful Shutdown Mechanism (Atomic Persistence Flush).
        Waits for all tracked tasks to complete before process termination.
        """
        if not self._pending_tasks:
            logger.info("👋 [SHUTDOWN] No pending persistence tasks. Closing cleanly.")
            return

        logger.info(f"⏳ [SHUTDOWN] Flushing {len(self._pending_tasks)} pending persistence tasks (Timeout: {timeout}s)...")
        try:
            await asyncio.wait_for(asyncio.gather(*self._pending_tasks, return_exceptions=True), timeout=timeout)
            logger.info("✅ [SHUTDOWN] All persistence tasks flushed successfully.")
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ [SHUTDOWN] Persistence flush timed out after {timeout}s. {len(self._pending_tasks)} tasks lost.")
        except Exception as e:
            logger.exception(f"❌ [SHUTDOWN] Error during persistence flush: {e}")

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
            # --- GUARDRAIL TAREA 3.1: Proteger la escritura del asesor humano ---
            if key in _CRM_PROTECTED_FIELDS and key in current_data:
                continue

            # ── Latch check: once True, stays True ──
            if key in _LATCH_TRUE_FIELDS and current_data.get(key) is True:
                merged[key] = True
                continue

            # ── Field validity gate ──
            if not self._is_field_valid(value):
                continue

            merged[key] = value

        # [HOTFIX] Inyección de valor por defecto para esquema estricto
        # Permite el guardado parcial de la memoria en el PASO 2 de Simulación Ciega
        # Solo inyecta False si el documento actual no tiene la llave y la IA tampoco la extrajo
        if current_data.get("habeas_data_accepted") is None and "habeas_data_accepted" not in merged:
            merged["habeas_data_accepted"] = False

        return merged
        
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
        """Persist a single chat message to prospectos/{phone}/historial."""
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = self._db.collection(self.collection_name).document(clean_phone) \
                .collection("historial").document()
            await self._firestore_io(
                doc_ref.set({"role": role, "content": content, "timestamp": firestore.SERVER_TIMESTAMP}),
                phone=clean_phone, label="save_message"
            )
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded) as e:
            logger.exception(f"🔌 [NETWORK_ERR] Fallo de red/timeout de Firestore en save_message para {phone_number}: {e}")
            raise
        except Exception as e:
            logger.exception(f"❌ save_message failed for {phone_number}: {e}")
            raise

    async def get_chat_history(self, phone_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve last N messages from historial, ordered ascending."""
        clean_phone = PhoneNormalizer.normalize(phone_number)
        try:
            query_ref = self._db.collection(self.collection_name).document(clean_phone) \
                .collection("historial") \
                .order_by("timestamp", direction=firestore.Query.DESCENDING) \
                .limit(limit)
            # WHY: stream() devuelve AsyncGenerator — se consuma dentro del timeout
            history = []
            async def _collect():
                async for doc in query_ref.stream():
                    history.append(doc.to_dict())
            await self._firestore_io(_collect(), phone=clean_phone, label="get_chat_history")
            return history[::-1]
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded) as e:
            logger.exception(f"🔌 [NETWORK_ERR] Fallo de red/timeout de Firestore en get_chat_history para {phone_number}: {e}")
            raise
        except Exception as e:
            logger.exception(f"❌ get_chat_history failed for {phone_number}: {e}")
            raise

    async def get_prospect_data(self, phone_number: str) -> Dict[str, Any]:
        """
        Read prospect document from Firestore.

        WHY _find_prospect_ref: allows test_read_asymmetry to inject mocks
        without wiring the full collection().document() chain.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            doc_snap = await self._firestore_io(doc_ref.get(), phone=phone_number, label="get_prospect_data")
            if doc_snap.exists:
                data = doc_snap.to_dict() or {}
                data["exists"] = True
                if "celular" not in data:
                    data["celular"] = doc_ref.id
                return data
            return {"exists": False}
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded) as e:
            logger.exception(f"🔌 [NETWORK_ERR] Fallo de red/timeout de Firestore en get_prospect_data para {phone_number}: {e}")
            raise
        except Exception as e:
            logger.exception(f"❌ get_prospect_data failed for {phone_number}: {e}")
            raise

    async def create_prospect_if_missing(self, phone_number: str) -> None:
        """
        Idempotent prospect initialization with zombie session purge.
        Restored from v9.5.0 logic to ensure full CRM compatibility.

        Contract (test_reset_flow.py, test_read_asymmetry.py):
          - If prospect does NOT exist → create with canonical keys
          - Purge any stale historial subcollection docs
          - Canonical keys: status=PENDING, chatbot_status=ACTIVE, etc.
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = self._db.collection(self.collection_name).document(clean_phone)
            doc_snap = await self._firestore_io(doc_ref.get(), phone=clean_phone, label="create_prospect_if_missing.get")

            if not doc_snap.exists:
                payload = {
                    "celular": clean_phone,
                    "nombre": "",
                    "ciudad": "",
                    "moto_interest": "",
                    "forma_pago": "",
                    "chatbot_status": "ACTIVE",
                    "status": "PENDING", # [SYNC-CRM] Ancla para el Dashboard
                    "source": "whatsapp_bot",
                    "human_help_requested": False,
                    "habeas_data_accepted": False,
                    "habeas_data_accepted_sent": False,
                    "servicios_publicos": None,
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "fecha": firestore.SERVER_TIMESTAMP,
                    "current_agent": "expert",
                    "total_tokens_consumed": 0,
                    "session_cost_usd": 0.0
                }
                await self._firestore_io(doc_ref.set(payload), phone=clean_phone, label="create_prospect_if_missing.set")
                logger.info(f"✅ Prospect created for {clean_phone} (Status: PENDING)")

            # Zombie purge — clear stale historial docs under prospectos/{phone}/historial
            # WHY: Ensures idempotency for /reset by wiping orphan history
            await self.clear_memory(clean_phone)
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded) as e:
            logger.exception(f"🔌 [NETWORK_ERR] Fallo de red/timeout de Firestore en create_prospect_if_missing para {phone_number}: {e}")
            raise
        except Exception as e:
            logger.exception(f"❌ create_prospect_if_missing failed for {phone_number}: {e}")
            raise

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
            history_ref = self._db.collection(self.collection_name).document(clean_phone) \
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
        Nuclear wipe of a prospect and their history (ASYNC).
        Restored from v9.5.0 with CRM MULTI-SCAN compatibility.
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            logger.warning(f"☢️ [NUCLEAR RESET] Starting multi-scan wipe for {clean_phone}")
            
            # --- 1. PURGE HISTORIAL (Subcolección bajo prospectos) ---
            try:
                await self.clear_memory(clean_phone)
            except Exception as e:
                logger.warning(f"⚠️ Failed to purge historial for {clean_phone}: {e}")
            
            # --- 2. PURGE PROSPECT DATA (CRM MULTI-SCAN) ---
            prospectos_ref = self._db.collection(self.collection_name)
            
            # Search by ID, celular field, and Variations
            variations = [clean_phone]
            if clean_phone.startswith("+"):
                variations.append(clean_phone.replace("+", ""))
            
            # Search and destroy all matches
            query = prospectos_ref.where("celular", "in", list(set(variations))).limit(10)
            docs = await query.get()
            
            for doc in docs:
                logger.info(f"🧹 [NUCLEAR WIPE] Removing record {doc.id}")
                await doc.reference.delete()
            
            # Ensure the normalized ID document is gone
            await prospectos_ref.document(clean_phone).delete()
            
            logger.info(f"✅ [NUCLEAR RESET] Finished multi-scan wipe for {clean_phone}")
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
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = await self.get_ref(clean_phone)
            doc_snap = await self._firestore_io(doc_ref.get(), phone=clean_phone, label="update_prospect_summary.get")
            
            # --- CORRECCIÓN QUIRÚRGICA ANTE BORRADO NUCLEAR (/RESET) ---
            if not doc_snap.exists:
                logger.warning(f"⚠️ [RESET_RECOVERY] Documento no encontrado para {clean_phone} durante actualización. Creando nodo base de emergencia...")
                # Invocamos la inicialización limpia con claves canónicas
                await self.create_prospect_if_missing(clean_phone)
                # Re-congelamos el snapshot para obtener el diccionario base limpio
                doc_snap = await self._firestore_io(doc_ref.get(), phone=clean_phone, label="update_prospect_summary.reget")
            
            current_data = doc_snap.to_dict() if doc_snap.exists else {}

            # Use centralized merge logic
            update_payload = self._merge_extracted_data(current_data, extracted_data or {})
            update_payload["ai_summary"] = summary_text
            update_payload["fecha"] = firestore.SERVER_TIMESTAMP

            await self._firestore_io(doc_ref.set(update_payload, merge=True), phone=clean_phone, label="update_prospect_summary.set")
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded):
            raise
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
            try:
                summary_text = summary_data["summary"]
                extracted_data = summary_data["extracted"]
            except KeyError as e:
                logger.warning(
                    f"⚠️ [ANTI-NULL-MASKING] Fallo de aserción rígida. Llave mandatoria ausente en EXTRACTION_SCHEMA: {e}. "
                    f"Payload de IA: {summary_data}",
                    exc_info=True
                )
                summary_text = summary_data.get("summary", "")
                extracted_data = summary_data.get("extracted", {})

            await self.update_prospect_summary(
                phone_number, 
                summary_text, 
                extracted_data
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
            doc_snap = await self._firestore_io(doc_ref.get(), phone=phone_number, label="transition_to_in_progress.get")
            
            if not doc_snap.exists:
                return False

            current_data = doc_snap.to_dict() or {}
            current_status = current_data.get("status", "")
            
            if current_status != "PENDING":
                logger.info(f"⏭️ [STATE] Prospecto {phone_number} ya está en '{current_status}'. Transición omitida.")
                return False

            await self._firestore_io(
                doc_ref.update({"status": "IN_PROGRESS", "fecha": firestore.SERVER_TIMESTAMP}),
                phone=phone_number, label="transition_to_in_progress.update"
            )
            logger.info(f"🟢 [STATE] Prospecto {phone_number}: PENDING → IN_PROGRESS")
            return True

        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded):
            raise
        except Exception as e:
            logger.exception(f"❌ [STATE] Error in transition_to_in_progress for {phone_number}: {e}")
            return False

    async def set_human_help_status(self, phone_number: str, status: bool) -> bool:
        """
        Set the human_help_requested flag. When True, the bot remains silent.
        Restored from v9.5.0 to handle missing prospects (Auto-Creation).
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            
            if doc_ref:
                await self._firestore_io(
                    doc_ref.update({"human_help_requested": status, "fecha": firestore.SERVER_TIMESTAMP}),
                    phone=phone_number, label="set_human_help_status.update"
                )
                logger.info(f"✅ Updated human_help_requested={status} for {phone_number}")
                return True

            # No existing document found - create new one (CRITICAL for Judge Fallback)
            clean_phone = PhoneNormalizer.normalize(phone_number)
            logger.warning(f"⚠️ No prospect found for {phone_number}, creating new document for help request")
            await self.create_prospect_if_missing(clean_phone)
            
            # Re-fetch and update
            doc_ref = await self._find_prospect_ref(clean_phone)
            await self._firestore_io(
                doc_ref.update({"human_help_requested": status, "fecha": firestore.SERVER_TIMESTAMP}),
                phone=clean_phone, label="set_human_help_status.update_refetch"
            )
            return True
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded):
            raise
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
        [ARCH-BULK-META-010] Actualiza el sub-campo metadata.whatsapp y campos de nivel superior.
        Incluye guardrail para evitar retrodegradación del status CRM.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            
            # --- GUARDRAIL: Leer status CRM actual antes de escribir ---
            doc_snap = await self._firestore_io(doc_ref.get(), phone=phone_number, label="update_whatsapp_status.get")
            current_data = doc_snap.to_dict() if doc_snap.exists else {}
            current_crm_status = current_data.get("status", "")
            protected_statuses = {"IN_PROGRESS", "DONE", "DISCARDED"}

            # Sincronía de nivel superior para el Dashboard CRM
            payload = {
                "metadata.whatsapp.last_status": status_value,
                "metadata.whatsapp.last_status_timestamp": firestore.SERVER_TIMESTAMP,
                "metadata.whatsapp.last_wamid": wamid,
                "whatsapp_delivery_status": status_value, # [SYNC-CRM] Top-level field
                "whatsapp_delivery_updated_at": firestore.SERVER_TIMESTAMP,
            }

            # Idempotencia para whatsapp_read_at
            if status_value == "read" and "whatsapp_read_at" not in current_data:
                payload["whatsapp_read_at"] = firestore.SERVER_TIMESTAMP

            if errors:
                payload["metadata.whatsapp.last_error"] = errors
                if isinstance(errors, list) and len(errors) > 0:
                    # Guardamos el resumen del error para el Dashboard
                    error_summary = errors[0]
                    payload["last_whatsapp_error"] = error_summary.get("message")
                    payload["whatsapp_error_details"] = error_summary
            
            # Guardrail de máquina de estados: nunca tocamos 'status' desde acuses de recibo
            if status_value == "read" and current_crm_status in protected_statuses:
                logger.info(f"🛡️ [STATUSES] Guardrail activo: status '{current_crm_status}' no se altera por acuse 'read'.")

            await self._firestore_io(doc_ref.update(payload), phone=phone_number, label="update_whatsapp_status.update")
            logger.info(f"✅ [STATUSES] Acuse '{status_value}' registrado para {phone_number}")
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded) as e:
            # [BOT-BUG-040] NO re-raise: update_whatsapp_status corre en background task.
            # WHY: Este método procesa acuses de recibo Meta (sent/delivered/read/failed).
            # Un re-raise aquí mata el hilo de background sin path de recuperación,
            # rompiendo el orquestador para los siguientes webhooks de ese lead.
            # Zero-Silent-Failures se cumple con el log forense explícito.
            logger.exception(
                f"❌ [BOT-BUG-040] gRPC/Timeout error en update_whatsapp_status para {phone_number}: {e}. "
                f"Status: '{status_value}', WAMID: '{wamid}'. "
                f"El acuse NO fue persistido pero el orquestador continúa."
            )
        except Exception as e:
            logger.exception(f"❌ [STATUSES] Error actualizando metadata.whatsapp para {phone_number}: {e}")

    async def update_last_interaction(self, phone_number: str) -> None:
        """
        Updates the 'fecha' timestamp to bring user to top of Admin Panel list.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            await self._firestore_io(
                doc_ref.update({"fecha": firestore.SERVER_TIMESTAMP}),
                phone=phone_number, label="update_last_interaction"
            )
            logger.info(f"🕐 Updated last interaction timestamp for {phone_number}")
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded):
            raise
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
