"""
Context management for subagent tools.

This module provides context isolation and management capabilities to ensure
clean separation between subagent executions and proper resource cleanup.
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional, List, Set
from contextlib import asynccontextmanager
from dataclasses import dataclass, field


@dataclass
class SubagentContext:
    """
    Context container for a subagent execution.
    
    This class maintains execution state, metadata, and resources for a single
    subagent task, ensuring clean isolation from other executions.
    """
    
    # Identification
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_agent_id: Optional[str] = None
    task_description: str = ""
    
    # Execution metadata
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status: str = "created"  # created, running, completed, failed, timeout
    
    # Resource tracking
    agent_instance: Optional[Any] = None
    cleanup_callbacks: List[callable] = field(default_factory=list)
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    
    # Context data
    initial_prompt: str = ""
    working_directory: Optional[str] = None
    environment_vars: Dict[str, str] = field(default_factory=dict)
    
    # Results
    result: Optional[str] = None
    error: Optional[str] = None
    execution_log: List[str] = field(default_factory=list)
    
    def add_log(self, message: str):
        """Add a log entry with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        self.execution_log.append(f"[{timestamp}] {message}")
    
    def add_cleanup_callback(self, callback: callable):
        """Add a cleanup callback to be executed when context is disposed."""
        self.cleanup_callbacks.append(callback)
    
    def mark_started(self):
        """Mark the context as started."""
        self.started_at = time.time()
        self.status = "running"
        self.add_log("Subagent execution started")
    
    def mark_completed(self, result: str):
        """Mark the context as completed with result."""
        self.completed_at = time.time()
        self.status = "completed"
        self.result = result
        self.add_log("Subagent execution completed successfully")
    
    def mark_failed(self, error: str):
        """Mark the context as failed with error."""
        self.completed_at = time.time()
        self.status = "failed"
        self.error = error
        self.add_log(f"Subagent execution failed: {error}")
    
    def mark_timeout(self):
        """Mark the context as timed out."""
        self.completed_at = time.time()
        self.status = "timeout"
        self.error = "Execution timed out"
        self.add_log("Subagent execution timed out")
    
    def get_duration(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or time.time()
        return end_time - self.started_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging/debugging."""
        return {
            'context_id': self.context_id,
            'parent_agent_id': self.parent_agent_id,
            'task_description': self.task_description,
            'status': self.status,
            'duration': self.get_duration(),
            'result_length': len(self.result) if self.result else 0,
            'error': self.error,
            'log_entries': len(self.execution_log),
            'cleanup_callbacks': len(self.cleanup_callbacks)
        }


class ContextManager:
    """
    Manager for subagent contexts with automatic cleanup and resource tracking.
    
    This class handles the lifecycle of subagent contexts, ensuring proper
    resource management and cleanup to prevent memory leaks.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._active_contexts: Dict[str, SubagentContext] = {}
        self._context_lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False
        
        # Start background cleanup task
        self._start_cleanup_task()
    
    def _start_cleanup_task(self):
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodic cleanup of stale contexts."""
        while not self._shutdown:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_stale_contexts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in periodic cleanup: {e}")
    
    async def _cleanup_stale_contexts(self):
        """Clean up contexts that have been inactive for too long."""
        current_time = time.time()
        stale_threshold = 300  # 5 minutes
        
        async with self._context_lock:
            stale_contexts = []
            for context_id, context in self._active_contexts.items():
                # Consider context stale if it's been running too long or completed long ago
                if context.status == "running":
                    if context.started_at and (current_time - context.started_at) > stale_threshold:
                        context.mark_timeout()
                        stale_contexts.append(context_id)
                elif context.status in ["completed", "failed", "timeout"]:
                    if context.completed_at and (current_time - context.completed_at) > 60:  # 1 minute grace
                        stale_contexts.append(context_id)
            
            # Clean up stale contexts
            for context_id in stale_contexts:
                await self._cleanup_context(context_id)
    
    async def create_context(
        self,
        task_description: str,
        parent_agent_id: Optional[str] = None,
        working_directory: Optional[str] = None,
        environment_vars: Optional[Dict[str, str]] = None
    ) -> SubagentContext:
        """
        Create a new subagent context.
        
        Args:
            task_description: Description of the task
            parent_agent_id: ID of the parent agent
            working_directory: Working directory for the subagent
            environment_vars: Environment variables for the subagent
            
        Returns:
            A new SubagentContext instance
        """
        context = SubagentContext(
            parent_agent_id=parent_agent_id,
            task_description=task_description,
            working_directory=working_directory,
            environment_vars=environment_vars or {}
        )
        
        async with self._context_lock:
            self._active_contexts[context.context_id] = context
        
        self.logger.debug(f"Created context {context.context_id} for task: {task_description[:50]}...")
        return context
    
    async def get_context(self, context_id: str) -> Optional[SubagentContext]:
        """Get a context by ID."""
        async with self._context_lock:
            return self._active_contexts.get(context_id)
    
    async def cleanup_context(self, context_id: str) -> bool:
        """
        Clean up a specific context.
        
        Args:
            context_id: ID of the context to clean up
            
        Returns:
            True if context was found and cleaned up, False otherwise
        """
        return await self._cleanup_context(context_id)
    
    async def _cleanup_context(self, context_id: str) -> bool:
        """Internal method to clean up a context."""
        async with self._context_lock:
            context = self._active_contexts.get(context_id)
            if not context:
                return False
            
            # Execute cleanup callbacks
            for callback in context.cleanup_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback()
                    else:
                        callback()
                except Exception as e:
                    self.logger.error(f"Error in cleanup callback for context {context_id}: {e}")
            
            # Close agent instance if it exists
            if context.agent_instance and hasattr(context.agent_instance, 'close'):
                try:
                    await context.agent_instance.close()
                except Exception as e:
                    self.logger.error(f"Error closing agent for context {context_id}: {e}")
            
            # Remove from active contexts
            del self._active_contexts[context_id]
            
            duration = context.get_duration()
            self.logger.debug(
                f"Cleaned up context {context_id} (status: {context.status}, "
                f"duration: {duration:.2f}s)" if duration else 
                f"Cleaned up context {context_id} (status: {context.status})"
            )
            return True
    
    @asynccontextmanager
    async def managed_context(
        self,
        task_description: str,
        parent_agent_id: Optional[str] = None,
        working_directory: Optional[str] = None,
        environment_vars: Optional[Dict[str, str]] = None
    ):
        """
        Context manager for automatic cleanup of subagent contexts.
        
        Usage:
            async with context_manager.managed_context("task") as context:
                # Use context here
                pass
            # Context is automatically cleaned up
        """
        context = await self.create_context(
            task_description=task_description,
            parent_agent_id=parent_agent_id,
            working_directory=working_directory,
            environment_vars=environment_vars
        )
        
        try:
            yield context
        finally:
            await self._cleanup_context(context.context_id)
    
    async def get_active_contexts(self) -> List[SubagentContext]:
        """Get all currently active contexts."""
        async with self._context_lock:
            return list(self._active_contexts.values())
    
    async def get_context_stats(self) -> Dict[str, Any]:
        """Get statistics about active contexts."""
        async with self._context_lock:
            contexts = list(self._active_contexts.values())
            
            stats = {
                'total_active': len(contexts),
                'by_status': {},
                'average_duration': 0,
                'oldest_context': None,
                'newest_context': None
            }
            
            if not contexts:
                return stats
            
            # Count by status
            for context in contexts:
                stats['by_status'][context.status] = stats['by_status'].get(context.status, 0) + 1
            
            # Calculate average duration for completed contexts
            completed_durations = [c.get_duration() for c in contexts if c.get_duration() is not None]
            if completed_durations:
                stats['average_duration'] = sum(completed_durations) / len(completed_durations)
            
            # Find oldest and newest
            stats['oldest_context'] = min(contexts, key=lambda c: c.created_at).created_at
            stats['newest_context'] = max(contexts, key=lambda c: c.created_at).created_at
            
            return stats
    
    async def cleanup_all(self):
        """Clean up all active contexts."""
        async with self._context_lock:
            context_ids = list(self._active_contexts.keys())
        
        for context_id in context_ids:
            await self._cleanup_context(context_id)
        
        self.logger.info(f"Cleaned up {len(context_ids)} contexts")
    
    async def shutdown(self):
        """Shutdown the context manager and clean up all resources."""
        self._shutdown = True
        
        # Cancel the cleanup task
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Clean up all contexts
        await self.cleanup_all()
        
        self.logger.info("Context manager shutdown complete")


# Global context manager instance
_global_context_manager: Optional[ContextManager] = None


def get_context_manager(logger: Optional[logging.Logger] = None) -> ContextManager:
    """Get the global context manager instance."""
    global _global_context_manager
    if _global_context_manager is None:
        _global_context_manager = ContextManager(logger)
    return _global_context_manager


async def cleanup_global_context_manager():
    """Clean up the global context manager."""
    global _global_context_manager
    if _global_context_manager:
        await _global_context_manager.shutdown()
        _global_context_manager = None