"""
Message Buffer Service - Debounce Logic for WhatsApp Messages

This service implements message aggregation to reduce AI costs and improve response quality
by buffering fragmented user messages (e.g., "Hola" ... "Precio" ... "Moto") into a single
coherent request before processing.

Technical Specification: Section 3.1 - Message Debounce Mechanism
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MessageBuffer:
    """
    Thread-safe message buffering service with debounce logic.
    
    Buffers incoming messages per user (wa_id) and aggregates them after a configurable
    debounce period. Implements task-based cancellation to handle rapid message sequences.
    
    Attributes:
        debounce_seconds: Time to wait before processing buffered messages (default: 4.0)
        _buffers: Dictionary mapping wa_id to list of message texts
        _active_tasks: Dictionary mapping wa_id to current active task_id
        _locks: Dictionary mapping wa_id to asyncio.Lock for thread-safe operations
    """
    
    def __init__(self, debounce_seconds: float = 4.0):
        """
        Initialize the message buffer service.
        
        Args:
            debounce_seconds: Time to wait before processing (default: 4.0 seconds)
        """
        self.debounce_seconds = debounce_seconds
        self._buffers: Dict[str, List[str]] = {}
        self._active_tasks: Dict[str, str] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._processed_wamids: Dict[str, set] = {}
        logger.info(f"📦 MessageBuffer initialized with {debounce_seconds}s debounce")
    
    def _get_lock(self, wa_id: str) -> asyncio.Lock:
        """
        Get or create a lock for the specified user.
        
        Args:
            wa_id: WhatsApp user ID
            
        Returns:
            asyncio.Lock for thread-safe operations
        """
        if wa_id not in self._locks:
            self._locks[wa_id] = asyncio.Lock()
        return self._locks[wa_id]
    
    async def add_message(self, wa_id: str, message_text: str, task_id: str) -> bool:
        """
        Add a message to the buffer and register the task as active.
        
        This method is thread-safe and will supersede any previous active task
        for the same user.
        
        Args:
            wa_id: WhatsApp user ID
            message_text: Text content of the message
            task_id: Unique identifier for this processing task
            
        Returns:
            True if the message was successfully added, False if it was completely ignored as a duplicate wamid.
        """
        lock = self._get_lock(wa_id)
        async with lock:
            if wa_id not in self._processed_wamids:
                self._processed_wamids[wa_id] = set()

            if task_id in self._processed_wamids[wa_id]:
                logger.warning(f"🔄 Duplicate webhook ignored for wamid/task_id: {task_id}")
                return False

            self._processed_wamids[wa_id].add(task_id)

            # Initialize buffer if needed
            if wa_id not in self._buffers:
                self._buffers[wa_id] = []
            
            # Check if this is the first message
            is_first_message = len(self._buffers[wa_id]) == 0
            
            # Add message to buffer
            self._buffers[wa_id].append(message_text)
            
            # Supersede previous task
            previous_task = self._active_tasks.get(wa_id)
            if previous_task:
                logger.info(f"🔄 Task {previous_task} superseded by {task_id} for {wa_id}")
            
            # Register this task as active
            self._active_tasks[wa_id] = task_id
            
            logger.info(
                f"📥 Message added to buffer for {wa_id} | "
                f"Buffer size: {len(self._buffers[wa_id])} | "
                f"Task: {task_id} | "
                f"First: {is_first_message}"
            )
            
            return True
    
    def is_task_active(self, wa_id: str, task_id: str) -> bool:
        """
        Check if the specified task is still the active task for the user.
        
        This is used to implement task cancellation: if a newer message arrived
        during the debounce period, the older task should abort.
        
        Args:
            wa_id: WhatsApp user ID
            task_id: Task identifier to check
            
        Returns:
            True if this task is still active, False if superseded
        """
        active_task = self._active_tasks.get(wa_id)
        is_active = active_task == task_id
        
        if not is_active:
            logger.debug(f"⏭️ Task {task_id} is no longer active for {wa_id} (current: {active_task})")
        
        return is_active
    
    async def get_aggregated_message(self, wa_id: str) -> str:
        """
        Retrieve and combine all buffered messages for the user.
        
        Messages are joined with spaces to form a coherent text string.
        The buffer is NOT cleared by this method - use clear_buffer() explicitly.
        
        Args:
            wa_id: WhatsApp user ID
            
        Returns:
            Combined message text, or empty string if no messages buffered
        """
        lock = self._get_lock(wa_id)
        async with lock:
            messages = self._buffers.get(wa_id, [])
            
            if not messages:
                logger.warning(f"⚠️ No messages in buffer for {wa_id}")
                return ""
            
            # Combine messages with space separator
            aggregated = " ".join(messages)
            
            logger.info(
                f"📤 Aggregated {len(messages)} message(s) for {wa_id} | "
                f"Total length: {len(aggregated)} chars"
            )
            
            return aggregated
    
    async def clear_buffer(self, wa_id: str) -> None:
        """
        Clear the message buffer and active task for the user.
        
        This should be called after successfully processing the aggregated message
        to prevent memory leaks and prepare for the next message sequence.
        
        Args:
            wa_id: WhatsApp user ID
        """
        lock = self._get_lock(wa_id)
        async with lock:
            # Remove buffer
            if wa_id in self._buffers:
                msg_count = len(self._buffers[wa_id])
                del self._buffers[wa_id]
                logger.debug(f"🗑️ Cleared {msg_count} message(s) from buffer for {wa_id}")
            
            # Remove active task
            if wa_id in self._active_tasks:
                del self._active_tasks[wa_id]
                logger.debug(f"🗑️ Cleared active task for {wa_id}")
            
            # Remove processed wamids
            if wa_id in self._processed_wamids:
                del self._processed_wamids[wa_id]
    
    async def get_buffer_stats(self) -> Dict[str, int]:
        """
        Get current buffer statistics for monitoring.
        
        Returns:
            Dictionary with buffer metrics
        """
        return {
            "active_users": len(self._buffers),
            "active_tasks": len(self._active_tasks),
            "total_messages": sum(len(msgs) for msgs in self._buffers.values())
        }
