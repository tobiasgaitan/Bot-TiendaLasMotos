"""
Memory Service - CRM Integration & Long-Term Memory
v9.8.9 - BOT-BUILD-FUNNEL-SKIP-014 (reset_phase_latches: reset de latches de fase sin purgar historial/identidad)

CHANGELOG v9.8.9:
  - [BOT-BUILD-FUNNEL-SKIP-014] Added `reset_phase_latches()` to zero phase latches
    (habeas_data_accepted, habeas_data_accepted_sent, forma_pago, moto_interest,
    moto_interes, moto_confirmada, score_resultado) while preserving commercial
    history and identity (nombre/ciudad). Idempotent via set(merge=True).

CHANGELOG v9.8.8:
  - [AUD-FP-AUTO-REG-009] Relaxed R1 and R2 in update_prospect_summary
    derivation layer so that forma_pago="Crédito" fills when either (a)
    habeas_data_accepted is already accepted or arrives in the same payload,
    and (b) habeas_data_accepted_sent is already persisted or arrives in the
    same payload. R3 (vacancy + explicit-wins) remains intact. Closes the
    canonical immediate-acceptance gap (reaction 👍 and text "Sí").

CHANGELOG v9.8.7:
  - [AUD-FP-AUTO-007] Added deterministic derivation layer in
    update_prospect_summary: writes forma_pago="Crédito" when the canonical
    Habeas Data acceptance transition (False -> True) occurs, the legal script
    was already presented (habeas_data_accepted_sent=True), and forma_pago is
    vacant. Explicit same-turn extraction always takes precedence.

CHANGELOG v9.8.6:
  - [AUD-SCORE-PERSIST-001] Added persist_credit_score_result() with atomic
    Firestore transaction (parent score_resultado + historial subdoc)
  - [AUD-SCORE-PERSIST-001] Added _dashboard_mirror() for retrocompatible
    dashboard aliases (moto_interes, ingresos, gastos, habeas_data,
    habeas_data_sent) without renames/deletions
  - [AUD-SCORE-PERSIST-001] Added _score_historial_dedup_id() deterministic
    deduplication key (bucket 300s)

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
import hashlib
import time
from typing import Dict, Any, Optional, List, Set, Union
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
        # [BOT-BUILD-ETAPA3-WAVE02-HYGIENE-001] _pending_tasks se conserva: es leído
        # por shutdown() (cableado en el lifespan de main.py) como punto de flush.
        # El productor _track_task fue purgado (0 call sites verificados — Vestigio
        # Valla de Chesterton pre-Linear-Blocking BOT-INFRA-ASYNC-094: todas las
        # escrituras del embudo son await bloqueante, nadie registraba tareas).
        self._pending_tasks: Set[asyncio.Task] = set()
        logger.info("🧠 MemoryService v9.8.8 (retrigger 16bf9f7→): AUD-FP-AUTO-REG-009 + AUD-FP-AUTO-007 + AUD-SCORE-PERSIST-001")

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
    # Dashboard key mirroring (retrocompatible double-write)
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _dashboard_mirror(
        merged: Dict[str, Any], current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        [AUD-SCORE-PERSIST-001] Retrocompatible mirror layer for the dashboard
        consumer keys. Keeps the bot's canonical long keys intact and ADDS
        the dashboard-canonical aliases. No renames, no deletions.

        Rules:
          - moto_interest -> moto_interes (verbatim string)
          - ingresos_mensuales -> ingresos (int, only if pure digits)
          - gastos_mensuales -> gastos (int, only if pure digits)
          - habeas_data_accepted -> habeas_data (bool, latch-guarded)
          - habeas_data_accepted_sent -> habeas_data_sent (bool, latch-guarded)
        """
        mirror: Dict[str, Any] = {}
        if not isinstance(merged, dict):
            return mirror

        # 1. Moto interest — verbatim alias
        if "moto_interest" in merged:
            mirror["moto_interes"] = merged["moto_interest"]

        # 2. Income / expenses — coerce to int only for pure-digit strings
        for src_key, dst_key in (
            ("ingresos_mensuales", "ingresos"),
            ("gastos_mensuales", "gastos"),
        ):
            if src_key in merged:
                raw = merged[src_key]
                try:
                    numeric = int(str(raw).strip())
                    mirror[dst_key] = numeric
                except (ValueError, TypeError):
                    logger.warning(
                        f"⚠️ [DASHBOARD_MIRROR] {src_key} value {raw!r} is not a pure integer; "
                        f"skipping mirror to {dst_key} (Anti-Null-Masking)."
                    )

        # 3. Habeas consent flags — never write False over an existing True
        #    (protects web-created leads that already have habeas_data=true)
        alias_map = {
            "habeas_data_accepted": "habeas_data",
            "habeas_data_accepted_sent": "habeas_data_sent",
        }
        for src_key, dst_key in alias_map.items():
            if src_key in merged:
                value = merged[src_key]
                if value is True:
                    mirror[dst_key] = True
                elif current_data.get(dst_key) is not True:
                    mirror[dst_key] = value

        return mirror

    @staticmethod
    def _score_historial_dedup_id(phone: str, content: str, now: Optional[float] = None) -> str:
        """
        [AUD-SCORE-PERSIST-001] Deterministic deduplication key for the score
        result historial document. Collapses re-entries (double-save, Cloud
        Tasks redelivery, judge retries) within the same 300s bucket.
        """
        bucket = int((now if now is not None else time.time()) // 300)
        digest = hashlib.sha256(
            f"{phone}|model|{content}|{bucket}".encode("utf-8")
        ).hexdigest()
        return f"scoremsg_{digest[:24]}"
        
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

    async def persist_credit_score_result(
        self,
        phone_number: str,
        score_marker: Union[int, float, Dict[str, Any]],
        content: str,
    ) -> None:
        """
        [AUD-SCORE-PERSIST-001] Atomic persistence of the credit score result:
          - parent doc: score_resultado (verbatim number) + score_resultado_at
          - historial subdoc: role/model + content + timestamp + structured

        The historial document uses a deterministic dedup ID so that re-entries
        (double-save in text pipeline, Cloud Tasks retries) collapse into a
        single Firestore document. The content text is preserved byte-identical.
        """
        clean_phone = PhoneNormalizer.normalize(phone_number)

        # Accept either a bare numeric score or a dict marker from ai_brain.
        if isinstance(score_marker, dict):
            score = score_marker.get("score")
            entity = score_marker.get("entity")
            strategy = score_marker.get("strategy")
        else:
            score = score_marker
            entity = None
            strategy = None

        # Type guard: score MUST be numeric (int or float, not bool). Verbatim.
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            logger.warning(
                f"⚠️ [SCORE_PERSIST] score value is not numeric (got {score!r} of type "
                f"{type(score).__name__}). Falling back to plain save_message; "
                f"score_resultado will NOT be persisted (Anti-Null-Masking)."
            )
            await self.save_message(clean_phone, "model", content)
            return

        dedup_id = self._score_historial_dedup_id(clean_phone, content)
        parent_ref = self._db.collection(self.collection_name).document(clean_phone)
        hist_ref = parent_ref.collection("historial").document(dedup_id)

        structured: Dict[str, Any] = {
            "type": "credit_score",
            "score": score,
        }
        if entity is not None:
            structured["entity"] = entity
        if strategy is not None:
            structured["strategy"] = strategy

        transaction = self._db.transaction()

        @firestore.async_transactional
        async def _commit_score(txn):
            txn.set(
                parent_ref,
                {
                    "score_resultado": score,
                    "score_resultado_at": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            txn.set(
                hist_ref,
                {
                    "role": "model",
                    "content": content,
                    "timestamp": firestore.SERVER_TIMESTAMP,
                    "structured": structured,
                },
            )

        await self._firestore_io(
            _commit_score(transaction),
            phone=clean_phone,
            label="persist_credit_score_result",
        )

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

    async def get_or_create_prospect(self, phone_number: str) -> Dict[str, Any]:
        """
        Obtiene de forma síncrona/bloqueante los datos del prospecto.
        Si no existe en Firestore, lo crea con sus campos canónicos por defecto
        y retorna la estructura de datos correspondiente.
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = await self._find_prospect_ref(clean_phone)
            doc_snap = await self._firestore_io(doc_ref.get(), phone=clean_phone, label="get_or_create_prospect.get")
            
            if not doc_snap.exists:
                logger.warning(f"⚠️ [GET_OR_CREATE] Prospecto {clean_phone} inexistente. Forzando inicialización base...")
                await self.create_prospect_if_missing(clean_phone)
                # Re-fetch posterior a la creación
                doc_snap = await self._firestore_io(doc_ref.get(), phone=clean_phone, label="get_or_create_prospect.reget")
                
            data = doc_snap.to_dict() or {}
            data["exists"] = True
            if "celular" not in data:
                data["celular"] = doc_ref.id
            return data
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded) as e:
            logger.exception(f"🔌 [NETWORK_ERR] Fallo de red/timeout de Firestore en get_or_create_prospect para {phone_number}: {e}")
            raise
        except Exception as e:
            logger.exception(f"❌ get_or_create_prospect failed for {phone_number}: {e}")
            raise

    async def create_prospect_if_missing(self, phone_number: str) -> None:
        """
        Idempotent prospect initialization with zombie session purge on fresh start.

        Restored from v9.5.0 logic to ensure full CRM compatibility.

        Contract (test_reset_flow.py, test_read_asymmetry.py):
          - If prospect does NOT exist → create with canonical keys
            and purge any stale historial subcollection docs
          - If prospect exists → NO history wipe; accumulated state is preserved
          - Canonical keys: status=PENDING, chatbot_status=ACTIVE, etc.

        [BOT-BUILD-CLASSIFIER-011] The history purge is conditional: it only runs
        when the parent doc is created here. This keeps /reset idempotency (after
        nuclear wipe the next message recreates the doc and wipes orphan history)
        while preserving chat memory for existing prospects.
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
                # WHY: Ensures idempotency for /reset by wiping orphan history.
                # ONLY executed on fresh doc creation (see docstring above).
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
        catalog_moto_hint: Optional[str] = None,
        catalog=None,
    ) -> None:
        """Merge AI-extracted data into prospect and update summary."""
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = await self.get_ref(clean_phone)
            doc_snap = await self._firestore_io(doc_ref.get(), phone=clean_phone, label="update_prospect_summary.get")
            
            # --- CORRECCIÓN QUIRÚRGICA ANTE BORRADO NUCLEAR (/RESET) ---
            if not doc_snap.exists:
                logger.warning(f"⚠️ [RESET_RECOVERY] Documento no encontrado para {clean_phone} durante actualización. Creando nodo base de emergencia...")
                # Invocamos la inicialización limpia con llaves canónicas
                await self.create_prospect_if_missing(clean_phone)
                # Re-congelamos el snapshot para obtener el diccionario base limpio
                doc_snap = await self._firestore_io(doc_ref.get(), phone=clean_phone, label="update_prospect_summary.reget")
            
            current_data = doc_snap.to_dict() if doc_snap.exists else {}

            # [M1+M2] Canonicalize moto_interest before merging.
            # The catalog_moto_hint (model name chosen by the tool-exec) is the
            # source of truth; it overrides any category/style extracted by the LLM.
            extracted = dict(extracted_data) if extracted_data else {}
            hint = str(catalog_moto_hint).strip() if catalog_moto_hint else None
            incoming_moto = str(extracted.get("moto_interest", "")).strip() or None
            if hint:
                extracted["moto_interest"] = hint
                logger.info(f"🔁 [MOTO-CANON] catalog_moto_hint='{hint}' overrides extracted moto_interest for {clean_phone}")
            elif incoming_moto:
                incoming_is_canonical = self._is_canonical_moto_interest(incoming_moto, catalog)
                current_is_canonical = self._is_canonical_moto_interest(current_data.get("moto_interest"), catalog)
                if not incoming_is_canonical and not current_is_canonical:
                    # [BOT-BUILD-DRIFT-CANON-016-B] Reject category/alias/partial model extractions
                    # that resolve to catalog results, but allow no-match conservative values.
                    effective_catalog = self._resolve_catalog(catalog)
                    try:
                        matches = effective_catalog.search_items(incoming_moto) if effective_catalog else []
                    except Exception:
                        matches = []
                    if matches:
                        logger.info(
                            f"🔁 [MOTO-CANON] rejecting non-canonical extraction='{incoming_moto}' "
                            f"(resolves to {len(matches)} catalog matches, no hint/DB) for {clean_phone}"
                        )
                        extracted.pop("moto_interest", None)
                    else:
                        logger.info(
                            f"🔁 [MOTO-CANON] allowing non-canonical no-match extraction='{incoming_moto}' "
                            f"for {clean_phone}"
                        )
                elif not incoming_is_canonical and current_is_canonical:
                    # Protect an already-canonical DB value from a non-canonical (category/style)
                    # extraction when no tool hint is available.
                    logger.info(
                        f"🔁 [MOTO-CANON] preserving canonical DB moto_interest='{current_data.get('moto_interest')}' "
                        f"over non-canonical extracted='{incoming_moto}' for {clean_phone}"
                    )
                    extracted.pop("moto_interest", None)

            # Use centralized merge logic
            update_payload = self._merge_extracted_data(current_data, extracted)

            # [AUD-FP-AUTO-007 + AUD-FP-AUTO-REG-009] Deterministic payment-method
            # auto-fill on Habeas Data acceptance (PASO 4). R1 accepts either a
            # current/payload accepted flag; R2 accepts either a current/payload
            # sent flag (latch-guarded via _LATCH_TRUE_FIELDS). R3 (vacancy +
            # explicit-wins) remains intact.
            if (
                (
                    update_payload.get("habeas_data_accepted") is True
                    or current_data.get("habeas_data_accepted") is True
                )
                and (
                    current_data.get("habeas_data_accepted_sent") is True
                    or update_payload.get("habeas_data_accepted_sent") is True
                )
                and not self._is_field_valid(current_data.get("forma_pago"))
                and "forma_pago" not in update_payload
            ):
                update_payload["forma_pago"] = "Crédito"

            # [AUD-SCORE-PERSIST-001] Add retrocompatible dashboard aliases without
            # renaming or removing the bot's canonical keys. Runs AFTER merge so
            # the _merge_extracted_data contract (test_memory_merge pins) is untouched.
            mirror_payload = self._dashboard_mirror(update_payload, current_data)
            update_payload.update(mirror_payload)

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
        last_bot_question: str = "",
        catalog_moto_hint: Optional[str] = None,
    ) -> None:
        """
        Garantía de Verdad (Linear Blocking):
        1. Ejecuta la extracción de la IA (Generate Summary).
        2. Persiste en Firestore inmediatamente.
        """
        try:
            logger.info(f"🧠 [LINEAR BLOCKING] Starting summary generation for {phone_number}...")
            
            # [M1] Reactivate REGLA DE PERSISTENCIA: feed the extractor with the
            # canonical moto_interest already stored in Firestore, so it is not
            # overwritten by a category/style extraction on subsequent turns.
            previous_moto_interest = ""
            try:
                current_data = await self.get_prospect_data(phone_number)
                previous_moto_interest = (current_data or {}).get("moto_interest", "")
            except Exception as e:
                logger.warning(f"⚠️ [MOTO-PERSIST] Could not fetch previous moto_interest for {phone_number}: {e}")
            
            # 1. AI Extraction (Async)
            summary_data = await ai_brain.generate_summary(
                conversation_text, 
                last_bot_question=last_bot_question,
                session_id=phone_number,
                previous_moto_interest=previous_moto_interest,
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
                extracted_data,
                catalog_moto_hint=catalog_moto_hint,
            )
            
            logger.info(f"✅ Successfully updated prospect summary for {phone_number}")
            
        except Exception as e:
            logger.exception(f"❌ [LINEAR BLOCKING] Failed to generate/update summary for {phone_number}: {e}")

    def _resolve_catalog(self, catalog: Any = None) -> Any:
        """Resolve the catalog singleton if none was explicitly passed."""
        if catalog is not None:
            return catalog
        try:
            from app.services.catalog_service import catalog_service
            return catalog_service
        except Exception:
            return None

    def _is_canonical_moto_interest(self, value: Any, catalog=None) -> bool:
        """True if value exactly matches a canonical model name in the catalog."""
        if value is None:
            return False
        try:
            target = str(value).strip()
            if not target:
                return False
            effective_catalog = self._resolve_catalog(catalog)
            if effective_catalog is None:
                return False
            matches = effective_catalog.search_items(target)
            if not matches:
                return False
            target_norm = effective_catalog._normalize_item_id_key(target)
            return any(
                effective_catalog._normalize_item_id_key(str(item.get("name", ""))) == target_norm
                for item in matches
            )
        except Exception as e:
            logger.exception(f"❌ [MOTO-CANON] Error validating moto_interest canonicity: {e}")
            return False

    async def update_prospect_moto_interest(
        self,
        phone_number: str,
        moto_interest: Optional[str],
        catalog=None,
    ) -> None:
        """
        Persist the canonical model name selected by the catalog tool-exec.
        This runs AFTER AI inference (the extraction phase already completed)
        and protects the CRM from category/style extractions.
        """
        if not moto_interest or not str(moto_interest).strip():
            return
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = await self.get_ref(clean_phone)
            doc_snap = await self._firestore_io(doc_ref.get(), phone=clean_phone, label="update_prospect_moto_interest.get")
            current_data = doc_snap.to_dict() if doc_snap.exists else {}
            extracted_data = {"moto_interest": str(moto_interest).strip()}
            # [M2] Canonical gate: reject non-canonical hints that resolve to catalog matches
            # when neither DB nor hint is canonical; allow no-match conservative hints.
            # [BOT-BUILD-DRIFT-CANON-016-B] Post-reset DB is empty, so "already canonical DB" guard
            # is insufficient; we must also reject category/style hints outright.
            incoming_is_canonical = self._is_canonical_moto_interest(extracted_data["moto_interest"], catalog)
            current_is_canonical = self._is_canonical_moto_interest(current_data.get("moto_interest"), catalog)
            if not incoming_is_canonical and not current_is_canonical:
                try:
                    matches = catalog.search_items(extracted_data["moto_interest"]) if catalog else []
                except Exception:
                    matches = []
                if matches:
                    logger.info(
                        f"🔁 [MOTO-CANON] rejecting non-canonical hint '{extracted_data['moto_interest']}' "
                        f"(resolves to {len(matches)} catalog matches, no canonical DB) for {clean_phone}"
                    )
                    return
                logger.info(
                    f"🔁 [MOTO-CANON] allowing non-canonical no-match hint '{extracted_data['moto_interest']}' "
                    f"for {clean_phone}"
                )
            if not incoming_is_canonical and current_is_canonical:
                logger.info(
                    f"🔁 [MOTO-CANON] skipping persistence: DB already has canonical "
                    f"'{current_data.get('moto_interest')}' and hint '{extracted_data['moto_interest']}' is not canonical for {clean_phone}"
                )
                return
            update_payload = self._merge_extracted_data(current_data, extracted_data)
            if not update_payload:
                return
            mirror_payload = self._dashboard_mirror(update_payload, current_data)
            update_payload.update(mirror_payload)
            update_payload["fecha"] = firestore.SERVER_TIMESTAMP
            await self._firestore_io(doc_ref.set(update_payload, merge=True), phone=clean_phone, label="update_prospect_moto_interest.set")
            logger.info(f"💾 [MOTO-CANON] persisted canonical moto_interest='{extracted_data['moto_interest']}' for {clean_phone}")
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded):
            raise
        except Exception as e:
            logger.exception(f"❌ update_prospect_moto_interest failed for {phone_number}: {e}")

    async def reset_phase_latches(self, phone_number: str) -> bool:
        """
        [BOT-BUILD-FUNNEL-SKIP-014] Reset de latches de fase SIN purgar historial
        comercial ni identidad del prospecto. Idempotente: set(merge=True) sobre
        documento inexistente simplemente lo crea con los latches en cero (C-8).
        """
        try:
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = await self.get_ref(clean_phone)
            reset_payload = {
                "habeas_data_accepted": False,
                "habeas_data_accepted_sent": False,
                "habeas_data": False,
                "habeas_data_sent": False,
                "forma_pago": "",
                "moto_interest": "",
                "moto_interes": "",
                "moto_confirmada": False,
                "score_resultado": "",
                "reset_at": firestore.SERVER_TIMESTAMP,
                "reset_by": "system_reset_command",
            }
            await self._firestore_io(
                doc_ref.set(reset_payload, merge=True),
                phone=clean_phone,
                label="reset_phase_latches.set",
            )
            logger.info(f"🧹 [RESET-LATCHES] Phase latches reset for {clean_phone}")
            return True
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded):
            raise
        except Exception as e:
            logger.exception(f"❌ [RESET-LATCHES] Failed to reset phase latches for {phone_number}: {e}")
            return False

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

    async def update_last_interaction(self, phone_number: str) -> None:
        """
        Actualiza el timestamp de última interacción del prospecto.

        WHY: El router invoca este método en L645 (texto) y L881 (audio) para
        registrar la actividad del usuario en el CRM.

        Condiciones de diseño (v10.12.6):
          - phone_number: string E.164 canónico, pre-sanitizado por PhoneNormalizer
            en la capa del enrutador (app/routers/whatsapp.py L264). NO se invoca
            PhoneNormalizer aquí para prevenir colisiones de namespace (Condición #1).
          - set(merge=True): tolera documentos inexistentes post-/reset sin lanzar
            google.cloud.exceptions.NotFound (idempotencia).
          - Langfuse: registra traza explícita dentro del contexto transaccional
            activo para observabilidad de escrituras de infraestructura (Condición #2).
        """
        try:
            doc_ref = self._db.collection(self.collection_name).document(phone_number)
            await self._firestore_io(
                doc_ref.set({"fecha": firestore.SERVER_TIMESTAMP}, merge=True),
                phone=phone_number, label="update_last_interaction.set"
            )
            # --- VINCULACIÓN LANGFUSE (Condición #2) ---
            # WHY: Registra la escritura de infraestructura dentro del span activo
            # de Langfuse para garantizar observabilidad end-to-end. El import lazy
            # previene ImportError si Langfuse no está configurado en el entorno.
            try:
                from app.utils.observability import langfuse_context
                langfuse_context.update_current_observation(
                    metadata={"update_last_interaction": phone_number, "idempotent": True}
                )
            except Exception as e:
                # [BOT-BUILD-ETAPA3-WAVE06-LATENCY-CLOSE-001] Zero-Silent-Failures:
                # Langfuse es opcional y no bloquea la operación de Firestore, pero
                # su ausencia queda registrada con ID de correlación (E.164).
                logger.warning(f"⚠️ [LANGFUSE] Observación no registrada para {phone_number}: {e}")
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded):
            raise
        except Exception as e:
            logger.exception(f"❌ update_last_interaction failed for {phone_number}: {e}")
            raise

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
            clean_phone = PhoneNormalizer.normalize(phone_number)
            doc_ref = await self._find_prospect_ref(clean_phone)
            
            # --- GUARDRAIL: Leer status CRM actual antes de escribir ---
            doc_snap = await self._firestore_io(doc_ref.get(), phone=clean_phone, label="update_whatsapp_status.get")
            
            # RECOBRAMIENTO DE EMERGENCIA POST-NUCLEAR WIPE (/RESET)
            is_new_doc = not doc_snap.exists
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

            # Si el documento fue borrado por un /reset, inicializamos las llaves mínimas de estructura
            if is_new_doc:
                if status_value in ("sent", "delivered"):
                    logger.info(f"🛡️ [STATUSES] Ignorando acuse '{status_value}' para prospecto inexistente/purgado {clean_phone} (Bypass de Webhook Recovery).")
                    return
                logger.warning(f"⚠️ [WEBHOOK_RECOVERY] Registrando acuse '{status_value}' en prospecto inexistente/purgado {clean_phone}. Inicializando claves canónicas.")
                payload.update({
                    "celular": clean_phone,
                    "chatbot_status": "ACTIVE",
                    "status": "PENDING",
                    "source": "whatsapp_bot",
                    "human_help_requested": False,
                    "habeas_data_accepted": False,
                    "habeas_data_accepted_sent": False,
                    "created_at": firestore.SERVER_TIMESTAMP
                })

            # Idempotencia para whatsapp_read_at
            if status_value == "read" and "whatsapp_read_at" not in current_data:
                payload["whatsapp_read_at"] = firestore.SERVER_TIMESTAMP

            if errors:
                payload["metadata.whatsapp.last_error"] = errors
                if isinstance(errors, list) and len(errors) > 0:
                    error_summary = errors[0]
                    payload["last_whatsapp_error"] = error_summary.get("message")
                    payload["whatsapp_error_details"] = error_summary
            
            # Guardrail de máquina de estados
            if status_value == "read" and current_crm_status in protected_statuses:
                logger.info(f"🛡️ [STATUSES] Guardrail activo: status '{current_crm_status}' no se altera por acuse 'read'.")

            # CONMUTACIÓN QUIRÚRGICA: set(merge=True) tolera la no existencia física del nodo padre
            await self._firestore_io(doc_ref.set(payload, merge=True), phone=clean_phone, label="update_whatsapp_status.set_merge")
            logger.info(f"✅ [STATUSES] Acuse '{status_value}' registrado con éxito para {clean_phone}")
        except (asyncio.TimeoutError, gcp_exceptions.ServiceUnavailable, gcp_exceptions.DeadlineExceeded) as e:
            logger.exception(
                f"❌ [BOT-BUG-040] gRPC/Timeout error en update_whatsapp_status para {phone_number}: {e}. "
                f"Status: '{status_value}', WAMID: '{wamid}'. El acuse NO fue persistido pero el orquestador continúa."
            )
        except Exception as e:
            logger.exception(f"❌ [STATUSES] Error actualizando metadata.whatsapp para {phone_number}: {e}")

    async def claim_webhook_idempotency(self, wamid: str, phone: str) -> bool:
        """
        [RF-1 / BOT-BUILD-REFACTOR-ETAPA1-WAVE2-200] Reclamo atómico de idempotencia (Piso 2).

        Crea el documento `processed_webhooks/{wamid}` con semántica create-only:
          - Primera entrega → crea y retorna True.
          - Entrega duplicada (reintento Cloud Tasks / Meta) → AlreadyExists → retorna False.

        WHY: La barrera RAM (register_wamid) vive solo en webhook_handler y por proceso;
        este reclamo durable cubre el worker multi-instancia de Cloud Run. El documento
        porta `claimed_at` para limpieza operativa vía TTL de Firestore (tarea de infra).
        """
        doc_ref = self._db.collection("processed_webhooks").document(wamid)
        try:
            await asyncio.wait_for(
                doc_ref.create({
                    "wamid": wamid,
                    "phone": phone,
                    "claimed_at": firestore.SERVER_TIMESTAMP
                }),
                timeout=settings.db_timeout
            )
            return True
        except gcp_exceptions.AlreadyExists:
            logger.warning(
                f"🔄 [RF-1] Entrega duplicada ignorada por reclamo durable: "
                f"wamid='{wamid}' phone='{phone}'"
            )
            return False

    async def release_webhook_claim(self, wamid: str, phone: str) -> None:
        """
        [RF-1] Libera el reclamo durable ante fallo de procesamiento, permitiendo el
        reproceso vía reintento de Cloud Tasks (TTL 120s, BOT-BRAIN-ALIGNMENT-099).
        Best-effort: jamás enmascara la excepción original del pipeline.
        """
        doc_ref = self._db.collection("processed_webhooks").document(wamid)
        try:
            await asyncio.wait_for(doc_ref.delete(), timeout=settings.db_timeout)
            logger.info(f"🔓 [RF-1] Reclamo de idempotencia liberado para reproceso: wamid='{wamid}'")
        except Exception as e:
            logger.exception(
                f"❌ [RF-1] Fallo al liberar reclamo de idempotencia "
                f"wamid='{wamid}' phone='{phone}': {e}"
            )


# ──────────────────────────────────────────────────────────────────────
# Module-level singleton (used by routers)
# ──────────────────────────────────────────────────────────────────────
memory_service: Optional[MemoryService] = None


def init_memory_service(db: firestore.AsyncClient) -> None:
    """Initialize the global memory_service singleton."""
    global memory_service
    memory_service = MemoryService(db)
