#
#
#
#
#
# tool call and tool error with same tool id should have the same importance level, otherwise LLM would reject it.
#- tool call ==> tool error, should be MEDIUM . if there is no pair of tool call ==> tool error after that (It is the last error)
#- should be LOW, if another pair of tool call ==> tool response (response without error) happens after it.
#- if this happens at the end of conversation, the rule of HIGH importance will overrule everything, so they would be HIGh priority. 
# Last message pairs should be high priority.
#
# tool_call => tool is a pair, and share the same importance level
#
#
# if 'role': 'assistant',
#   'content': '',
#   'tool_calls => function ==> name 
#
# should share same level of importance for it's response with role = tool and same tool_call_id

# last 3 pairs in the history should have HIGH importance
#
#
#
# memory_manager.py
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class MessageImportance(Enum):
    """Defines the importance levels for messages."""
    CRITICAL = "critical"      # Must always be kept (system, final answers, etc.)
    HIGH = "high"             # Important context, keep unless absolutely necessary
    MEDIUM = "medium"         # Standard conversation, can be summarized
    LOW = "low"              # Tool errors, failed attempts, can be removed
    TEMP = "temp"            # Temporary messages, remove after success

class MessageType(Enum):
    """Categorizes different types of messages."""
    SYSTEM = "system"
    USER_QUERY = "user_query"
    ASSISTANT_RESPONSE = "assistant_response"
    TOOL_CALL = "tool_call"
    TOOL_RESPONSE = "tool_response"
    TOOL_ERROR = "tool_error"
    FINAL_ANSWER = "final_answer"
    QUESTION_TO_USER = "question_to_user"

@dataclass
class MessageMetadata:
    """Metadata for tracking message importance and lifecycle."""
    message_type: MessageType
    importance: MessageImportance
    created_at: float
    token_count: int = 0
    is_error: bool = False
    error_resolved: bool = False
    part_of_task: Optional[str] = None  # Task/subtask identifier
    task_completed: bool = False
    can_summarize: bool = True
    summary: Optional[str] = None
    related_messages: List[int] = field(default_factory=list)  # Indices of related messages
    tool_call_id: Optional[str] = None  # To track tool call/response pairs
    function_name: Optional[str] = None  # The actual function name for tool calls/responses

class MemoryStrategy(ABC):
    """Abstract base class for memory management strategies."""
    
    @abstractmethod
    def should_keep_message(self, message: Dict[str, Any], metadata: MessageMetadata, 
                          context: Dict[str, Any]) -> bool:
        """Determine if a message should be kept in memory."""
        pass
    
    @abstractmethod
    def get_priority_score(self, message: Dict[str, Any], metadata: MessageMetadata) -> float:
        """Get priority score for message ranking."""
        pass

class ConservativeStrategy(MemoryStrategy):
    """Conservative strategy - keeps more messages, summarizes less aggressively."""
    
    def should_keep_message(self, message: Dict[str, Any], metadata: MessageMetadata, 
                          context: Dict[str, Any]) -> bool:
        # Always keep critical messages
        if metadata.importance == MessageImportance.CRITICAL:
            return True
        
        # Keep high importance messages unless we're really tight on space
        if metadata.importance == MessageImportance.HIGH:
            return context.get('memory_pressure', 0) < 0.8
        
        # Keep recent messages
        if time.time() - metadata.created_at < 300:  # 5 minutes
            return True
        
        # Remove resolved errors and temp messages
        if metadata.importance == MessageImportance.TEMP:
            return False
        
        if metadata.is_error and metadata.error_resolved:
            return False
        
        return context.get('memory_pressure', 0) < 0.6
    
    def get_priority_score(self, message: Dict[str, Any], metadata: MessageMetadata) -> float:
        base_score = {
            MessageImportance.CRITICAL: 1000,
            MessageImportance.HIGH: 100,
            MessageImportance.MEDIUM: 50,
            MessageImportance.LOW: 10,
            MessageImportance.TEMP: 1
        }[metadata.importance]
        
        # Boost recent messages
        age_factor = max(0.1, 1.0 - (time.time() - metadata.created_at) / 3600)
        
        # Penalize errors
        error_penalty = 0.5 if metadata.is_error else 1.0
        
        return base_score * age_factor * error_penalty

class AggressiveStrategy(MemoryStrategy):
    """Aggressive strategy - removes more messages, summarizes more aggressively."""
    
    def should_keep_message(self, message: Dict[str, Any], metadata: MessageMetadata, 
                          context: Dict[str, Any]) -> bool:
        # Always keep critical messages
        if metadata.importance == MessageImportance.CRITICAL:
            return True
        
        # Be more selective with high importance
        if metadata.importance == MessageImportance.HIGH:
            return context.get('memory_pressure', 0) < 0.5 and (time.time() - metadata.created_at < 600)
        
        # Only keep very recent medium importance messages
        if metadata.importance == MessageImportance.MEDIUM:
            return time.time() - metadata.created_at < 180  # 3 minutes
        
        # Remove low importance and temp messages quickly
        return False
    
    def get_priority_score(self, message: Dict[str, Any], metadata: MessageMetadata) -> float:
        base_score = {
            MessageImportance.CRITICAL: 1000,
            MessageImportance.HIGH: 80,
            MessageImportance.MEDIUM: 30,
            MessageImportance.LOW: 5,
            MessageImportance.TEMP: 1
        }[metadata.importance]
        
        # Strong recency bias
        age_factor = max(0.05, 1.0 - (time.time() - metadata.created_at) / 1800)
        
        # Heavy error penalty
        error_penalty = 0.2 if metadata.is_error else 1.0
        
        return base_score * age_factor * error_penalty

class BalancedStrategy(MemoryStrategy):
    """Balanced strategy - moderate approach to memory management."""
    
    def should_keep_message(self, message: Dict[str, Any], metadata: MessageMetadata, 
                          context: Dict[str, Any]) -> bool:
        # Always keep critical messages
        if metadata.importance == MessageImportance.CRITICAL:
            return True
        
        # Keep high importance messages unless high memory pressure
        if metadata.importance == MessageImportance.HIGH:
            return context.get('memory_pressure', 0) < 0.7
        
        # Keep recent medium importance messages
        if metadata.importance == MessageImportance.MEDIUM:
            return time.time() - metadata.created_at < 450  # 7.5 minutes
        
        # Remove resolved errors and temp messages
        if metadata.is_error and metadata.error_resolved:
            return False
        
        if metadata.importance == MessageImportance.TEMP:
            return time.time() - metadata.created_at < 60  # 1 minute
        
        return context.get('memory_pressure', 0) < 0.4
    
    def get_priority_score(self, message: Dict[str, Any], metadata: MessageMetadata) -> float:
        base_score = {
            MessageImportance.CRITICAL: 1000,
            MessageImportance.HIGH: 90,
            MessageImportance.MEDIUM: 40,
            MessageImportance.LOW: 8,
            MessageImportance.TEMP: 2
        }[metadata.importance]
        
        # Moderate recency bias
        age_factor = max(0.1, 1.0 - (time.time() - metadata.created_at) / 2400)
        
        # Moderate error penalty
        error_penalty = 0.3 if metadata.is_error else 1.0
        
        return base_score * age_factor * error_penalty

