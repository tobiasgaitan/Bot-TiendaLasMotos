"""
Memory Service - CRM Integration & Long-Term Memory
Handles prospect data retrieval and conversation summary updates in Firestore.
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, Set
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

    def __init__(self, db: firestore.AsyncClient):
        """
        Initialize the memory service.

        Args:
            db: Firestore client instance
        """
        self._db = db
        self._pending_tasks: Set[asyncio.Task] = set()
        logger.info("🧠 MemoryService initialized with AsyncClient & Task Tracker (v6.9.6)")

    def _track_task(self, coro) -> asyncio.Task:
        """
        Register a coroutine as a tracked task to ensure visibility during shutdown.
        """
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
        return task

    async def shutdown(self, timeout: int = 8) -> None:
        """
        Graceful Shutdown Mechanism (Atomic Persistence Flush).
        Waits for all tracked tasks to complete before allowing process termination.
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
            logger.error(f"❌ [SHUTDOWN] Error during persistence flush: {e}")

    async def _find_prospect_ref(self, phone_number: str) -> Optional[firestore.AsyncDocumentReference]:
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
            doc_snapshot = await doc_ref.get()
            if doc_snapshot.exists:
                return doc_ref
            
            # 2. Try by field query (Multi-format CRM support)
            variations = [clean_phone, f"57{clean_phone}", f"+57{clean_phone}", f"+{clean_phone}"]
            query = prospectos_ref.where("celular", "in", variations).limit(1)
            docs = await query.get()
            if docs:
                return docs[0].reference
                
            return None
        except Exception as e:
            logger.error(f"❌ Error in _find_prospect_ref for {phone_number}: {e}")
            return None

    async def get_prospect_data(self, phone_number: str) -> Dict[str, Any]:
        """
        Garantía de Verdad (Linear Blocking): Recupera datos frescos del prospecto.
        Refactored to native Async I/O (v6.9.6).
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            if doc_ref:
                doc_snap = await doc_ref.get()
                if doc_snap.exists:
                    data = doc_snap.to_dict()
                    prospect_data = {
                        "nombre": data.get("nombre") or data.get("name") or "",
                        "ciudad": data.get("ciudad") or data.get("city") or "",
                        "moto_interes": data.get("moto_interes") or data.get("motoInteres") or data.get("moto_interest", ""), 
                        "moto_confirmada": data.get("moto_confirmada") or data.get("motoConfirmada", False),
                        "forma_pago": data.get("forma_pago") or data.get("formaPago") or "",
                        "summary": data.get("ai_summary") or data.get("summary"),
                        "human_help_requested": data.get("human_help_requested", False),
                        "survey_state": data.get("survey_state"),
                        "exists": True,
                        "habeas_data_sent": data.get("habeas_data_sent", False),
                        "habeas_data": data.get("habeas_data") or data.get("habeasData") or data.get("habeas_data_accepted", False),
                        "servicios_publicos": data.get("servicios_publicos") or data.get("serviciosPublicos", None),
                        "total_tokens_consumed": data.get("total_tokens_consumed", 0),
                        "session_cost_usd": data.get("session_cost_usd", 0.0)
                    }
                    return prospect_data
            
            return {
                "nombre": "", "ciudad": "", "moto_interes": "",
                "forma_pago": "", "summary": "",
                "human_help_requested": False, "survey_state": None, "exists": False,
                "habeas_data_sent": False, 
                "habeas_data": False,
                "servicios_publicos": None,
                "total_tokens_consumed": 0, "session_cost_usd": 0.0
            }
        except Exception as e:
            logger.error(f"❌ Error in get_prospect_data for {phone_number}: {e}")
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
            
            # --- INYECCIÓN DE CONTEXTO PREVIO (UNE v7.0.0 Unification) ---
            prospect_data = await self.get_prospect_data(phone_number)
            moto_interes_prev = prospect_data.get("moto_interes", "") if prospect_data else ""

            # 1. AI Extraction (Async)
            summary_data = await ai_brain.generate_summary(
                conversation_text, 
                last_bot_question=last_bot_question,
                session_id=phone_number,
                previous_moto_interes=moto_interes_prev
            )
            
            # 2. Firestore Persistence (Blocking Await for Data Integrity)
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
        Native Async Implementation (v6.9.6)
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            logger.info(f"💾 Updating prospect summary for {clean_phone} (ASYNC)")

            doc_ref = await self._find_prospect_ref(phone_number)
            
            if not doc_ref:
                logger.warning(f"⚠️ No prospect found to update for {clean_phone}")
                new_doc_ref = self._db.collection("prospectos").document(clean_phone)
                await new_doc_ref.set({
                    "celular": f"+57{clean_phone}",
                    "ai_summary": summary_text,
                    "chatbot_status": "ACTIVE",
                    "created_at": firestore.SERVER_TIMESTAMP,
                    "updated_at": firestore.SERVER_TIMESTAMP
                })
                logger.info(f"✅ Created new prospect document for {clean_phone}")
                return

            doc_snap = await doc_ref.get()
            current_data = doc_snap.to_dict()

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

            # 3. Media Vault Update (if present)
            if extracted_data and "media_url" in extracted_data:
                update_data["media_vault"] = firestore.ArrayUnion([extracted_data["media_url"]])
                logger.info(f"📸 Adding image to media_vault for {clean_phone}")

            logger.info(f"💾 [MEMORY DUMP] Final payload to Firestore for {clean_phone}")
            await doc_ref.update(update_data)
            logger.info(f"✅ Successfully updated prospect summary for {clean_phone}")

        except Exception as e:
            logger.error(f"❌ Error updating prospect summary for {phone_number}: {str(e)}", exc_info=True)

    def _merge_extracted_data(self, current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        """
        Applies Non-Destructive Merge Strategy (UNE v7.0.0).
        
        Rules:
        - NO_TRANSLATION: Keys are used directly as provided by the AI (standardized snake_case).
        - PRESERVE_IF_HISTORIC_VALID: Incoming null/empty does NOT overwrite existing valid data.
        - LATCH_TRUE_ONLY: Boolean flags cannot transition from True to False.
        """
        merged = {}
        
        def is_valid(val):
            if val is None: return False
            if isinstance(val, bool): return True
            s_val = str(val).strip().lower()
            return s_val not in ["", "null", "none", "n/a", "undefined"]

        # List of fields that once True, must never revert to False (Legal/Business Guardrails)
        latch_fields = ["habeas_data_sent", "habeas_data", "moto_confirmada", "gas_natural"]

        # 1. Merge and Sanitize (Directly using incoming keys)
        for key, val in incoming.items():
            # Boolean Casting for critical flags
            if key == "habeas_data":
                val = bool(val)

            # [JSON Voorhees v6.9.6] PII Guardrail: Truncate to 50 chars
            if key in ["nombre", "ciudad"] and isinstance(val, str):
                val = val[:50].strip()
                logger.debug(f"🛡️ PII Guardrail: Truncated {key} to 50 chars.")

            # Apply Merge Logic
            if key in latch_fields:
                # Rule: Once True, never False
                existing_val = current.get(key)
                if existing_val is True:
                    merged[key] = True
                else:
                    merged[key] = val
            elif is_valid(val):
                # Rule: Update only if new value is valid
                merged[key] = val
            else:
                # Rule: Preserve numeric or non-null values if they exist
                # If we don't handle it here, it won't be in 'merged' and thus not updated.
                pass

        return merged

    async def update_last_interaction(self, phone_number: str) -> None:
        """
        Updates only the fecha timestamp to bring user to top of admin list.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            if doc_ref:
                await doc_ref.update({"fecha": firestore.SERVER_TIMESTAMP})
                logger.info(f"✅ TIMESTAMP UPDATED for {phone_number}")
        except Exception as e:
            logger.error(f"❌ Error updating timestamp: {e}", exc_info=True)

    async def set_human_help_status(self, phone_number: str, status: bool) -> None:
        """
        Set the human_help_requested flag for a prospect in Firestore.
        Native Async Implementation (v6.9.6)
        """
        try:
            logger.info(f"🔧 Setting human_help_requested={status} for {phone_number} (ASYNC)")

            doc_ref = await self._find_prospect_ref(phone_number)
            
            if doc_ref:
                await doc_ref.update({
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
            await new_doc_ref.set({
                "celular": f"+57{normalized_phone}",
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

    async def create_prospect_if_missing(self, phone_number: str) -> bool:
        """
        Ensures a prospect document exists for the given phone number.
        Native Async Implementation (v6.9.6)
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            logger.info(f"💾 Ensuring prospect existence for {clean_phone} (ASYNC)...")
            
            prospectos_ref = self._db.collection("prospectos")
            doc_ref = prospectos_ref.document(clean_phone)
            doc_snap = await doc_ref.get()
            
            if doc_snap.exists:
                return False
                
            new_data = {
                "celular": f"+57{clean_phone}",
                "nombre": "",
                "ciudad": "",
                "moto_interes": "", # UNE v7.0.0 Standard
                "forma_pago": "",
                "chatbot_status": "ACTIVE",
                "status": "PENDING",
                "source": "whatsapp_bot",
                "human_help_requested": False,
                "habeas_data_sent": False,
                "habeas_data": False,
                "servicios_publicos": None,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
            await doc_ref.set(new_data)
            logger.info(f"✅ Created NEW prospect doc for {clean_phone} (ASYNC)")

            # --- ZOMBIE SESSION PURGE ---
            try:
                session_ref = self._db.collection("mensajeria").document("whatsapp").collection("sesiones").document(clean_phone)
                await session_ref.delete()
                logger.info(f"🗑️ Zombie session purged for new prospect {clean_phone} (ASYNC)")
            except Exception as e:
                logger.warning(f"⚠️ Failed to purge zombie session for {clean_phone}: {e}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating prospect for {phone_number}: {e}", exc_info=True)
            return False

    async def _delete_collection_batched(self, collection_ref, batch_size=400):
        """
        Helper to delete all documents in a collection (ASYNC).
        """
        total_deleted = 0
        while True:
            docs_stream = collection_ref.limit(batch_size).stream()
            docs = []
            async for doc in docs_stream:
                docs.append(doc)
            
            if not docs:
                break
                
            batch = self._db.batch()
            count = 0
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
            
            await batch.commit()
            total_deleted += count
            
            if count < batch_size:
                break
        return total_deleted

    async def delete_prospect_completely(self, phone_number: str) -> int:
        """
        Nuclear wipe of a prospect and their history (ASYNC).
        Handles multi-format schema matches for frontend CRM compatibility.
        """
        try:
            deleted = 0
            clean_phone = PhoneNormalizer.normalize(phone_number)

            # --- 1. PURGE MENSAJERIA SESSIONS (AI History) ---
            try:
                session_ref = self._db.collection("mensajeria").document("whatsapp").collection("sesiones").document(clean_phone)
                history_ref = session_ref.collection("historial")
                count = await self._delete_collection_batched(history_ref)
                await session_ref.delete()
                deleted += count + 1
            except Exception as e:
                logger.warning(f"⚠️ Failed to purge mensajeria session for {clean_phone}: {e}")
            
            # --- 2. PURGE PROSPECT DATA (CRM MULTI-SCAN) ---
            prospectos_ref = self._db.collection("prospectos")
            refs_to_delete = {}
            
            # A) Búsqueda Legacy (Por ID directo)
            doc_ref = prospectos_ref.document(clean_phone)
            doc_snap = await doc_ref.get()
            if doc_snap.exists:
                refs_to_delete[doc_ref.id] = doc_ref
                
            # B) Búsqueda Nativa (Inyección Frontend)
            raw_target = str(phone_number).strip()
            variaciones = [raw_target, clean_phone, f"+{raw_target}"]
            if clean_phone:
                variaciones.extend([f"+57{clean_phone}", f"57{clean_phone}"])
                
            # Filtrar y dedup (límite de Firestore es 10 para IN array)
            variaciones_unicas = list(set([v for v in variaciones if v]))[:10]
            
            if variaciones_unicas:
                query = prospectos_ref.where("celular", "in", variaciones_unicas)
                docs = await query.get()
                for doc in docs:
                    refs_to_delete[doc.id] = doc.reference
                    
            # C) Aniquilación Atómica
            for ref_id, ref in refs_to_delete.items():
                logger.info(f"🧹 [NUCLEAR WIPE] Removing Document & Histories for CRM record {ref_id}")
                history_ref = ref.collection("historial")
                count = await self._delete_collection_batched(history_ref)
                await ref.delete()
                deleted += count + 1

            return deleted
        except Exception as e:
            logger.error(f"❌ Error in nuclear prospect delete for {phone_number}: {e}", exc_info=True)
            return deleted

    async def save_message(self, phone_number: str, role: str, content: str, blocking: bool = False) -> None:
        """
        Save a message to the chat history sub-collection.
        
        Path: mensajeria/whatsapp/sesiones/{phone}/historial
        
        Args:
            phone_number: User's phone number
            role: 'user' or 'model'
            content: Message text
            blocking: If True, awaits Firestore confirmation. If False, runs track_task.
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
            
            # Application of blocking/non-blocking strategy
            coro = history_ref.add(message_data)
            if blocking:
                await coro
            else:
                self._track_task(coro)
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
            docs_stream = query.stream()
            
            messages = []
            async for doc in docs_stream:
                data = doc.to_dict()
                messages.append({
                    "role": data.get("role"),
                    "content": data.get("content"),
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
            docs_stream = history_ref.stream()
            count = 0
            async for doc in docs_stream:
                batch.delete(doc.reference)
                count += 1
                if count >= 400: # Firestore limit
                    await batch.commit()
                    batch = self._db.batch()
                    count = 0
            await batch.commit()
            
            logger.info(f"🧠 AI Memory cleared for {clean_phone}")
            return True
        except Exception as e:
            logger.error(f"❌ Error clearing memory for {phone_number}: {e}")
            return False

    async def update_whatsapp_status(
        self,
        phone_number: str,
        status_value: str,
        wamid: str,
        errors: list | None = None,
    ) -> None:
        """
        [ARCH-BULK-META-010] Actualiza el sub-campo metadata.whatsapp del prospecto
        y el campo top-level `whatsapp_delivery_status` con el último acuse de recibo
        de Meta (sent/delivered/read/failed).

        WHY dot-notation: Firestore interpreta 'metadata.whatsapp.last_status' como
        un path de campo anidado. Esto garantiza que otros campos dentro de 'metadata'
        no sean sobreescritos (merge-safe update).

        WHY top-level `whatsapp_delivery_status`: El dashboard de campañas necesita
        un campo plano para filtrar/ordenar prospectos por estado de entrega sin
        depender de la estructura anidada de metadata.

        WHY guardrail IN_PROGRESS: Un acuse de entrega 'read' no debe retrodegradar
        el `status` CRM si el prospecto ya respondió y está en IN_PROGRESS, DONE
        o cualquier estado posterior. Los campos de delivery son ortogonales al
        status de la máquina de estados del CRM.

        Args:
            phone_number: Teléfono del destinatario (cualquier formato — _find_prospect_ref normaliza).
            status_value: Literal del acuse — 'sent', 'delivered', 'read' o 'failed'.
            wamid: ID del mensaje al que corresponde el acuse (wa_message_id).
            errors: Array de objetos de error de Meta (solo presente si status='failed').
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            if not doc_ref:
                logger.warning(
                    f"⚠️ [STATUSES] Prospecto no encontrado para acuse '{status_value}' de {phone_number}. "
                    f"El webhooks se procesó correctamente pero no hay doc de Firestore que actualizar."
                )
                return

            # --- GUARDRAIL: Leer status CRM actual antes de escribir ---
            # WHY: Si el prospecto ya está en IN_PROGRESS (o más avanzado), el acuse
            # de entrega 'read' no debe retrodegradar ningún campo de estado CRM.
            # Los campos whatsapp_delivery_status / whatsapp_error_details son
            # ortogonales y siempre se actualizan.
            doc_snap = await doc_ref.get()
            current_data = doc_snap.to_dict() if doc_snap.exists else {}
            current_crm_status = current_data.get("status", "")
            protected_statuses = {"IN_PROGRESS", "DONE", "DISCARDED"}

            # Dot-notation: no sobreescribe otros campos de metadata
            update_payload: dict = {
                "metadata.whatsapp.last_status": status_value,
                "metadata.whatsapp.last_status_timestamp": firestore.SERVER_TIMESTAMP,
                "metadata.whatsapp.last_wamid": wamid,
                # Top-level para el dashboard de campañas (lectura directa sin path anidado)
                "whatsapp_delivery_status": status_value,
                "whatsapp_delivery_updated_at": firestore.SERVER_TIMESTAMP,
            }

            # --- Idempotencia para whatsapp_read_at ---
            if status_value == "read" and "whatsapp_read_at" not in current_data:
                update_payload["whatsapp_read_at"] = datetime.utcnow()
                logger.info(f"⏱️ [STATUSES] Inyectando whatsapp_read_at por primera vez para {phone_number}")

            # --- Error details: solo si Meta reportó un fallo ---
            if status_value == "failed" and errors:
                # Preservamos el array completo para auditoría forense.
                # Ejemplo Meta: [{"code": 131026, "title": "Message Undeliverable", ...}]
                error_summary = errors[0] if len(errors) == 1 else errors
                update_payload["whatsapp_error_details"] = error_summary
                logger.warning(
                    f"⚠️ [STATUSES] Fallo de entrega reportado por Meta para {phone_number}: {error_summary}"
                )

            # --- Guardrail de máquina de estados ---
            # Registramos solo para auditoría interna; nunca tocamos el campo 'status'.
            if status_value == "read" and current_crm_status in protected_statuses:
                logger.info(
                    f"🛡️ [STATUSES] Guardrail activo: status CRM '{current_crm_status}' para {phone_number} "
                    f"no se sobrescribe por acuse 'read'. Solo se actualiza whatsapp_delivery_status."
                )

            await doc_ref.update(update_payload)
            logger.info(
                f"✅ [STATUSES] Acuse '{status_value}' registrado para {phone_number} (WAMID: {wamid})"
            )
        except Exception as e:
            logger.error(
                f"❌ [STATUSES] Error actualizando metadata.whatsapp para {phone_number}: {str(e)}",
                exc_info=True,
            )


    async def transition_to_in_progress(self, phone_number: str) -> bool:
        """
        [ARCH-BULK-META-010] Transición atómica PENDING → IN_PROGRESS.

        WHY: El orquestador de campaña (admin.py) ya NO actualiza el status al enviar
        el template. La transición ocurre aquí cuando se recibe la primera respuesta
        real del usuario (webhook de tipo 'messages').

        GUARDRAIL: Verifica el status actual antes de escribir para evitar sobreescrituras
        innecesarias en prospectos que ya están en IN_PROGRESS, DONE o DISCARDED.

        Args:
            phone_number: Teléfono del usuario que respondió.

        Returns:
            True si se realizó la transición (era PENDING), False si no era necesaria.
        """
        try:
            doc_ref = await self._find_prospect_ref(phone_number)
            if not doc_ref:
                logger.warning(f"⚠️ [STATE] No doc para transición de {phone_number}")
                return False

            # Verificación bloqueante: leer status actual antes de decidir
            doc_snap = await doc_ref.get()
            if not doc_snap.exists:
                return False

            current_status = doc_snap.to_dict().get("status", "")
            if current_status != "PENDING":
                logger.info(
                    f"⏭️ [STATE] Prospecto {phone_number} ya está en '{current_status}'. "
                    f"Transición PENDING→IN_PROGRESS omitida."
                )
                return False

            # Transición atómica: await bloqueante garantiza commit antes de continuar
            await doc_ref.update({
                "status": "IN_PROGRESS",
                "updated_at": firestore.SERVER_TIMESTAMP,
            })
            logger.info(
                f"🟢 [STATE] Prospecto {phone_number}: PENDING → IN_PROGRESS (primera respuesta recibida)"
            )
            return True

        except Exception as e:
            logger.error(
                f"❌ [STATE] Error en transición PENDING→IN_PROGRESS para {phone_number}: {str(e)}",
                exc_info=True
            )
            return False

# Singleton instance (will be initialized in main.py with db)
memory_service: Optional["MemoryService"] = None

def init_memory_service(db: firestore.AsyncClient) -> None:
    """
    Initialize the global memory service instance.

    Args:
        db: Firestore client instance
    """
    global memory_service
    memory_service = MemoryService(db)
    logger.info("🧠 Global MemoryService initialized")
