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
            if BQ_AVAILABLE:
                try:
                    # Assumes GOOGLE_APPLICATION_CREDENTIALS or default auth
                    cls._instance.client = bigquery.Client()
                    cls._instance.dataset_id = "audit_logs" # Defines dataset
                    cls._instance.table_id = "interactions" # Defines table
                    logger.info("📊 AuditService initialized with BigQuery")
                except Exception as e:
                    logger.error(f"❌ Failed to init BigQuery: {e}")
        return cls._instance

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