class MemoryManager:
    """
    Advanced memory management system for TinyAgent.
    
    Features:
    - Message importance tracking with dynamic positioning
    - Intelligent message removal and summarization
    - Multiple memory management strategies
    - Task-based message grouping
    - Error recovery tracking
    - Tool call/response pair integrity
    """
    
    _DEFAULT_NUM_RECENT_PAIRS_HIGH_IMPORTANCE = 3
    _DEFAULT_NUM_INITIAL_PAIRS_CRITICAL = 3

    def __init__(
        self,
        max_tokens: int = 8000,
        target_tokens: int = 6000,
        strategy: MemoryStrategy = None,
        enable_summarization: bool = True,
        logger: Optional[logging.Logger] = None,
        num_recent_pairs_high_importance: Optional[int] = None,
        num_initial_pairs_critical: Optional[int] = None
    ):
        self.max_tokens = max_tokens
        self.target_tokens = target_tokens
        self.strategy = strategy or BalancedStrategy()
        self.enable_summarization = enable_summarization
        self.logger = logger or logging.getLogger(__name__)
        
        # Configure importance thresholds
        self._num_recent_pairs_for_high_importance = (
            num_recent_pairs_high_importance 
            if num_recent_pairs_high_importance is not None 
            else self._DEFAULT_NUM_RECENT_PAIRS_HIGH_IMPORTANCE
        )
        
        self._num_initial_pairs_critical = (
            num_initial_pairs_critical
            if num_initial_pairs_critical is not None
            else self._DEFAULT_NUM_INITIAL_PAIRS_CRITICAL
        )
        
        # Message metadata storage
        self.message_metadata: List[MessageMetadata] = []
        
        # Reference to messages for tool call pairing
        self.messages: Optional[List[Dict[str, Any]]] = None
        
        # Task tracking
        self.active_tasks: Set[str] = set()
        self.completed_tasks: Set[str] = set()
        
        # Summary storage
        self.conversation_summary: Optional[str] = None
        self.task_summaries: Dict[str, str] = {}
        
        # Statistics
        self.stats = {
            'messages_removed': 0,
            'messages_summarized': 0,
            'tokens_saved': 0,
            'memory_optimizations': 0
        }
        
        # Tool call tracking for proper pairing
        self._tool_call_pairs: Dict[str, Tuple[int, int]] = {}  # tool_call_id -> (call_index, response_index)
        self._resolved_errors: Set[str] = set()  # Track resolved error tool_call_ids
        
        # Tool importance overrides (tool_name -> importance_level)
        self._tool_importance_overrides: Dict[str, MessageImportance] = {}
    
    def register_tool_importance_override(self, tool_name: str, importance_level: str) -> None:
        """
        Register a custom importance level for a specific tool.
        
        Args:
            tool_name: Name of the tool
            importance_level: Importance level ("CRITICAL", "HIGH", "MEDIUM", "LOW", "TEMP")
        """
        importance_map = {
            "CRITICAL": MessageImportance.CRITICAL,
            "HIGH": MessageImportance.HIGH,
            "MEDIUM": MessageImportance.MEDIUM,
            "LOW": MessageImportance.LOW,
            "TEMP": MessageImportance.TEMP
        }
        
        importance_level_upper = importance_level.upper()
        if importance_level_upper not in importance_map:
            raise ValueError(f"Invalid importance level '{importance_level}'. Must be one of: {list(importance_map.keys())}")
        
        self._tool_importance_overrides[tool_name] = importance_map[importance_level_upper]
        self.logger.debug(f"Registered tool importance override: {tool_name} -> {importance_level_upper}")
    
    def register_tools_from_agent(self, agent: Any) -> None:
        """
        Register tool importance overrides from an agent's tool configurations.
        
        Args:
            agent: TinyAgent instance with tools
        """
        # Register custom tools
        if hasattr(agent, 'custom_tool_handlers'):
            for tool_name, handler in agent.custom_tool_handlers.items():
                if hasattr(handler, '_tool_metadata'):
                    metadata = handler._tool_metadata
                    memory_importance = metadata.get('memory_importance')
                    if memory_importance:
                        self.register_tool_importance_override(tool_name, memory_importance)
        
        self.logger.debug(f"Registered {len(self._tool_importance_overrides)} tool importance overrides")
    
    def get_tool_importance_override(self, tool_name: str) -> Optional[MessageImportance]:
        """
        Get the importance override for a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            MessageImportance if override exists, None otherwise
        """
        return self._tool_importance_overrides.get(tool_name)
    
    def _count_message_tokens(self, message: Dict[str, Any], token_counter: callable) -> int:
        """
        Properly count tokens in a message, including tool calls.
        
        Args:
            message: The message to count tokens for
            token_counter: Function to count tokens in text
            
        Returns:
            Total token count for the message
        """
        total_tokens = 0
        
        # Count content tokens
        content = message.get('content', '')
        if content:
            total_tokens += token_counter(str(content))
        
        # Count tool call tokens
        if 'tool_calls' in message and message['tool_calls']:
            for tool_call in message['tool_calls']:
                # Handle both dict and object-style tool calls
                if isinstance(tool_call, dict):
                    # Count tool call ID
                    if 'id' in tool_call:
                        total_tokens += token_counter(str(tool_call['id']))
                    
                    # Count function data
                    if 'function' in tool_call:
                        func_data = tool_call['function']
                        if 'name' in func_data:
                            total_tokens += token_counter(func_data['name'])
                        if 'arguments' in func_data:
                            # Arguments are usually JSON strings, count them properly
                            args_str = str(func_data['arguments'])
                            total_tokens += token_counter(args_str)
                    
                    # Count type if present
                    if 'type' in tool_call:
                        total_tokens += token_counter(str(tool_call['type']))
                        
                elif hasattr(tool_call, 'function'):
                    # Handle object-style tool calls
                    if hasattr(tool_call, 'id'):
                        total_tokens += token_counter(str(tool_call.id))
                    if hasattr(tool_call.function, 'name'):
                        total_tokens += token_counter(tool_call.function.name)
                    if hasattr(tool_call.function, 'arguments'):
                        total_tokens += token_counter(str(tool_call.function.arguments))
        
        # Count tool call ID for tool responses
        if 'tool_call_id' in message and message['tool_call_id']:
            total_tokens += token_counter(str(message['tool_call_id']))
        
        # Count tool name for tool responses
        if 'name' in message and message.get('role') == 'tool':
            total_tokens += token_counter(str(message['name']))
        
        return total_tokens
    
    def _calculate_dynamic_importance(
        self, 
        message: Dict[str, Any], 
        index: int, 
        total_messages: int, 
        message_pairs: List[Tuple[int, int]],
        messages: Optional[List[Dict[str, Any]]] = None
    ) -> MessageImportance:
        """
        Calculate dynamic importance using a hierarchical rule-based system.
        
        Rules are applied in order of precedence:
        1. Absolute Rules (cannot be overridden)
        2. Content-Based Rules (based on message content/type)
        3. Position-Based Rules (based on conversation position)
        4. Default Rules (fallback based on role)
        
        Args:
            message: The message to evaluate
            index: Position of the message in the conversation
            total_messages: Total number of messages
            message_pairs: List of message pair ranges
            messages: Optional array of messages for better user message detection
            
        Returns:
            MessageImportance level
        """
        role = message.get('role', '')
        content = str(message.get('content', ''))
        
        # ===== ABSOLUTE RULES (Highest Priority - Cannot be overridden) =====
        
        # Rule 1: System messages are always CRITICAL
        if role == 'system':
            return MessageImportance.CRITICAL
        
        # Rule 2: First user message is always CRITICAL (as per requirements)
        if role == 'user' and self._is_first_user_message(index):
            return MessageImportance.CRITICAL
        
        # ===== CONTENT-BASED RULES (Second Priority) =====
        
        # Rule 3: Final answers and ask_question are HIGH
        if role == 'assistant' and message.get('tool_calls'):
            tool_calls = message.get('tool_calls', [])
            if any(tc.get('function', {}).get('name') in ['final_answer', 'ask_question'] 
                   for tc in tool_calls):
                return MessageImportance.HIGH
        
        # Rule 4: Resolved errors are LOW importance
        if self._is_tool_error_response(message):
            return MessageImportance.HIGH
        
        # ===== TOOL IMPORTANCE OVERRIDES (Third Priority) =====
        
        # Rule 5: Tool importance overrides from @tool decorator
        if message.get('role') == 'tool':
            tool_override = self.get_tool_importance_override(message.get('name', 'unknown'))
            if tool_override is not None:
                self.logger.debug(f"Applying tool importance override for {message.get('name', 'unknown')}: {tool_override.value}")
                return tool_override
        elif message.get('role') == 'assistant' and message.get('tool_calls'):
            # Apply tool overrides to tool calls as well
            tool_calls = message.get('tool_calls', [])
            for tool_call in tool_calls:
                function_name = tool_call.get('function', {}).get('name')
                if function_name:
                    tool_override = self.get_tool_importance_override(function_name)
                    if tool_override is not None:
                        self.logger.debug(f"Applying tool importance override for tool call {function_name}: {tool_override.value}")
                        return tool_override
        
        # ===== POSITION-BASED RULES (Fourth Priority) =====
        
        # Apply positional rules based on message pairs
        current_pair_index = self._find_message_pair_index(index, message_pairs)
        
        if current_pair_index is not None:
            # Debug logging
            self.logger.debug(f"Recalc - Message at index {index}: pair_index={current_pair_index}, total_pairs={len(message_pairs)}, last_{self._num_recent_pairs_for_high_importance}_threshold={len(message_pairs) - self._num_recent_pairs_for_high_importance}")
            
            # Rule 4: First N pairs are CRITICAL for longer conversations
            if (total_messages > 10 and 
                current_pair_index < self._num_initial_pairs_critical):
                return MessageImportance.CRITICAL
            
            # Rule 5: Last N pairs are HIGH (most recent pairs) - applies to all conversations
            if current_pair_index >= len(message_pairs) - self._num_recent_pairs_for_high_importance:
                self.logger.debug(f"Recalc - Applying HIGH importance due to recency rule for message at index {index}")
                return MessageImportance.HIGH
        
        # ===== ERROR-BASED RULES (Fourth Priority) =====
        
        # Rule 6: Tool errors are HIGH importance by default (per memory.md guidelines)
        if self._is_tool_error_response(message):
            return MessageImportance.HIGH
        
        # ===== DEFAULT RULES (Lowest Priority - Fallback) =====
        
        # Rule 8: User messages (except first and last) are HIGH
        if role == 'user':
            # Check if this is the last user message
            if messages is not None:
                is_last_user = self._is_last_user_message_in_array(index, messages)
            else:
                is_last_user = self._is_last_user_message(index, total_messages)
            
            if not is_last_user:  # Not first (handled above) and not last
                return MessageImportance.HIGH
            else:
                return MessageImportance.MEDIUM  # Last user message is MEDIUM
        
        # Rule 9: Assistant responses based on content complexity
        if role == 'assistant':
            if len(content) > 500:  # Substantial responses are MEDIUM
                return MessageImportance.MEDIUM
            else:
                return MessageImportance.LOW
        
        # Rule 10: Tool responses are MEDIUM (unless errors, handled above)
        if role == 'tool':
            return MessageImportance.MEDIUM
        
        # Rule 11: Default fallback
        return MessageImportance.LOW
    
    def _is_first_user_message(self, current_index: int) -> bool:
        """
        Check if the current message is the first user message in the conversation.
        This works during initial categorization when we don't have full metadata yet.
        
        Args:
            current_index: Index of the current message being processed
            
        Returns:
            True if this is the first user message
        """
        # Check all previous messages in metadata to see if any were user messages
        for i in range(current_index):
            if i < len(self.message_metadata):
                if self.message_metadata[i].message_type == MessageType.USER_QUERY:
                    return False  # Found an earlier user message
        
        # If we reach here, no previous user messages were found
        return True
    
    def _find_message_pair_index(self, message_index: int, message_pairs: List[Tuple[int, int]]) -> Optional[int]:
        """
        Find which pair index a message belongs to.
        
        Args:
            message_index: Index of the message
            message_pairs: List of message pair ranges
            
        Returns:
            Pair index or None if not found
        """
        for pair_idx, (start_idx, end_idx) in enumerate(message_pairs):
            if start_idx <= message_index <= end_idx:
                return pair_idx
        return None
    
    def add_message_metadata(
        self, 
        message: Dict[str, Any], 
        token_count: int, 
        position: int, 
        total_messages: int,
        messages: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add metadata for a message and update tool call pairs.
        
        Args:
            message: The message to add metadata for
            token_count: Number of tokens in the message
            position: Position of the message in the conversation
            total_messages: Total number of messages in the conversation
            messages: Optional array of messages for better user message detection
        """
        # Extract tool call ID and function name first (before categorization)
        tool_call_id = None
        function_name = None
        
        if message.get('role') == 'tool':
            # Tool response - get tool_call_id directly
            tool_call_id = message.get('tool_call_id')
            function_name = message.get('name')  # Tool responses have 'name' field
        elif message.get('role') == 'assistant' and message.get('tool_calls'):
            # Tool call - for multi-tool-call messages, we'll store the first one in metadata
            # but _update_tool_call_pairs will handle all tool calls by examining the actual message
            tool_calls = message.get('tool_calls', [])
            if tool_calls:
                tool_call_id = tool_calls[0].get('id')
                # Extract function name from the tool call
                function_data = tool_calls[0].get('function', {})
                function_name = function_data.get('name')
        
        # Create preliminary metadata without importance calculation
        is_error = self._is_tool_error_response(message)
        task_id = self._extract_task_id(message)
        if task_id:
            self.active_tasks.add(task_id)
        
        # Determine message type first
        role = message.get('role', '')
        if role == 'system':
            msg_type = MessageType.SYSTEM
        elif role == 'user':
            msg_type = MessageType.USER_QUERY
        elif role == 'tool':
            if is_error:
                msg_type = MessageType.TOOL_ERROR
            else:
                msg_type = MessageType.TOOL_RESPONSE
        elif role == 'assistant':
            if message.get('tool_calls'):
                # Check if this is a final_answer or ask_question tool call
                tool_calls = message.get('tool_calls', [])
                if any(tc.get('function', {}).get('name') == 'final_answer' 
                       for tc in tool_calls):
                    msg_type = MessageType.FINAL_ANSWER
                elif any(tc.get('function', {}).get('name') == 'ask_question' 
                         for tc in tool_calls):
                    msg_type = MessageType.QUESTION_TO_USER
                else:
                    msg_type = MessageType.TOOL_CALL
            else:
                msg_type = MessageType.ASSISTANT_RESPONSE
        else:
            msg_type = MessageType.ASSISTANT_RESPONSE
        
        # Create metadata with temporary LOW importance (will be recalculated)
        metadata = MessageMetadata(
            message_type=msg_type,
            importance=MessageImportance.LOW,  # Temporary, will be recalculated
            created_at=time.time(),
            token_count=token_count,
            is_error=is_error,
            error_resolved=False,
            part_of_task=task_id,
            task_completed=task_id in self.completed_tasks if task_id else False,
            tool_call_id=tool_call_id,
            can_summarize=msg_type not in [MessageType.SYSTEM, MessageType.FINAL_ANSWER],
            summary=None,
            function_name=function_name
        )
        
        # Add to metadata list
        self.message_metadata.append(metadata)
        
        # Update tool call pairs FIRST (before importance calculation)
        self._update_tool_call_pairs(messages)
        
        # Update resolved errors
        self._update_resolved_errors()
        
        # Now calculate the correct importance with updated pairs
        message_pairs = self._calculate_message_pairs()
        correct_importance = self._calculate_dynamic_importance(message, position, total_messages, message_pairs, messages)
        metadata.importance = correct_importance
        
        # Synchronize tool call pair importance levels
        self._synchronize_tool_call_pairs()
        
        self.logger.debug(f"Added metadata for message at position {position}: {msg_type.value}, {correct_importance.value}, tool_call_id: {tool_call_id}")

    def _update_tool_call_pairs(self, messages: Optional[List[Dict[str, Any]]] = None) -> None:
        """Update the tool call pairs mapping based on current messages."""
        self._tool_call_pairs.clear()
        
        # First, collect all tool call IDs from assistant messages
        tool_call_messages = {}  # tool_call_id -> message_index
        
        for i, metadata in enumerate(self.message_metadata):
            if metadata.message_type in [MessageType.TOOL_CALL, MessageType.FINAL_ANSWER, MessageType.QUESTION_TO_USER]:
                # This is an assistant message with tool calls, extract all tool call IDs
                # We need to look at the actual message to get all tool calls
                if messages and i < len(messages):
                    message = messages[i]
                    tool_calls = message.get('tool_calls', [])
                    for tool_call in tool_calls:
                        tool_call_id = tool_call.get('id')
                        if tool_call_id:
                            tool_call_messages[tool_call_id] = i
                elif metadata.tool_call_id:
                    # Fallback: use the tool_call_id from metadata if available
                    tool_call_messages[metadata.tool_call_id] = i
        
        # Then, find responses for each tool call
        for i, metadata in enumerate(self.message_metadata):
            if (metadata.tool_call_id and 
                metadata.message_type in [MessageType.TOOL_RESPONSE, MessageType.TOOL_ERROR] and
                metadata.tool_call_id in tool_call_messages):
                
                call_idx = tool_call_messages[metadata.tool_call_id]
                self._tool_call_pairs[metadata.tool_call_id] = (call_idx, i)

    def _recalculate_all_importance_levels(self) -> None:
        """Recalculate importance levels for all messages based on current context."""
        if not self.message_metadata:
            return
        
        # First update resolved errors
        self._update_resolved_errors()
        
        # Update tool call pairs (without messages reference during recalculation)
        self._update_tool_call_pairs()
        
        # Calculate message pairs for context
        message_pairs = self._calculate_message_pairs()
        total_messages = len(self.message_metadata)
        
        # Recalculate importance for each message
        for i, metadata in enumerate(self.message_metadata):
            new_importance = self._calculate_positional_importance(i, total_messages, message_pairs, metadata)
            metadata.importance = new_importance
        
        # After recalculating all, synchronize tool call pairs
        self._synchronize_tool_call_pairs()
        
        self.logger.debug(f"Recalculated importance levels for {total_messages} messages")

    def _calculate_positional_importance(
        self, 
        index: int, 
        total_messages: int, 
        message_pairs: List[Tuple[int, int]],
        metadata: MessageMetadata
    ) -> MessageImportance:
        """
        Calculate importance based on position and message type using the same rule hierarchy.
        This method is used during recalculation when we have full metadata context.
        """
        
        # ===== ABSOLUTE RULES (Highest Priority - Cannot be overridden) =====
        
        # Rule 1: System messages are always CRITICAL
        if metadata.message_type == MessageType.SYSTEM:
            return MessageImportance.CRITICAL
        
        # Rule 2: First user message is always CRITICAL
        if metadata.message_type == MessageType.USER_QUERY and self._is_first_user_message_by_metadata(index):
            return MessageImportance.CRITICAL
        
        # ===== CONTENT-BASED RULES (Second Priority) =====
        
        # Rule 3: Final answers and ask_question are HIGH
        if metadata.message_type in [MessageType.FINAL_ANSWER, MessageType.QUESTION_TO_USER]:
            return MessageImportance.HIGH
        
        # Rule 4: Resolved errors are LOW importance
        if metadata.is_error and metadata.error_resolved:
            return MessageImportance.LOW
        
        # ===== TOOL IMPORTANCE OVERRIDES (Third Priority) =====
        
        # Rule 5: Tool importance overrides from @tool decorator
        if metadata.function_name:
            tool_override = self.get_tool_importance_override(metadata.function_name)
            if tool_override is not None:
                self.logger.debug(f"Applying tool importance override for {metadata.function_name}: {tool_override.value}")
                return tool_override
        
        # ===== POSITION-BASED RULES (Fourth Priority) =====
        
        # Apply positional rules based on message pairs
        current_pair_index = self._find_message_pair_index(index, message_pairs)
        
        if current_pair_index is not None:
            # Debug logging
            self.logger.debug(f"Recalc - Message at index {index}: pair_index={current_pair_index}, total_pairs={len(message_pairs)}, last_{self._num_recent_pairs_for_high_importance}_threshold={len(message_pairs) - self._num_recent_pairs_for_high_importance}")
            
            # Rule 4: First N pairs are CRITICAL for longer conversations
            if (total_messages > 10 and 
                current_pair_index < self._num_initial_pairs_critical):
                return MessageImportance.CRITICAL
            
            # Rule 5: Last N pairs are HIGH (most recent pairs) - applies to all conversations
            if current_pair_index >= len(message_pairs) - self._num_recent_pairs_for_high_importance:
                self.logger.debug(f"Recalc - Applying HIGH importance due to recency rule for message at index {index}")
                return MessageImportance.HIGH
        
        # ===== ERROR-BASED RULES (Fourth Priority) =====
        
        # Rule 7: Unresolved errors are HIGH importance by default (per memory.md guidelines)
        if metadata.is_error and not metadata.error_resolved:
            return MessageImportance.HIGH
        
        # ===== DEFAULT RULES (Lowest Priority - Fallback) =====
        
        # Rule 8: User messages (except first and last) are HIGH
        if metadata.message_type == MessageType.USER_QUERY:
            # Check if this is the last user message
            is_last_user = self._is_last_user_message(index, total_messages)
            if not is_last_user:  # Not first (handled above) and not last
                return MessageImportance.HIGH
            else:
                return MessageImportance.MEDIUM  # Last user message is MEDIUM
        
        # Rule 9: Tool calls and responses are MEDIUM (unless errors, handled above)
        if metadata.message_type in [MessageType.TOOL_CALL, MessageType.TOOL_RESPONSE]:
            return MessageImportance.MEDIUM
        
        # Rule 10: Default fallback
        return MessageImportance.LOW

    def _is_first_user_message_by_metadata(self, current_index: int) -> bool:
        """
        Check if the current message is the first user message using metadata.
        This is used during recalculation when we have full metadata available.
        
        Args:
            current_index: Index of the current message
            
        Returns:
            True if this is the first user message
        """
        for i in range(current_index):
            if i < len(self.message_metadata):
                if self.message_metadata[i].message_type == MessageType.USER_QUERY:
                    return False  # Found an earlier user message
        
        return True  # No earlier user messages found

    def _calculate_message_pairs(self) -> List[Tuple[int, int]]:
        """Calculate logical message pairs for positional importance."""
        pairs = []
        i = 0
        max_iterations = len(self.message_metadata) * 2  # Safety limit
        iterations = 0
        
        while i < len(self.message_metadata) and iterations < max_iterations:
            iterations += 1
            metadata = self.message_metadata[i]
            
            # System message stands alone
            if metadata.message_type == MessageType.SYSTEM:
                pairs.append((i, i))
                i += 1
                continue
            
            # User message followed by assistant response
            if metadata.message_type == MessageType.USER_QUERY:
                if i + 1 < len(self.message_metadata):
                    next_meta = self.message_metadata[i + 1]
                    if next_meta.message_type in [MessageType.ASSISTANT_RESPONSE, MessageType.TOOL_CALL, MessageType.FINAL_ANSWER, MessageType.QUESTION_TO_USER]:
                        pairs.append((i, i + 1))
                        i += 2
                        continue
                
                # User message without response
                pairs.append((i, i))
                i += 1
                continue
            
            # Tool call with response - with safety checks
            if (metadata.tool_call_id and 
                metadata.tool_call_id in self._tool_call_pairs):
                
                call_idx, response_idx = self._tool_call_pairs[metadata.tool_call_id]
                
                # Safety checks to prevent infinite loops
                if (call_idx >= 0 and response_idx >= 0 and 
                    call_idx < len(self.message_metadata) and 
                    response_idx < len(self.message_metadata) and
                    i == call_idx and response_idx > call_idx):
                    
                    pairs.append((call_idx, response_idx))
                    i = response_idx + 1
                    continue
                else:
                    # Invalid pair data, treat as single message
                    self.logger.warning(f"Invalid tool call pair data for {metadata.tool_call_id}: call_idx={call_idx}, response_idx={response_idx}, current_i={i}")
                    pairs.append((i, i))
                    i += 1
                    continue
            
            # Single message
            pairs.append((i, i))
            i += 1
        
        # Safety check for infinite loop detection
        if iterations >= max_iterations:
            self.logger.error(f"Infinite loop detected in _calculate_message_pairs! Breaking after {iterations} iterations. Current index: {i}, metadata count: {len(self.message_metadata)}")
            # Return what we have so far
        
        return pairs

    def _update_resolved_errors(self) -> None:
        """
        Update the set of resolved error tool call IDs.
        Enhanced logic for tool error recovery detection that can be overridden by developers.
        """
        self._resolved_errors.clear()
        
        # Track tool calls that had errors but later succeeded
        error_tool_calls = {}  # tool_call_id -> (function_name, error_index, error_metadata)
        success_tool_calls = {}  # function_name -> [(success_index, success_metadata), ...]
        
        for i, metadata in enumerate(self.message_metadata):
            if metadata.tool_call_id and metadata.function_name:
                if metadata.is_error:
                    # This is an error response
                    error_tool_calls[metadata.tool_call_id] = (metadata.function_name, i, metadata)
                elif metadata.message_type == MessageType.TOOL_RESPONSE:
                    # This is a successful response
                    if metadata.function_name not in success_tool_calls:
                        success_tool_calls[metadata.function_name] = []
                    success_tool_calls[metadata.function_name].append((i, metadata))
        
        # Mark errors as resolved using improved logic
        for tool_call_id, (function_name, error_index, error_metadata) in error_tool_calls.items():
            if function_name in success_tool_calls:
                # Check all successful calls for this function
                for success_index, success_metadata in success_tool_calls[function_name]:
                    # Use overridable method to determine if this represents error recovery
                    if self.is_tool_error_recovery(error_metadata, success_metadata, error_index, success_index):
                        self._resolved_errors.add(tool_call_id)
                        # Update the metadata
                        error_metadata.error_resolved = True
                        self.logger.debug(f"Marked error {tool_call_id} as resolved for function {function_name} (error at {error_index}, success at {success_index})")
                        break  # Found recovery, no need to check more successes

    def is_tool_error_recovery(
        self, 
        error_metadata: MessageMetadata, 
        success_metadata: MessageMetadata, 
        error_index: int, 
        success_index: int
    ) -> bool:
        """
        Determine if a successful tool call represents recovery from an earlier error.
        This method can be overridden by developers for custom error recovery logic.
        
        Args:
            error_metadata: Metadata of the error message
            success_metadata: Metadata of the potential recovery message
            error_index: Index of the error message
            success_index: Index of the success message
            
        Returns:
            True if the success represents recovery from the error
        """
        # Default logic: same function succeeding after the error occurred
        same_function = error_metadata.function_name == success_metadata.function_name
        success_after_error = success_index > error_index
        
        return same_function and success_after_error

    def _get_function_name_for_tool_call(self, tool_call_id: str) -> Optional[str]:
        """Get the function name for a given tool call ID from stored metadata."""
        for metadata in self.message_metadata:
            if metadata.tool_call_id == tool_call_id:
                return metadata.function_name
        return None

    def _extract_function_from_tool_call_id(self, tool_call_id: str) -> Optional[str]:
        """Extract a function identifier from tool call ID for error resolution tracking."""
        # This is a simplified approach - in a real implementation, you'd want to 
        # store the function name in the metadata when the tool call is made
        if not tool_call_id:
            return None
        
        # For now, we'll use the tool_call_id itself as a unique identifier
        # This works for the current use case where we're tracking if the same
        # type of operation succeeded later
        return tool_call_id

    def _synchronize_tool_call_pairs(self) -> None:
        """Ensure tool call pairs have synchronized importance levels."""
        # First pass: handle individual pairs
        for tool_call_id, (call_idx, response_idx) in self._tool_call_pairs.items():
            if (call_idx < len(self.message_metadata) and 
                response_idx < len(self.message_metadata)):
                
                call_meta = self.message_metadata[call_idx]
                response_meta = self.message_metadata[response_idx]
                
                # Special handling for resolved errors - both should be LOW
                if response_meta.is_error and response_meta.error_resolved:
                    call_meta.importance = MessageImportance.LOW
                    response_meta.importance = MessageImportance.LOW
                    self.logger.debug(f"Set resolved error pair {tool_call_id} to LOW importance")
                    continue
                
                # Check if either message has a tool importance override
                call_has_override = call_meta.function_name and self.get_tool_importance_override(call_meta.function_name) is not None
                response_has_override = response_meta.function_name and self.get_tool_importance_override(response_meta.function_name) is not None
                
                if call_has_override or response_has_override:
                    # If either has an override, apply it to both
                    if call_meta.function_name:
                        override_importance = self.get_tool_importance_override(call_meta.function_name)
                        if override_importance:
                            call_meta.importance = override_importance
                            response_meta.importance = override_importance
                            self.logger.debug(f"Applied tool importance override to pair {tool_call_id}: both set to {override_importance.value}")
                            continue
                
                # Use the higher importance level for both (original logic)
                importance_order = [
                    MessageImportance.TEMP,
                    MessageImportance.LOW, 
                    MessageImportance.MEDIUM,
                    MessageImportance.HIGH,
                    MessageImportance.CRITICAL
                ]
                
                call_priority = importance_order.index(call_meta.importance)
                response_priority = importance_order.index(response_meta.importance)
                
                target_importance = importance_order[max(call_priority, response_priority)]
                
                # Update both to use the higher importance
                call_meta.importance = target_importance
                response_meta.importance = target_importance
                
                self.logger.debug(f"Synchronized tool call pair {tool_call_id}: both set to {target_importance.value}")
        
        # Second pass: handle multi-tool-call messages
        # Group tool calls by their call message index
        call_message_groups = {}  # call_idx -> [response_indices]
        
        for tool_call_id, (call_idx, response_idx) in self._tool_call_pairs.items():
            if call_idx not in call_message_groups:
                call_message_groups[call_idx] = []
            call_message_groups[call_idx].append(response_idx)
        
        # For each call message with multiple responses, ensure it has the highest importance
        for call_idx, response_indices in call_message_groups.items():
            if len(response_indices) > 1 and call_idx < len(self.message_metadata):
                call_meta = self.message_metadata[call_idx]
                
                # Find the highest importance among all responses
                max_importance = MessageImportance.TEMP
                importance_order = [
                    MessageImportance.TEMP,
                    MessageImportance.LOW, 
                    MessageImportance.MEDIUM,
                    MessageImportance.HIGH,
                    MessageImportance.CRITICAL
                ]
                
                for response_idx in response_indices:
                    if response_idx < len(self.message_metadata):
                        response_meta = self.message_metadata[response_idx]
                        response_priority = importance_order.index(response_meta.importance)
                        max_priority = importance_order.index(max_importance)
                        if response_priority > max_priority:
                            max_importance = response_meta.importance
                
                # Update the call message to have the highest importance
                call_meta.importance = max_importance
                self.logger.debug(f"Updated multi-tool call message at {call_idx} to {max_importance.value} importance")

    def _extract_task_id(self, message: Dict[str, Any]) -> Optional[str]:
        """Extract task identifier from message content."""
        content = str(message.get('content', ''))
        
        # Look for task patterns - be more careful with parsing
        content_lower = content.lower()
        
        # Pattern 1: "task: something"
        if 'task:' in content_lower:
            try:
                parts = content_lower.split('task:')
                if len(parts) > 1:
                    task_part = parts[1].strip().split()[0] if parts[1].strip().split() else None
                    if task_part:
                        # Clean up the task part - remove quotes and special characters
                        task_part = task_part.strip('"\'.,!?;')
                        return f"task_{task_part}" if task_part else None
            except Exception:
                pass
        
        # Pattern 2: Look for common task-related keywords
        task_keywords = ['plan', 'create', 'generate', 'build', 'design', 'analyze']
        for keyword in task_keywords:
            if keyword in content_lower:
                return f"task_{keyword}"
        
        return None
    
    def _is_tool_error_response(self, message: Dict[str, Any]) -> bool:
        """
        Enhanced helper to determine if a tool response is an error.
        This method can be overridden by developers for custom error detection.
        
        Args:
            message: The tool response message to check
            
        Returns:
            True if the message represents an error, False otherwise
        """
        if message.get('role') != 'tool':
            return False
        
        content = str(message.get('content', '')).lower()
        
        # Check if content starts with common error prefixes
        error_prefixes = [
            'error', 'error executing', 'failed to', 'unable to',
            'could not', 'cannot', 'exception:', 'traceback',
            'error', 'failed', 'exception', 'traceback', 'invalid',
            'not found', 'permission denied', 'timeout', 'connection refused',
            'unauthorized', 'forbidden', 'bad request', 'internal server error',
            'syntax error', 'runtime error', 'type error', 'value error',
            'file not found', 'access denied', 'network error'
        ]
        
        # Check for error indicators
        
        has_error_prefix = any(content.startswith(prefix) for prefix in error_prefixes)
        
        return has_error_prefix 
    
    def is_tool_error_response(self, message: Dict[str, Any]) -> bool:
        """
        Public method for error detection that can be easily overridden by developers.
        
        Args:
            message: The tool response message to check
            
        Returns:
            True if the message represents an error, False otherwise
        """
        return self._is_tool_error_response(message)
    
    def calculate_memory_pressure(self, total_tokens: int) -> float:
        """Calculate current memory pressure (0.0 to 1.0)."""
        return min(1.0, total_tokens / self.max_tokens)
    
    def should_optimize_memory(self, total_tokens: int) -> bool:
        """Determine if memory optimization is needed."""
        return total_tokens > self.target_tokens
    
    def optimize_messages(
        self, 
        messages: List[Dict[str, Any]], 
        token_counter: callable
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Optimize message list by removing/summarizing ONLY less important messages.
        
        CONSERVATIVE PRINCIPLE: 
        - NEVER remove CRITICAL, HIGH, or USER messages
        - Only remove LOW, TEMP, and MEDIUM messages when absolutely necessary
        - If we can't get under the limit without removing important messages, accept going over the limit
        - Preserve conversation integrity and tool call/response pairs
        """
        # RULE: If there are less than 10 messages in the history, there is no need to remove any pairs
        if len(messages) < 10:
            total_tokens = sum(self._count_message_tokens(msg, token_counter) for msg in messages)
            return messages, {
                'action': 'none', 
                'reason': 'less_than_10_messages',
                'message_count': len(messages),
                'total_tokens': total_tokens
            }
        
        # Ensure metadata is up to date
        if len(messages) > len(self.message_metadata):
            for i in range(len(self.message_metadata), len(messages)):
                msg = messages[i]
                token_count = self._count_message_tokens(msg, token_counter)
                self.add_message_metadata(msg, token_count, i, len(messages), messages)
        
        if len(messages) != len(self.message_metadata):
            self.logger.warning("Message count mismatch with metadata")
            return messages, {"error": "Message metadata mismatch"}
        
        # Recalculate importance levels based on current conversation state
        self._recalculate_all_importance_levels()
        
        # Calculate current token usage using proper token counting
        total_tokens = sum(self._count_message_tokens(msg, token_counter) for msg in messages)
        
        if not self.should_optimize_memory(total_tokens):
            return messages, {'action': 'none', 'reason': 'within_limits'}
        
        memory_pressure = self.calculate_memory_pressure(total_tokens)
        context = {'memory_pressure': memory_pressure}
        
        self.logger.info(f"Memory optimization needed. Total tokens: {total_tokens}, pressure: {memory_pressure:.2f}")
        self.logger.debug(f"DEBUG: Memory optimization starting with {len(messages)} messages")
        
        # Debug: Log all message importance levels
        for i, (msg, meta) in enumerate(zip(messages, self.message_metadata)):
            self.logger.debug(f"DEBUG: Message {i} ({meta.message_type.value}): {meta.importance.value} - {str(msg.get('content', ''))[:50]}...")
        
        # Find all tool call/response pairs
        tool_call_pairs = self._tool_call_pairs
        self.logger.debug(f"DEBUG: Found {len(tool_call_pairs)} tool call pairs to preserve")
        
        # STEP 1: Identify messages that are NEVER removable
        never_remove_indices = set()
        
        for i, meta in enumerate(self.message_metadata):
            # Never remove these importance levels
            if meta.importance in [MessageImportance.CRITICAL, MessageImportance.HIGH]:
                never_remove_indices.add(i)
            # Never remove user messages regardless of importance 
            elif meta.message_type == MessageType.USER_QUERY:
                never_remove_indices.add(i)
        
        # STEP 2: Identify tool call pairs and their combined importance
        pair_groups = {}  # Maps group_id to set of indices
        pair_importance = {}  # Maps group_id to max importance in pair
        
        for tool_call_id, (call_idx, response_idx) in tool_call_pairs.items():
            group_id = f"pair_{tool_call_id}"
            pair_groups[group_id] = {call_idx, response_idx}
            
            # Determine pair importance (use the higher of the two)
            call_meta = self.message_metadata[call_idx] if call_idx < len(self.message_metadata) else None
            response_meta = self.message_metadata[response_idx] if response_idx < len(self.message_metadata) else None
            
            if call_meta and response_meta:
                importance_order = [
                    MessageImportance.TEMP,
                    MessageImportance.LOW,
                    MessageImportance.MEDIUM,
                    MessageImportance.HIGH,
                    MessageImportance.CRITICAL
                ]
                call_priority = importance_order.index(call_meta.importance)
                response_priority = importance_order.index(response_meta.importance)
                max_importance = importance_order[max(call_priority, response_priority)]
                pair_importance[group_id] = max_importance
                
                # If either message in the pair is never removable, protect the whole pair
                if call_idx in never_remove_indices or response_idx in never_remove_indices:
                    never_remove_indices.update({call_idx, response_idx})
        
        # STEP 3: Identify candidates for removal (only LOW, TEMP, MEDIUM)
        removal_candidates = []  # List of (index, metadata, tokens, is_pair_group)
        
        for i, meta in enumerate(self.message_metadata):
            if i in never_remove_indices:
                continue  # Skip never-removable messages
                
            # Only consider LOW, TEMP, and MEDIUM for removal
            if meta.importance in [MessageImportance.LOW, MessageImportance.TEMP, MessageImportance.MEDIUM]:
                msg_tokens = self._count_message_tokens(messages[i], token_counter)
                
                # Check if this message is part of a tool call pair
                is_in_pair = False
                pair_group_id = None
                for group_id, indices in pair_groups.items():
                    if i in indices:
                        is_in_pair = True
                        pair_group_id = group_id
                        break
                
                if is_in_pair:
                    # For pairs, only add if we haven't already added this pair and it's removable
                    if (pair_group_id not in [candidate[4] for candidate in removal_candidates if len(candidate) > 4] and
                        pair_importance.get(pair_group_id, MessageImportance.MEDIUM) in [MessageImportance.LOW, MessageImportance.TEMP, MessageImportance.MEDIUM]):
                        
                        # Calculate tokens for the entire pair
                        pair_indices = sorted(pair_groups[pair_group_id])
                        pair_tokens = sum(self._count_message_tokens(messages[idx], token_counter) for idx in pair_indices)
                        removal_candidates.append((min(pair_indices), meta, pair_tokens, True, pair_group_id, pair_indices))
                else:
                    # Single message
                    removal_candidates.append((i, meta, msg_tokens, False))
        
        # STEP 4: Sort candidates by priority (remove least important first)
        def get_removal_priority(candidate):
            importance_priority = {
                MessageImportance.TEMP: 0,
                MessageImportance.LOW: 1,
                MessageImportance.MEDIUM: 2
            }
            return importance_priority.get(candidate[1].importance, 999)
        
        removal_candidates.sort(key=get_removal_priority)
        
        self.logger.debug(f"DEBUG: Found {len(removal_candidates)} removal candidates")
        
        # STEP 5: Try to optimize by removing candidates until we're under the target
        optimized_messages = messages.copy()
        optimized_metadata = self.message_metadata.copy()
        tokens_saved = 0
        messages_removed = 0
        messages_summarized = 0
        removed_indices = set()
        
        current_tokens = total_tokens
        
        for candidate in removal_candidates:
            if current_tokens <= self.target_tokens:
                break  # We've achieved our target
                
            if len(candidate) == 6:  # This is a pair
                _, meta, pair_tokens, is_pair, pair_group_id, pair_indices = candidate
                
                # Check if we can summarize instead of removing
                if self.enable_summarization and meta.can_summarize and not meta.summary:
                    # Try summarizing the pair
                    summary_tokens = 0
                    can_summarize_pair = True
                    
                    for idx in pair_indices:
                        if idx not in removed_indices:
                            summary = self._summarize_message(messages[idx])
                            summary_tokens += token_counter(summary)
                    
                    if summary_tokens < pair_tokens and current_tokens - pair_tokens + summary_tokens <= self.target_tokens:
                        # Summarize the pair
                        for idx in pair_indices:
                            if idx not in removed_indices:
                                summary = self._summarize_message(messages[idx])
                                optimized_messages[idx] = messages[idx].copy()
                                optimized_messages[idx]['content'] = summary
                                optimized_metadata[idx].summary = summary
                        
                        tokens_saved += pair_tokens - summary_tokens
                        messages_summarized += len(pair_indices)
                        current_tokens = current_tokens - pair_tokens + summary_tokens
                        self.logger.debug(f"DEBUG: Summarized tool call pair {pair_indices} - saved {pair_tokens - summary_tokens} tokens")
                        continue
                
                # Remove the entire pair
                for idx in pair_indices:
                    if idx not in removed_indices:
                        removed_indices.add(idx)
                
                tokens_saved += pair_tokens
                messages_removed += len(pair_indices)
                current_tokens -= pair_tokens
                self.logger.debug(f"DEBUG: Removed tool call pair {pair_indices} ({meta.importance.value}) - saved {pair_tokens} tokens")
                
            else:  # Single message
                i, meta, msg_tokens, is_pair = candidate
                
                if i in removed_indices:
                    continue  # Already removed as part of a pair
                
                # Try summarization first
                if self.enable_summarization and meta.can_summarize and not meta.summary:
                    summary = self._summarize_message(messages[i])
                    summary_tokens = token_counter(summary)
                    
                    if summary_tokens < msg_tokens and current_tokens - msg_tokens + summary_tokens <= self.target_tokens:
                        # Summarize this message
                        optimized_messages[i] = messages[i].copy()
                        optimized_messages[i]['content'] = summary
                        optimized_metadata[i].summary = summary
                        
                        tokens_saved += msg_tokens - summary_tokens
                        messages_summarized += 1
                        current_tokens = current_tokens - msg_tokens + summary_tokens
                        self.logger.debug(f"DEBUG: Summarized message {i} ({meta.importance.value}) - saved {msg_tokens - summary_tokens} tokens")
                        continue
                
                # Remove the message
                removed_indices.add(i)
                tokens_saved += msg_tokens
                messages_removed += 1
                current_tokens -= msg_tokens
                self.logger.debug(f"DEBUG: Removed message {i} ({meta.importance.value}) - saved {msg_tokens} tokens")
        
        # STEP 6: Build final optimized message list
        if removed_indices:
            final_messages = []
            final_metadata = []
            
            for i, (msg, meta) in enumerate(zip(optimized_messages, optimized_metadata)):
                if i not in removed_indices:
                    final_messages.append(msg)
                    final_metadata.append(meta)
            
            optimized_messages = final_messages
            optimized_metadata = final_metadata
        
        # Update metadata list
        self.message_metadata = optimized_metadata
        
        # STEP 7: Check if we achieved meaningful optimization
        final_tokens = sum(self._count_message_tokens(msg, token_counter) for msg in optimized_messages)
        
        if final_tokens > self.target_tokens and tokens_saved == 0:
            # We couldn't optimize without removing important messages - return original
            self.message_metadata = self.message_metadata  # Restore original metadata
            self.logger.info(f"Memory optimization skipped: Cannot reduce tokens without removing important messages. "
                           f"Current: {total_tokens}, Target: {self.target_tokens}")
            return messages, {
                'action': 'none', 
                'reason': 'cannot_optimize_without_removing_important_messages',
                'total_tokens': total_tokens,
                'target_tokens': self.target_tokens
            }
        
        # Update statistics
        self.stats['messages_removed'] += messages_removed
        self.stats['messages_summarized'] += messages_summarized
        self.stats['tokens_saved'] += tokens_saved
        self.stats['memory_optimizations'] += 1
        
        optimization_info = {
            'action': 'optimized',
            'original_tokens': total_tokens,
            'final_tokens': final_tokens,
            'tokens_saved': tokens_saved,
            'messages_removed': messages_removed,
            'messages_summarized': messages_summarized,
            'memory_pressure_before': memory_pressure,
            'memory_pressure_after': self.calculate_memory_pressure(final_tokens),
            'tool_pairs_preserved': len([pair for pair in tool_call_pairs.values() 
                                       if not any(idx in removed_indices for idx in pair)]),
            'important_messages_preserved': len([i for i in never_remove_indices if i not in removed_indices])
        }
        
        self.logger.info(f"Memory optimization completed: {optimization_info}")
        
        # Final validation: ensure tool call integrity is maintained
        remaining_tool_pairs = {}
        for tool_call_id, (call_idx, response_idx) in tool_call_pairs.items():
            # Map old indices to new indices
            new_call_idx = None
            new_response_idx = None
            new_idx = 0
            
            for old_idx in range(len(messages)):
                if old_idx not in removed_indices:
                    if old_idx == call_idx:
                        new_call_idx = new_idx
                    if old_idx == response_idx:
                        new_response_idx = new_idx
                    new_idx += 1
            
            if new_call_idx is not None and new_response_idx is not None:
                remaining_tool_pairs[tool_call_id] = (new_call_idx, new_response_idx)
        
        # Update tool call pairs with new indices
        self._tool_call_pairs = remaining_tool_pairs
        
        if len(remaining_tool_pairs) != len([pair for pair in tool_call_pairs.values() 
                                           if not any(idx in removed_indices for idx in pair)]):
            self.logger.warning("Tool call/response integrity may be compromised during index remapping")
        
        return optimized_messages, optimization_info
    
    def _summarize_message(self, message: Dict[str, Any]) -> str:
        """Create a summary of a message."""
        content = str(message.get('content', ''))
        role = message.get('role', '')
        
        # Simple summarization - could be enhanced with LLM-based summarization
        if role == 'tool':
            tool_name = message.get('name', 'unknown')
            if len(content) > 200:
                return f"[SUMMARY] Tool {tool_name} executed: {content[:100]}... [truncated]"
            return content
        
        if role == 'assistant' and len(content) > 300:
            return f"[SUMMARY] Assistant response: {content[:150]}... [truncated]"
        
        if len(content) > 200:
            return f"[SUMMARY] {content[:100]}... [truncated]"
        
        return content
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory management statistics."""
        return {
            **self.stats,
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len(self.completed_tasks),
            'total_messages': len(self.message_metadata),
            'critical_messages': sum(1 for m in self.message_metadata if m.importance == MessageImportance.CRITICAL),
            'error_messages': sum(1 for m in self.message_metadata if m.is_error),
            'resolved_errors': sum(1 for m in self.message_metadata if m.is_error and m.error_resolved)
        }
    
    def reset_stats(self) -> None:
        """Reset memory management statistics."""
        self.stats = {
            'messages_removed': 0,
            'messages_summarized': 0,
            'tokens_saved': 0,
            'memory_optimizations': 0
        }
    
    def clear_completed_tasks(self) -> None:
        """Clear metadata for completed tasks to free up memory."""
        # Remove metadata for completed, non-critical messages
        kept_metadata = []
        removed_count = 0
        
        for metadata in self.message_metadata:
            if (metadata.task_completed and 
                metadata.importance not in [MessageImportance.CRITICAL, MessageImportance.HIGH] and
                time.time() - metadata.created_at > 1800):  # 30 minutes old
                removed_count += 1
            else:
                kept_metadata.append(metadata)
        
        self.message_metadata = kept_metadata
        self.logger.info(f"Cleared {removed_count} completed task metadata entries")
    
    def mark_task_completed(self, task_id: str) -> None:
        """Mark a task as completed and update related message metadata."""
        if task_id in self.active_tasks:
            self.active_tasks.remove(task_id)
            self.completed_tasks.add(task_id)
            
            # Update metadata for messages related to this task
            for metadata in self.message_metadata:
                if metadata.part_of_task == task_id:
                    metadata.task_completed = True
            
            self.logger.info(f"Marked task '{task_id}' as completed")
        else:
            self.logger.warning(f"Task '{task_id}' not found in active tasks")
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory manager state."""
        return {
            'max_tokens': self.max_tokens,
            'target_tokens': self.target_tokens,
            'enable_summarization': self.enable_summarization,
            'active_tasks': list(self.active_tasks),
            'completed_tasks': list(self.completed_tasks),
            'conversation_summary': self.conversation_summary,
            'task_summaries': self.task_summaries,
            'stats': self.stats,
            'message_metadata': [
                {
                    'message_type': meta.message_type.value,
                    'importance': meta.importance.value,
                    'created_at': meta.created_at,
                    'token_count': meta.token_count,
                    'is_error': meta.is_error,
                    'error_resolved': meta.error_resolved,
                    'part_of_task': meta.part_of_task,
                    'task_completed': meta.task_completed,
                    'can_summarize': meta.can_summarize,
                    'summary': meta.summary,
                    'related_messages': meta.related_messages,
                    'tool_call_id': meta.tool_call_id,
                    'function_name': meta.function_name
                }
                for meta in self.message_metadata
            ]
        }
    
    @classmethod
    def from_dict(
        cls, 
        data: Dict[str, Any], 
        strategy: MemoryStrategy = None,
        logger: Optional[logging.Logger] = None
    ) -> 'MemoryManager':
        """Deserialize memory manager state."""
        manager = cls(
            max_tokens=data.get('max_tokens', 8000),
            target_tokens=data.get('target_tokens', 6000),
            strategy=strategy,
            enable_summarization=data.get('enable_summarization', True),
            logger=logger
        )
        
        manager.active_tasks = set(data.get('active_tasks', []))
        manager.completed_tasks = set(data.get('completed_tasks', []))
        manager.conversation_summary = data.get('conversation_summary')
        manager.task_summaries = data.get('task_summaries', {})
        manager.stats = data.get('stats', manager.stats)
        
        # Restore message metadata
        metadata_list = data.get('message_metadata', [])
        manager.message_metadata = [
            MessageMetadata(
                message_type=MessageType(meta['message_type']),
                importance=MessageImportance(meta['importance']),
                created_at=meta['created_at'],
                token_count=meta['token_count'],
                is_error=meta['is_error'],
                error_resolved=meta['error_resolved'],
                part_of_task=meta['part_of_task'],
                task_completed=meta['task_completed'],
                can_summarize=meta['can_summarize'],
                summary=meta['summary'],
                related_messages=meta['related_messages'],
                tool_call_id=meta['tool_call_id'],
                function_name=meta['function_name']
            )
            for meta in metadata_list
        ]
        
        return manager

    def recalculate_importance_levels(self, messages: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Public method to trigger recalculation of importance levels.
        This should be called when conversation structure changes significantly.
        
        Args:
            messages: Optional list of messages for validation (not used in calculation)
        """
        self._recalculate_all_importance_levels()
        self.logger.info("Manually triggered importance level recalculation")

    def _is_last_user_message(self, index: int, total_messages: int) -> bool:
        """
        Check if the current message is the last user message in the conversation.
        
        Args:
            index: Position of the current message
            total_messages: Total number of messages in the conversation
            
        Returns:
            True if this is the last user message
        """
        # During initial calculation, we might not have all metadata yet
        # Check if there are any user messages after this one in metadata
        for i in range(index + 1, min(len(self.message_metadata), total_messages)):
            if i < len(self.message_metadata):
                if self.message_metadata[i].message_type == MessageType.USER_QUERY:
                    return False  # Found a later user message
        
        # If we don't have metadata beyond current index, this might be during initial calculation
        # In that case, we can't determine if it's the last user message, so assume it's not
        if len(self.message_metadata) <= index + 1:
            return False
        
        # No user messages found after this one, so this is the last
        return True

    def _is_last_user_message_in_array(self, index: int, messages: List[Dict[str, Any]]) -> bool:
        """
        Check if the current message is the last user message by looking at the messages array.
        This is used during initial calculation when metadata might not be complete.
        
        Args:
            index: Position of the current message
            messages: Array of messages to check
            
        Returns:
            True if this is the last user message
        """
        # Check if there are any user messages after this one in the messages array
        for i in range(index + 1, len(messages)):
            if messages[i].get('role') == 'user':
                return False  # Found a later user message
        
        # No user messages found after this one, so this is the last
        return True