"""
Audit Service
Logs interactions to BigQuery for auditing and analytics.
"""

import logging
import asyncio
from typing import Dict, Any, Set
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# BigQuery Import
try:
    from google.cloud import bigquery
    BQ_AVAILABLE = True
except ImportError:
    BQ_AVAILABLE = False
    logger.warning("⚠️ Google Cloud BigQuery library not found.")

class AuditService:
    """
    Service for asynchronous logging of events to BigQuery.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuditService, cls).__new__(cls)
            cls._instance.client = None
            cls._instance.dataset_id = "audit_logs"
            cls._instance.table_id = "interactions"
            cls._instance._pending_tasks: Set[asyncio.Task] = set()
            
            if BQ_AVAILABLE:
                try:
                    # Initialize BigQuery client
                    cls._instance.client = bigquery.Client()
                    
                    # Ensure dataset and table exist
                    cls._instance._ensure_table_exists()
                    
                    logger.info("📊 AuditService initialized with BigQuery")
                    print("📊 AuditService initialized with BigQuery", flush=True)
                except Exception as e:
                    import traceback
                    error_msg = f"❌ AUDIT INIT FAILED: {type(e).__name__}: {str(e)}"
                    logger.error(error_msg)
                    logger.error(f"   Exception repr: {repr(e)}")
                    logger.error(f"   Full error details:")
                    logger.error(traceback.format_exc())
                    logger.error("   ⚠️ Audit logging will be DISABLED for this session")
                    logger.error("   Fix the error above to enable audit logging")
                    
                    # CRITICAL: Also print to stdout for Cloud Run visibility
                    print(error_msg, flush=True)
                    print(f"   Exception repr: {repr(e)}", flush=True)
                    print(f"   Full traceback:", flush=True)
                    print(traceback.format_exc(), flush=True)
                    print("   ⚠️ Audit logging DISABLED", flush=True)
                    
                    # CRITICAL: Set client to None to prevent 404 errors
                    cls._instance.client = None
        return cls._instance

    def _ensure_table_exists(self):
        """
        Ensure BigQuery dataset and table exist, create if missing.
        Self-healing: Creates infrastructure programmatically (no manual CLI).
        Raises exception if creation fails to prevent silent 404 errors.
        """
        from google.api_core.exceptions import NotFound
        
        print(f"DEBUG: Starting BigQuery table setup...", flush=True)
        
        project_id = self.client.project
        logger.info(f"🔍 Checking BigQuery infrastructure for project: {project_id}")
        print(f"DEBUG: Project ID: {project_id}", flush=True)
        
        # Force create dataset with exists_ok=True
        dataset_ref = f"{project_id}.{self.dataset_id}"
        
        try:
            print(f"DEBUG: Checking dataset {self.dataset_id}...", flush=True)
            dataset = self.client.get_dataset(dataset_ref)
            logger.debug(f"✅ Dataset {self.dataset_id} exists")
            print(f"✅ Dataset {self.dataset_id} exists", flush=True)
        except NotFound:
            logger.info(f"📦 Dataset {self.dataset_id} not found, creating...")
            print(f"DEBUG: Creating dataset {self.dataset_id}...", flush=True)
            # Create dataset programmatically
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "us-central1"  # Match Cloud Run region
            created_dataset = self.client.create_dataset(dataset, exists_ok=True)
            logger.info(f"✅ Created dataset {self.dataset_id} in {created_dataset.location}")
            print(f"✅ Created dataset {self.dataset_id}", flush=True)
        except Exception as e:
            logger.error(f"❌ Failed to check/create dataset: {repr(e)}")
            print(f"CRITICAL AUDIT ERROR (dataset): {repr(e)}", flush=True)
            raise
        
        # Create table if it doesn't exist
        table_ref = f"{dataset_ref}.{self.table_id}"
        
        try:
            print(f"DEBUG: Checking table {self.table_id}...", flush=True)
            self.client.get_table(table_ref)
            logger.debug(f"✅ Table {self.table_id} exists")
            print(f"✅ Table {self.table_id} exists", flush=True)
        except NotFound:
            logger.info(f"📋 Table {self.table_id} not found, creating...")
            print(f"DEBUG: Creating table {self.table_id}...", flush=True)
            schema = [
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("user_phone", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("message_type", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("user_message", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("bot_response", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("context", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("sentiment", "STRING", mode="NULLABLE"),
            ]
            table = bigquery.Table(table_ref, schema=schema)
            self.client.create_table(table)
            logger.info(f"✅ Created table {self.table_id}")
            print(f"✅ Created table {self.table_id}", flush=True)
        except Exception as e:
            logger.error(f"❌ Failed to check/create table: {repr(e)}")
            print(f"CRITICAL AUDIT ERROR (table): {repr(e)}", flush=True)
            import traceback
            print(traceback.format_exc(), flush=True)
            raise

    def _track_task(self, coro) -> asyncio.Task:
        """
        Register a coroutine as a tracked task to ensure visibility during shutdown.
        WHY: an untracked create_task only holds a weak reference — the task can be
        garbage-collected mid-flight, silently losing BigQuery audit rows.
        Pattern reused from MemoryService._track_task (no new abstraction).
        """
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)
        return task

    async def shutdown(self, timeout: int = 8) -> None:
        """
        Graceful Shutdown Mechanism (Atomic Audit Flush).
        Waits for all tracked insert tasks to complete before process termination.
        Must never raise: shutdown of the process takes precedence.
        """
        if not self._pending_tasks:
            logger.info("👋 [AUDIT-SHUTDOWN] No pending audit tasks. Closing cleanly.")
            return

        logger.info(f"⏳ [AUDIT-SHUTDOWN] Flushing {len(self._pending_tasks)} pending audit tasks (Timeout: {timeout}s)...")
        try:
            await asyncio.wait_for(asyncio.gather(*self._pending_tasks, return_exceptions=True), timeout=timeout)
            logger.info("✅ [AUDIT-SHUTDOWN] All audit tasks flushed successfully.")
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ [AUDIT-SHUTDOWN] Audit flush timed out after {timeout}s. {len(self._pending_tasks)} tasks lost.")
        except Exception as e:
            logger.exception(f"❌ [AUDIT-SHUTDOWN] Error during audit flush: {e}")

    async def log_interaction(self, 
                              phone: str, 
                              input_text: str, 
                              output_text: str, 
                              sentiment: str = "neutral",
                              intent: str = "general"):
        """
        Log an interaction to BigQuery asynchronously.
        Does not block the main thread.
        """
        if not self.client:
            return

        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phone_number": phone,
            "input_text": input_text,
            "output_text": output_text,
            "sentiment": sentiment,
            "intent": intent,
            "metadata": "{}" # placeholder for JSON string
        }
        
        # tracked task (Zero-Silent-Failures: visible and flushable at shutdown)
        self._track_task(self._insert_row(row))

    async def _insert_row(self, row: Dict[str, Any]):
        """Internal insertion logic."""
        try:
            # We use the blocking insert in a thread or just hope it's fast?
            # BigQuery insert_rows_json is blocking. Use executor.
            loop = asyncio.get_running_loop()
            
            # Construct table ref
            table_ref = f"{self.client.project}.{self.dataset_id}.{self.table_id}"
            
            # Run in executor
            errors = await loop.run_in_executor(
                None, 
                lambda: self.client.insert_rows_json(table_ref, [row])
            )
            
            if errors:
                logger.error(f"❌ BigQuery Insert Errors: {errors}")
            else:
               pass # Success (silent)
               
        except Exception as e:
            # Contained to not disrupt service, but ALWAYS with forensic trace
            # (Zero-Silent-Failures).
            logger.exception(f"⚠️ Audit Log failed: {e}")

# Global Instance
audit_service = AuditService()
