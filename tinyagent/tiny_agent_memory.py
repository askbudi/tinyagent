import logging
from typing import Dict, List, Optional, Any, Tuple, Union
import time
import asyncio
from enum import Enum

from .tiny_agent import TinyAgent
from .memory_manager import MemoryManager, MemoryStrategy, BalancedStrategy, ConservativeStrategy, AggressiveStrategy
from .storage import Storage

logger = logging.getLogger(__name__)

class TinyAgentMemory(TinyAgent):
    """
    Enhanced TinyAgent with advanced memory management capabilities.
    
    This class extends TinyAgent with memory optimization features to:
    - Maintain conversation quality even with extensive history
    - Intelligently manage context window by removing or summarizing less important messages
    - Keep critical information while removing resolved errors and completed tasks
    - Support different memory management strategies
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        logger: Optional[logging.Logger] = None,
        model_kwargs: Optional[Dict[str, Any]] = {},
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        storage: Optional[Storage] = None,
        persist_tool_configs: bool = False,
        # Memory manager specific parameters
        memory_strategy: Union[MemoryStrategy, str] = "balanced",
        max_tokens: int = 8000,
        target_tokens: int = 6000,
        enable_summarization: bool = True,
        optimize_on_token_threshold: float = 0.75,  # Optimize when reaching 75% of max tokens
        num_recent_pairs_high_importance: Optional[int] = None,
        num_initial_pairs_critical: Optional[int] = None,
        # Add LoggingManager parameter
        log_manager: Optional[Any] = None
    ):
        """
        Initialize TinyAgentMemory with memory management capabilities.
        
        Args:
            model: The model to use with LiteLLM
            api_key: The API key for the model provider
            system_prompt: Custom system prompt for the agent
            temperature: Temperature for model sampling
            logger: Optional logger to use
            model_kwargs: Additional arguments for the model
            user_id: Optional user ID
            session_id: Optional session ID
            metadata: Optional metadata for the session
            storage: Optional storage backend for persistence
            persist_tool_configs: Whether to persist tool configurations
            memory_strategy: Memory management strategy (balanced, conservative, aggressive, or custom)
            max_tokens: Maximum tokens to send to the model
            target_tokens: Target token count after optimization
            enable_summarization: Whether to enable message summarization
            optimize_on_token_threshold: Threshold ratio to trigger optimization
            num_recent_pairs_high_importance: Number of recent pairs to mark as HIGH importance
            num_initial_pairs_critical: Number of initial pairs to mark as CRITICAL importance
            log_manager: Optional LoggingManager instance for proper logger configuration
        """
        # Initialize the parent TinyAgent
        super().__init__(
            model=model,
            api_key=api_key,
            system_prompt=system_prompt,
            temperature=temperature,
            logger=logger,
            model_kwargs=model_kwargs,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            storage=storage,
            persist_tool_configs=persist_tool_configs
        )
        
        # Initialize memory strategy
        if isinstance(memory_strategy, str):
            strategy_map = {
                "balanced": BalancedStrategy(),
                "conservative": ConservativeStrategy(),
                "aggressive": AggressiveStrategy()
            }
            strategy = strategy_map.get(memory_strategy.lower(), BalancedStrategy())
        else:
            strategy = memory_strategy
        
        # Create a dedicated logger for the memory manager
        memory_logger = logger
        if log_manager is not None:
            # Use LoggingManager to get the properly configured logger
            memory_logger = log_manager.get_logger('tinyagent.memory_manager')
        elif hasattr(logger, 'name') and logger.name.startswith('tinyagent'):
            # Fallback: create logger directly (this is the old buggy behavior)
            memory_logger = logging.getLogger('tinyagent.memory_manager')
            # Copy the parent logger's level as default if not specifically set
            if not hasattr(memory_logger, '_level_set_by_logging_manager'):
                memory_logger.setLevel(logger.level)
        
        # Initialize memory manager
        self.memory_manager = MemoryManager(
            max_tokens=max_tokens,
            target_tokens=target_tokens,
            strategy=strategy,
            enable_summarization=enable_summarization,
            logger=memory_logger,
            num_recent_pairs_high_importance=num_recent_pairs_high_importance,
            num_initial_pairs_critical=num_initial_pairs_critical
        )
        
        # Additional memory management parameters
        self.optimize_on_token_threshold = optimize_on_token_threshold
        
        # Add memory management event hooks
        self.add_callback(self._on_message_add)
        self.add_callback(self._on_llm_start)
        self.add_callback(self._on_after_message)
        
        # Track last optimization timestamp to avoid optimizing too frequently
        self._last_optimization_time = 0
        self._optimization_cooldown = 5  # seconds
        
        # Register tool importance overrides from existing custom tools
        self.memory_manager.register_tools_from_agent(self)
        
    async def _on_message_add(self, event_name: str, agent: "TinyAgent", **kwargs) -> None:
        """
        Callback hook: track message metadata when messages are added.
        """
        if event_name != "message_add":
            return
        
        message = kwargs.get("message")
        if not message:
            return
        
        # Use proper token counting that handles tool calls
        token_count = self.memory_manager._count_message_tokens(message, self.count_tokens)
        
        # Calculate current position and total messages for dynamic importance
        current_index = len(self.memory_manager.message_metadata)
        total_messages = len(self.messages)
        
        # Add metadata for the new message with dynamic importance
        self.memory_manager.add_message_metadata(message, token_count, current_index, total_messages, self.messages)
        
        # Mark error messages as resolved when relevant
        if self._is_error_resolution(message):
            await self._mark_related_errors_resolved()
    
    async def _on_llm_start(self, event_name: str, agent: "TinyAgent", **kwargs) -> None:
        """
        Callback hook: optimize messages before sending to LLM if needed.
        """
        if event_name != "llm_start":
            return
        
        messages = kwargs.get("messages", [])
        if not messages:
            return
        
        # Check if we should optimize based on token count
        total_tokens = sum(self.count_tokens(str(msg.get("content", ""))) for msg in messages)
        token_ratio = total_tokens / self.memory_manager.max_tokens
        
        current_time = time.time()
        time_since_last_opt = current_time - self._last_optimization_time
        
        if (token_ratio >= self.optimize_on_token_threshold and 
            time_since_last_opt > self._optimization_cooldown):
            # Optimize messages
            optimized_messages, opt_info = self.memory_manager.optimize_messages(
                messages, self.count_tokens
            )
            
            # Validate tool call integrity before accepting optimized messages
            if "error" not in opt_info:
                # Additional validation to ensure tool call/response integrity
                if self._validate_tool_call_integrity(optimized_messages):
                    # Update the messages in kwargs for the LLM call
                    kwargs["messages"] = optimized_messages
                    
                    # Update our message list
                    self.messages = optimized_messages
                    
                    # Update optimization timestamp
                    self._last_optimization_time = current_time
                    
                    self.logger.info(f"Memory optimized: {opt_info}")
                else:
                    self.logger.warning("Memory optimization rejected: would break tool call integrity")
            else:
                self.logger.warning(f"Memory optimization failed: {opt_info['error']}")
    
    async def _on_after_message(self, event_name: str, agent: "TinyAgent", **kwargs) -> None:
        """
        Callback hook: update message metadata after a new message is added.
        """
        if event_name != "after_message_add":
            return
        
        if not hasattr(self, 'memory_manager') or not self.memory_manager:
            return
        
        message = kwargs.get("message", {})
        if not message:
            return
        
        # The memory manager now handles recalculation automatically in add_message_metadata
        # However, we should trigger a full recalculation periodically to ensure accuracy
        total_messages = len(self.messages)
        
        # Trigger recalculation every 5 messages or when we have significant conversation growth
        if total_messages % 5 == 0 or total_messages > 10:
            self.memory_manager._recalculate_all_importance_levels()
            self.logger.debug(f"Triggered importance recalculation after {total_messages} messages")
        else:
            self.logger.debug("Message metadata updated automatically by memory manager")

    def _is_error_resolution(self, message: Dict[str, Any]) -> bool:
        """Check if a message represents resolution of a previous error."""
        if message.get('role') != 'tool':
            return False
        
        content = str(message.get('content', '')).lower()
        
        # Check if this is a successful response (not an error)
        error_indicators = [
            'error', 'failed', 'exception', 'traceback', 'invalid',
            'not found', 'permission denied', 'timeout', 'connection refused'
        ]
        
        return not any(indicator in content for indicator in error_indicators)
    
    async def _mark_related_errors_resolved(self) -> None:
        """Mark related error messages as resolved."""
        # The memory manager now handles this automatically through _update_resolved_errors
        # This method is kept for compatibility but delegates to the memory manager
        pass
    
    def _validate_tool_call_integrity(self, messages: List[Dict[str, Any]]) -> bool:
        """
        Validate that tool calls and responses are properly paired.
        
        Args:
            messages: List of messages to validate
            
        Returns:
            True if tool call integrity is maintained
        """
        tool_calls_waiting = {}  # tool_call_id -> message_index
        
        for i, msg in enumerate(messages):
            role = msg.get('role')
            
            if role == 'assistant' and 'tool_calls' in msg:
                # Register tool calls
                for tool_call in msg.get('tool_calls', []):
                    tool_call_id = tool_call.get('id')
                    if tool_call_id:
                        tool_calls_waiting[tool_call_id] = i
            
            elif role == 'tool':
                # Check for matching tool call
                tool_call_id = msg.get('tool_call_id')
                if tool_call_id in tool_calls_waiting:
                    # Found matching pair, remove from waiting
                    del tool_calls_waiting[tool_call_id]
                else:
                    # Orphaned tool response
                    self.logger.warning(f"Found orphaned tool response: {tool_call_id}")
                    return False
        
        # Check for unmatched tool calls
        if tool_calls_waiting:
            self.logger.warning(f"Found unmatched tool calls: {list(tool_calls_waiting.keys())}")
            return False
        
        return True

    @classmethod
    async def create(
        cls,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        logger: Optional[logging.Logger] = None,
        model_kwargs: Optional[Dict[str, Any]] = {},
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        storage: Optional[Storage] = None,
        persist_tool_configs: bool = False,
        memory_strategy: Union[MemoryStrategy, str] = "balanced",
        max_tokens: int = 8000,
        target_tokens: int = 6000,
        enable_summarization: bool = True,
        optimize_on_token_threshold: float = 0.75,
        num_recent_pairs_high_importance: Optional[int] = None,
        num_initial_pairs_critical: Optional[int] = None,
        # Add LoggingManager parameter
        log_manager: Optional[Any] = None
    ) -> "TinyAgentMemory":
        """
        Async factory: constructs the agent with memory management, then loads an existing session
        if (storage and session_id) were provided.
        """
        agent = cls(
            model=model,
            api_key=api_key,
            system_prompt=system_prompt,
            temperature=temperature,
            logger=logger,
            model_kwargs=model_kwargs,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            storage=storage,
            persist_tool_configs=persist_tool_configs,
            memory_strategy=memory_strategy,
            max_tokens=max_tokens,
            target_tokens=target_tokens,
            enable_summarization=enable_summarization,
            optimize_on_token_threshold=optimize_on_token_threshold,
            num_recent_pairs_high_importance=num_recent_pairs_high_importance,
            num_initial_pairs_critical=num_initial_pairs_critical,
            log_manager=log_manager
        )
        
        if agent._needs_session_load:
            await agent.init_async()
            
        return agent
        
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get statistics about memory management.
        
        Returns:
            Dictionary of memory statistics
        """
        return self.memory_manager.get_memory_stats()
    
    def clear_memory_stats(self) -> None:
        """Reset memory management statistics."""
        self.memory_manager.reset_stats()
    
    def clear_completed_tasks(self) -> None:
        """Clear metadata for completed tasks to free up memory."""
        self.memory_manager.clear_completed_tasks()

    def export_important_messages(
        self, 
        min_importance: str = "MEDIUM",
        include_metadata: bool = True,
        include_summaries: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Export messages with importance level >= min_importance.
        
        Args:
            min_importance: Minimum importance level to include ("CRITICAL", "HIGH", "MEDIUM", "LOW", "TEMP")
            include_metadata: Whether to include metadata in the exported messages
            include_summaries: Whether to include message summaries when available
            
        Returns:
            List of messages with optional metadata
        """
        from .memory_manager import MessageImportance
        
        # Map string to enum
        importance_map = {
            "CRITICAL": MessageImportance.CRITICAL,
            "HIGH": MessageImportance.HIGH,
            "MEDIUM": MessageImportance.MEDIUM,
            "LOW": MessageImportance.LOW,
            "TEMP": MessageImportance.TEMP
        }
        
        min_importance_enum = importance_map.get(min_importance.upper(), MessageImportance.MEDIUM)
        
        # Define importance order for comparison
        importance_order = [
            MessageImportance.TEMP,
            MessageImportance.LOW,
            MessageImportance.MEDIUM,
            MessageImportance.HIGH,
            MessageImportance.CRITICAL
        ]
        
        min_level = importance_order.index(min_importance_enum)
        
        exported_messages = []
        
        # Ensure we have metadata for all messages
        if len(self.memory_manager.message_metadata) != len(self.messages):
            self.logger.warning(f"Metadata count ({len(self.memory_manager.message_metadata)}) doesn't match message count ({len(self.messages)})")
            # Sync metadata if needed
            self._sync_metadata_with_messages()
        
        for i, (message, metadata) in enumerate(zip(self.messages, self.memory_manager.message_metadata)):
            # Check if this message meets the importance threshold
            msg_level = importance_order.index(metadata.importance)
            
            if msg_level >= min_level:
                exported_msg = message.copy()
                
                if include_metadata:
                    # Add metadata to the message
                    exported_msg["_metadata"] = {
                        "message_type": metadata.message_type.value,
                        "importance": metadata.importance.value,
                        "created_at": metadata.created_at,
                        "token_count": metadata.token_count,
                        "is_error": metadata.is_error,
                        "error_resolved": metadata.error_resolved,
                        "part_of_task": metadata.part_of_task,
                        "task_completed": metadata.task_completed,
                        "can_summarize": metadata.can_summarize,
                        "tool_call_id": metadata.tool_call_id,
                        "position": i,
                        "related_messages": metadata.related_messages
                    }
                    
                    if include_summaries and metadata.summary:
                        exported_msg["_metadata"]["summary"] = metadata.summary
                
                exported_messages.append(exported_msg)
        
        self.logger.info(f"Exported {len(exported_messages)} messages with importance >= {min_importance}")
        return exported_messages

    def export_message_pairs(
        self,
        min_importance: str = "MEDIUM",
        include_metadata: bool = True
    ) -> List[List[Dict[str, Any]]]:
        """
        Export messages grouped by conversation pairs.
        
        Args:
            min_importance: Minimum importance level to include
            include_metadata: Whether to include metadata
            
        Returns:
            List of message pairs, where each pair is a list of related messages
        """
        # Get message pairs from memory manager
        message_pairs = self.memory_manager._calculate_message_pairs()
        
        from .memory_manager import MessageImportance
        importance_map = {
            "CRITICAL": MessageImportance.CRITICAL,
            "HIGH": MessageImportance.HIGH,
            "MEDIUM": MessageImportance.MEDIUM,
            "LOW": MessageImportance.LOW,
            "TEMP": MessageImportance.TEMP
        }
        
        min_importance_enum = importance_map.get(min_importance.upper(), MessageImportance.MEDIUM)
        importance_order = [
            MessageImportance.TEMP,
            MessageImportance.LOW,
            MessageImportance.MEDIUM,
            MessageImportance.HIGH,
            MessageImportance.CRITICAL
        ]
        min_level = importance_order.index(min_importance_enum)
        
        exported_pairs = []
        
        for start_idx, end_idx in message_pairs:
            # Check if any message in this pair meets the importance threshold
            pair_messages = []
            pair_meets_threshold = False
            
            for i in range(start_idx, end_idx + 1):
                if i < len(self.messages) and i < len(self.memory_manager.message_metadata):
                    message = self.messages[i]
                    metadata = self.memory_manager.message_metadata[i]
                    
                    msg_level = importance_order.index(metadata.importance)
                    if msg_level >= min_level:
                        pair_meets_threshold = True
                    
                    exported_msg = message.copy()
                    if include_metadata:
                        exported_msg["_metadata"] = {
                            "message_type": metadata.message_type.value,
                            "importance": metadata.importance.value,
                            "created_at": metadata.created_at,
                            "token_count": metadata.token_count,
                            "is_error": metadata.is_error,
                            "error_resolved": metadata.error_resolved,
                            "part_of_task": metadata.part_of_task,
                            "task_completed": metadata.task_completed,
                            "tool_call_id": metadata.tool_call_id,
                            "position": i
                        }
                    
                    pair_messages.append(exported_msg)
            
            if pair_meets_threshold and pair_messages:
                exported_pairs.append(pair_messages)
        
        self.logger.info(f"Exported {len(exported_pairs)} message pairs with importance >= {min_importance}")
        return exported_pairs

    def export_tool_call_pairs(self, include_resolved_errors: bool = False) -> List[Dict[str, Any]]:
        """
        Export tool call/response pairs with their metadata.
        
        Args:
            include_resolved_errors: Whether to include resolved error pairs
            
        Returns:
            List of tool call pair information
        """
        tool_pairs = []
        
        for tool_call_id, (call_idx, response_idx) in self.memory_manager._tool_call_pairs.items():
            if (call_idx < len(self.messages) and response_idx < len(self.messages) and
                call_idx < len(self.memory_manager.message_metadata) and response_idx < len(self.memory_manager.message_metadata)):
                
                call_msg = self.messages[call_idx]
                response_msg = self.messages[response_idx]
                call_meta = self.memory_manager.message_metadata[call_idx]
                response_meta = self.memory_manager.message_metadata[response_idx]
                
                # Skip resolved errors if not requested
                if not include_resolved_errors and response_meta.is_error and response_meta.error_resolved:
                    continue
                
                pair_info = {
                    "tool_call_id": tool_call_id,
                    "call_message": call_msg.copy(),
                    "response_message": response_msg.copy(),
                    "call_metadata": {
                        "importance": call_meta.importance.value,
                        "message_type": call_meta.message_type.value,
                        "position": call_idx,
                        "token_count": call_meta.token_count
                    },
                    "response_metadata": {
                        "importance": response_meta.importance.value,
                        "message_type": response_meta.message_type.value,
                        "position": response_idx,
                        "token_count": response_meta.token_count,
                        "is_error": response_meta.is_error,
                        "error_resolved": response_meta.error_resolved
                    }
                }
                
                tool_pairs.append(pair_info)
        
        self.logger.info(f"Exported {len(tool_pairs)} tool call pairs")
        return tool_pairs

    def _sync_metadata_with_messages(self) -> None:
        """Synchronize metadata with current messages if they're out of sync."""
        if len(self.memory_manager.message_metadata) == len(self.messages):
            return
        
        self.logger.info("Synchronizing message metadata with current messages")
        
        # Clear existing metadata and rebuild
        self.memory_manager.message_metadata.clear()
        
        for i, message in enumerate(self.messages):
            # Use the memory manager's token counting method
            token_count = self.memory_manager._count_message_tokens(message, self.count_tokens)
            self.memory_manager.add_message_metadata(message, token_count, i, len(self.messages), self.messages)

    def add_message_with_metadata(self, message: Dict[str, Any]) -> None:
        """Add a message and its metadata, ensuring tool call pairs are synchronized."""
        # Add the message
        self.messages.append(message)
        
        # Use proper token counting
        token_count = self.memory_manager._count_message_tokens(message, self.count_tokens)
        
        # Add metadata - the memory manager now handles all synchronization automatically
        position = len(self.messages) - 1
        total_messages = len(self.messages)
        self.memory_manager.add_message_metadata(message, token_count, position, total_messages, self.messages)
        
        self.logger.debug(f"Added message with synchronized metadata at position {position}")

    def recalculate_importance_levels(self) -> None:
        """
        Manually trigger recalculation of all message importance levels.
        This should be called when conversation structure changes significantly.
        """
        if hasattr(self, 'memory_manager') and self.memory_manager:
            self.memory_manager.recalculate_importance_levels(self.messages)
        else:
            self.logger.warning("Memory manager not available for importance recalculation")

    def add_tool(self, tool_func_or_class: Any) -> None:
        """
        Add a custom tool (function or class) to the agent and register its memory importance override.
        
        Args:
            tool_func_or_class: A function or class decorated with @tool
        """
        # Call the parent method to add the tool
        super().add_tool(tool_func_or_class)
        
        # Register memory importance override if specified
        if hasattr(tool_func_or_class, '_tool_metadata'):
            metadata = tool_func_or_class._tool_metadata
            memory_importance = metadata.get('memory_importance')
            if memory_importance:
                self.memory_manager.register_tool_importance_override(
                    metadata["name"], 
                    memory_importance
                )
                self.logger.debug(f"Registered memory importance override for tool {metadata['name']}: {memory_importance}")

    def export_conversation_summary(self, include_metadata: bool = True) -> Dict[str, Any]:
        """
        Export a summary of the conversation including important messages and statistics.
        
        Args:
            include_metadata: Whether to include message metadata in the export
            
        Returns:
            Dictionary containing conversation summary
        """
        # Get important messages (MEDIUM and above)
        important_messages = self.export_important_messages(
            min_importance="MEDIUM",
            include_metadata=include_metadata
        )
        
        # Get memory statistics
        memory_stats = self.get_memory_stats()
        
        # Find unresolved errors
        unresolved_errors = []
        if include_metadata:
            for msg in important_messages:
                if (msg.get("_metadata", {}).get("is_error") and 
                    not msg.get("_metadata", {}).get("error_resolved")):
                    unresolved_errors.append({
                        "tool_call_id": msg.get("_metadata", {}).get("tool_call_id"),
                        "content": msg.get("content", "")[:100] + "..." if len(msg.get("content", "")) > 100 else msg.get("content", ""),
                        "position": msg.get("_metadata", {}).get("position", -1)
                    })
        
        summary = {
            "session_id": getattr(self, 'session_id', None),
            "total_messages": len(self.messages),
            "important_messages": important_messages,
            "memory_stats": memory_stats,
            "unresolved_errors": unresolved_errors,
            "export_timestamp": time.time()
        }
        
        self.logger.info(f"Exported conversation summary with {len(important_messages)} important messages")
        return summary

async def run_example():
    """Example usage of TinyAgentMemory with proper logging."""
    import os
    import sys
    from tinyagent.hooks.logging_manager import LoggingManager
    from tinyagent.hooks.rich_ui_callback import RichUICallback
    
    # Create and configure logging manager
    log_manager = LoggingManager(default_level=logging.INFO)
    log_manager.set_levels({
        'tinyagent.tiny_agent_memory': logging.DEBUG,
        'tinyagent.tiny_agent': logging.INFO,
        'tinyagent.mcp_client': logging.INFO,
        'tinyagent.hooks.rich_ui_callback': logging.INFO,
        'tinyagent.memory_manager': logging.DEBUG,  # Control memory manager logging
    })
    
    # Configure a console handler
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    
    # Get module-specific loggers
    agent_logger = log_manager.get_logger('tinyagent.tiny_agent_memory')
    ui_logger = log_manager.get_logger('tinyagent.hooks.rich_ui_callback')
    memory_logger = log_manager.get_logger('tinyagent.memory_manager')
    
    agent_logger.debug("Starting TinyAgentMemory example")
    memory_logger.debug("Memory manager logger configured")
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        agent_logger.error("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Initialize the agent with memory management - PASS LOG_MANAGER
    agent = await TinyAgentMemory.create(
        model="gpt-4.1-mini",
        api_key=api_key,
        logger=agent_logger,
        session_id="memory-test-session",
        memory_strategy="balanced",  # Can be "balanced", "conservative", or "aggressive"
        max_tokens=8000,
        target_tokens=6000,
        enable_summarization=True,
        log_manager=log_manager  # Pass the LoggingManager instance
    )
    
    # Connect to MCP servers for tools
    await agent.connect_to_server("npx",["-y","@openbnb/mcp-server-airbnb","--ignore-robots-txt"])
    await agent.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    # Add the Rich UI callback
    rich_ui = RichUICallback(
        markdown=True,
        show_message=True,
        show_thinking=True,
        show_tool_calls=True,
        logger=ui_logger
    )
    agent.add_callback(rich_ui)
    
    # Run the agent with a complex query that will require multiple steps
    user_input = "Plan a trip to Toronto for 7 days in the next month."
    agent_logger.info(f"Running agent with input: {user_input}")
    result = await agent.run(user_input, max_turns=15)
    
    # Show memory stats
    memory_stats = agent.get_memory_stats()
    agent_logger.info(f"Memory management statistics: {memory_stats}")
    
    agent_logger.info(f"Final result: {result}")
    
    # Clean up
    await agent.close()
    agent_logger.debug("Example completed")

if __name__ == "__main__":
    asyncio.run(run_example()) 