"""
Audit Service
Logs interactions to BigQuery for auditing and analytics.
"""

import logging
import asyncio
from typing import Dict, Any
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
            
            if BQ_AVAILABLE:
                try:
                    # Initialize BigQuery client
                    cls._instance.client = bigquery.Client()
                    
                    # Ensure dataset and table exist
                    cls._instance._ensure_table_exists()
                    
                    logger.info("📊 AuditService initialized with BigQuery")
                except Exception as e:
                    import traceback
                    logger.error(f"❌ AUDIT INIT FAILED: {type(e).__name__}: {str(e)}")
                    logger.error(f"   Full error details:")
                    logger.error(traceback.format_exc())
                    logger.error("   ⚠️ Audit logging will be DISABLED for this session")
                    logger.error("   Fix the error above to enable audit logging")
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
        
        project_id = self.client.project
        logger.info(f"🔍 Checking BigQuery infrastructure for project: {project_id}")
        
        # Force create dataset with exists_ok=True
        dataset_ref = f"{project_id}.{self.dataset_id}"
        
        try:
            dataset = self.client.get_dataset(dataset_ref)
            logger.debug(f"✅ Dataset {self.dataset_id} exists")
        except NotFound:
            logger.info(f"📦 Dataset {self.dataset_id} not found, creating...")
            # Create dataset programmatically
            dataset = bigquery.Dataset(dataset_ref)
            dataset.location = "us-central1"  # Match Cloud Run region
            created_dataset = self.client.create_dataset(dataset, exists_ok=True)
            logger.info(f"✅ Created dataset {self.dataset_id} in {created_dataset.location}")
        except Exception as e:
            logger.error(f"❌ FATAL: Cannot create dataset: {type(e).__name__}: {str(e)}")
            logger.error(f"   Project: {project_id}, Dataset: {self.dataset_id}")
            raise  # CRITICAL: Raise to prevent 404 errors later
        
        # Create table if not exists
        table_ref = f"{dataset_ref}.{self.table_id}"
        
        try:
            table = self.client.get_table(table_ref)
            logger.debug(f"✅ Table {self.table_id} exists")
        except NotFound:
            logger.info(f"📋 Table {self.table_id} not found, creating...")
            # Define schema
            schema = [
                bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
                bigquery.SchemaField("phone_number", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("input_text", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("output_text", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("sentiment", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("intent", "STRING", mode="NULLABLE"),
                bigquery.SchemaField("metadata", "STRING", mode="NULLABLE"),
            ]
            
            table = bigquery.Table(table_ref, schema=schema)
            created_table = self.client.create_table(table, exists_ok=True)
            logger.info(f"✅ Created table {self.table_id} with {len(schema)} fields")
        except Exception as e:
            logger.error(f"❌ FATAL: Cannot create table: {type(e).__name__}: {str(e)}")
            logger.error(f"   Table ref: {table_ref}")
            raise  # CRITICAL: Raise to prevent 404 errors later

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
        
        # fire and forget task
        asyncio.create_task(self._insert_row(row))

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
            # Silent fail to not disrupt service
            logger.warning(f"⚠️ Audit Log failed: {e}")

# Global Instance
audit_service = AuditService()
