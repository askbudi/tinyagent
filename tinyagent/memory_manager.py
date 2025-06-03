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

# last 4 pair in the history should have HIGH importance
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
                # Count function name
                if isinstance(tool_call, dict):
                    if 'function' in tool_call:
                        func_data = tool_call['function']
                        if 'name' in func_data:
                            total_tokens += token_counter(func_data['name'])
                        if 'arguments' in func_data:
                            total_tokens += token_counter(str(func_data['arguments']))
                    # Count tool call ID
                    if 'id' in tool_call:
                        total_tokens += token_counter(str(tool_call['id']))
                elif hasattr(tool_call, 'function'):
                    # Handle object-style tool calls
                    if hasattr(tool_call.function, 'name'):
                        total_tokens += token_counter(tool_call.function.name)
                    if hasattr(tool_call.function, 'arguments'):
                        total_tokens += token_counter(str(tool_call.function.arguments))
                    if hasattr(tool_call, 'id'):
                        total_tokens += token_counter(str(tool_call.id))
        
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
        message_pairs: List[Tuple[int, int]]
    ) -> MessageImportance:
        """
        Calculate dynamic importance based on position, content, and context.
        
        Args:
            message: The message to evaluate
            index: Position of the message in the conversation
            total_messages: Total number of messages
            message_pairs: List of message pair ranges
            
        Returns:
            MessageImportance level
        """
        role = message.get('role', '')
        content = str(message.get('content', ''))
        
        # System messages are always CRITICAL
        if role == 'system':
            return MessageImportance.CRITICAL
        
        # Check if this is a final_answer or ask_question tool call (HIGH importance)
        if role == 'assistant' and message.get('tool_calls'):
            tool_calls = message.get('tool_calls', [])
            if any(tc.get('function', {}).get('name') in ['final_answer', 'ask_question'] 
                   for tc in tool_calls):
                return MessageImportance.HIGH
        
        # Check if this is an error response (HIGH importance until resolved)
        if self._is_tool_error_response(message):
            return MessageImportance.HIGH
        
        # Position-based importance (first N pairs are CRITICAL, last N pairs are HIGH)
        if total_messages <= 10:
            # For short conversations, keep everything at MEDIUM or higher
            return MessageImportance.MEDIUM
        
        # Find which pair this message belongs to
        current_pair_index = None
        for pair_idx, (start_idx, end_idx) in enumerate(message_pairs):
            if start_idx <= index <= end_idx:
                current_pair_index = pair_idx
                break
        
        if current_pair_index is not None:
            # First N pairs are CRITICAL
            if current_pair_index < self._num_initial_pairs_critical:
                return MessageImportance.CRITICAL
            
            # Last N pairs are HIGH
            if current_pair_index >= len(message_pairs) - self._num_recent_pairs_for_high_importance:
                return MessageImportance.HIGH
        
        # Content-based importance adjustments
        if role == 'user':
            # User queries are generally important
            return MessageImportance.MEDIUM
        elif role == 'assistant':
            # Assistant responses vary by content length and complexity
            if len(content) > 500:  # Long responses might be more important
                return MessageImportance.MEDIUM
            else:
                return MessageImportance.LOW
        elif role == 'tool':
            # Tool responses are generally MEDIUM unless they're errors
            return MessageImportance.MEDIUM
        
        # Default importance
        return MessageImportance.LOW
    
    def categorize_message(self, message: Dict[str, Any], index: int, total_messages: int) -> Tuple[MessageType, MessageImportance]:
        """
        Categorize a message and determine its base importance.
        
        Args:
            message: The message to categorize
            index: Position of the message in the conversation
            total_messages: Total number of messages in the conversation
            
        Returns:
            Tuple of (MessageType, MessageImportance)
        """
        role = message.get('role', '')
        content = message.get('content', '')
        
        # Determine message type
        if role == 'system':
            msg_type = MessageType.SYSTEM
        elif role == 'user':
            msg_type = MessageType.USER_QUERY
        elif role == 'tool':
            if self._is_tool_error_response(message):
                msg_type = MessageType.TOOL_ERROR
            else:
                msg_type = MessageType.TOOL_RESPONSE
        elif role == 'assistant':
            if message.get('tool_calls'):
                # Check if this is a final_answer or ask_question tool call
                tool_calls = message.get('tool_calls', [])
                if any(tc.get('function', {}).get('name') in ['final_answer', 'ask_question'] 
                       for tc in tool_calls):
                    msg_type = MessageType.FINAL_ANSWER
                else:
                    msg_type = MessageType.TOOL_CALL
            else:
                msg_type = MessageType.ASSISTANT_RESPONSE
        else:
            msg_type = MessageType.ASSISTANT_RESPONSE
        
        # Calculate message pairs for dynamic importance
        message_pairs = self._calculate_message_pairs()
        
        # Calculate dynamic importance
        importance = self._calculate_dynamic_importance(message, index, total_messages, message_pairs)
        
        return msg_type, importance
    
    def add_message_metadata(
        self, 
        message: Dict[str, Any], 
        token_count: int, 
        position: int, 
        total_messages: int
    ) -> None:
        """
        Add metadata for a message and update tool call pairs.
        
        Args:
            message: The message to add metadata for
            token_count: Number of tokens in the message
            position: Position of the message in the conversation
            total_messages: Total number of messages in the conversation
        """
        # Categorize the message
        msg_type, base_importance = self.categorize_message(message, position, total_messages)
        
        # Extract task information
        task_id = self._extract_task_id(message)
        if task_id:
            self.active_tasks.add(task_id)
        
        # Check if this is an error message
        is_error = self._is_tool_error_response(message)
        
        # Extract tool call ID - handle both tool calls and tool responses
        tool_call_id = None
        if message.get('role') == 'tool':
            # Tool response - get tool_call_id directly
            tool_call_id = message.get('tool_call_id')
        elif message.get('role') == 'assistant' and message.get('tool_calls'):
            # Tool call - get the first tool call ID (assuming single tool call per message)
            tool_calls = message.get('tool_calls', [])
            if tool_calls:
                tool_call_id = tool_calls[0].get('id')
        
        # Create metadata
        metadata = MessageMetadata(
            message_type=msg_type,
            importance=base_importance,  # Will be recalculated dynamically
            created_at=time.time(),
            token_count=token_count,
            is_error=is_error,
            error_resolved=False,
            part_of_task=task_id,
            task_completed=task_id in self.completed_tasks if task_id else False,
            tool_call_id=tool_call_id,
            can_summarize=msg_type not in [MessageType.SYSTEM, MessageType.FINAL_ANSWER],
            summary=None
        )
        
        # Add to metadata list
        self.message_metadata.append(metadata)
        
        # Update tool call pairs
        self._update_tool_call_pairs()
        
        # Update resolved errors
        self._update_resolved_errors()
        
        # Synchronize tool call pair importance levels
        self._synchronize_tool_call_pairs()
        
        self.logger.debug(f"Added metadata for message at position {position}: {msg_type.value}, {base_importance.value}, tool_call_id: {tool_call_id}")

    def _update_tool_call_pairs(self) -> None:
        """Update the tool call pairs mapping based on current messages."""
        self._tool_call_pairs.clear()
        
        # Find all tool calls and their responses
        for i, metadata in enumerate(self.message_metadata):
            if metadata.tool_call_id:
                if metadata.message_type in [MessageType.TOOL_CALL, MessageType.FINAL_ANSWER]:
                    # This is a tool call, look for its response
                    for j in range(i + 1, len(self.message_metadata)):
                        response_meta = self.message_metadata[j]
                        if (response_meta.tool_call_id == metadata.tool_call_id and 
                            response_meta.message_type in [MessageType.TOOL_RESPONSE, MessageType.TOOL_ERROR]):
                            self._tool_call_pairs[metadata.tool_call_id] = (i, j)
                            break

    def _recalculate_all_importance_levels(self) -> None:
        """Recalculate importance levels for all messages based on current context."""
        if not self.message_metadata:
            return
        
        # Calculate message pairs for context
        message_pairs = self._calculate_message_pairs()
        total_messages = len(self.message_metadata)
        
        # Recalculate importance for each message
        for i, metadata in enumerate(self.message_metadata):
            # We need the original message to recalculate importance
            # For now, we'll use a simplified approach based on message type and position
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
        """Calculate importance based on position and message type."""
        
        # System messages are always CRITICAL
        if metadata.message_type == MessageType.SYSTEM:
            return MessageImportance.CRITICAL
        
        # Final answers are HIGH
        if metadata.message_type == MessageType.FINAL_ANSWER:
            return MessageImportance.HIGH
        
        # Errors are HIGH until resolved
        if metadata.is_error and not metadata.error_resolved:
            return MessageImportance.HIGH
        
        # Position-based importance
        if total_messages <= 10:
            return MessageImportance.MEDIUM
        
        # Find which pair this message belongs to
        current_pair_index = None
        for pair_idx, (start_idx, end_idx) in enumerate(message_pairs):
            if start_idx <= index <= end_idx:
                current_pair_index = pair_idx
                break
        
        if current_pair_index is not None:
            # First N pairs are CRITICAL
            if current_pair_index < self._num_initial_pairs_critical:
                return MessageImportance.CRITICAL
            
            # Last N pairs are HIGH
            if current_pair_index >= len(message_pairs) - self._num_recent_pairs_for_high_importance:
                return MessageImportance.HIGH
        
        # Default based on message type
        if metadata.message_type in [MessageType.USER_QUERY, MessageType.TOOL_RESPONSE]:
            return MessageImportance.MEDIUM
        
        return MessageImportance.LOW

    def _calculate_message_pairs(self) -> List[Tuple[int, int]]:
        """Calculate logical message pairs for positional importance."""
        pairs = []
        i = 0
        
        while i < len(self.message_metadata):
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
                    if next_meta.message_type in [MessageType.ASSISTANT_RESPONSE, MessageType.TOOL_CALL]:
                        pairs.append((i, i + 1))
                        i += 2
                        continue
                
                # User message without response
                pairs.append((i, i))
                i += 1
                continue
            
            # Tool call with response
            if metadata.tool_call_id and metadata.tool_call_id in self._tool_call_pairs:
                call_idx, response_idx = self._tool_call_pairs[metadata.tool_call_id]
                if i == call_idx:
                    pairs.append((call_idx, response_idx))
                    i = response_idx + 1
                    continue
            
            # Single message
            pairs.append((i, i))
            i += 1
        
        return pairs

    def _update_resolved_errors(self) -> None:
        """Update the set of resolved error tool call IDs."""
        self._resolved_errors.clear()
        
        # Track tool calls that had errors but later succeeded
        error_tool_calls = set()
        success_tool_calls = set()
        
        for metadata in self.message_metadata:
            if metadata.tool_call_id:
                if metadata.is_error:
                    error_tool_calls.add(metadata.tool_call_id)
                elif metadata.message_type in [MessageType.TOOL_RESPONSE]:
                    # Check if this is a successful response (not an error)
                    success_tool_calls.add(metadata.tool_call_id)
        
        # Find tool functions that had both errors and successes
        for tool_call_id in self._tool_call_pairs:
            call_idx, response_idx = self._tool_call_pairs[tool_call_id]
            
            if (call_idx < len(self.message_metadata) and 
                response_idx < len(self.message_metadata)):
                
                call_meta = self.message_metadata[call_idx]
                response_meta = self.message_metadata[response_idx]
                
                # Check if there's a later successful call to the same function
                if response_meta.is_error:
                    function_name = self._extract_function_name(call_meta, call_idx)
                    if function_name and self._has_later_success(function_name, call_idx):
                        self._resolved_errors.add(tool_call_id)
                        response_meta.error_resolved = True

    def _extract_function_name(self, metadata: MessageMetadata, message_index: int) -> Optional[str]:
        """Extract function name from a tool call message."""
        # This would need access to the actual message content
        # For now, return a placeholder - this should be implemented based on message structure
        return f"function_{message_index}"  # Placeholder

    def _has_later_success(self, function_name: str, error_position: int) -> bool:
        """Check if there's a later successful call to the same function."""
        # Look for successful calls to the same function after the error
        for i in range(error_position + 1, len(self.message_metadata)):
            metadata = self.message_metadata[i]
            if (metadata.message_type == MessageType.TOOL_RESPONSE and 
                not metadata.is_error):
                # Check if this is the same function (simplified check)
                return True
        return False

    def _synchronize_tool_call_pairs(self) -> None:
        """Ensure tool call pairs have synchronized importance levels."""
        for tool_call_id, (call_idx, response_idx) in self._tool_call_pairs.items():
            if (call_idx < len(self.message_metadata) and 
                response_idx < len(self.message_metadata)):
                
                call_meta = self.message_metadata[call_idx]
                response_meta = self.message_metadata[response_idx]
                
                # Use the higher importance level for both
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

    def _extract_task_id(self, message: Dict[str, Any]) -> Optional[str]:
        """Extract task identifier from message content."""
        # Simple implementation - could be enhanced with more sophisticated parsing
        content = str(message.get('content', ''))
        
        # Look for task patterns
        if 'task:' in content.lower():
            parts = content.lower().split('task:')
            if len(parts) > 1:
                task_part = parts[1].split()[0] if parts[1].split() else None
                return f"task_{task_part}" if task_part else None
        
        return None
    
    def _is_tool_error_response(self, message: Dict[str, Any]) -> bool:
        """
        Check if a tool response message represents an error.
        
        Args:
            message: The tool response message to check
            
        Returns:
            True if the message represents a tool error
        """
        if message.get('role') != 'tool':
            return False
        
        content = str(message.get('content', '')).strip().lower()
        
        # Check if content starts with "error"
        return content.startswith('error')
    
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
        Optimize message list by removing/summarizing less important messages
        while preserving tool call/response pairs and maintaining conversation integrity.
        """
        # Ensure metadata is up to date
        if len(messages) > len(self.message_metadata):
            for i in range(len(self.message_metadata), len(messages)):
                msg = messages[i]
                token_count = self._count_message_tokens(msg, token_counter)
                self.add_message_metadata(msg, token_count, i, len(messages))
        
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
        
        # Find all tool call/response pairs
        tool_call_pairs = self._tool_call_pairs
        
        # Create sets of message indices that must be kept together
        protected_indices = set()
        pair_groups = {}  # Maps group_id to set of indices
        
        for tool_call_id, (call_idx, response_idx) in tool_call_pairs.items():
            group_id = f"pair_{tool_call_id}"
            pair_groups[group_id] = {call_idx, response_idx}
            protected_indices.update({call_idx, response_idx})
        
        # Always protect system message and recent critical messages
        for i, meta in enumerate(self.message_metadata):
            if meta.importance == MessageImportance.CRITICAL:
                protected_indices.add(i)
        
        # Build optimized message list
        optimized_messages = []
        optimized_metadata = []
        tokens_used = 0
        tokens_saved = 0
        messages_removed = 0
        messages_summarized = 0
        
        # Process messages in order, respecting pairs and importance
        i = 0
        while i < len(messages):
            msg = messages[i]
            meta = self.message_metadata[i]
            msg_tokens = self._count_message_tokens(msg, token_counter)
            
            # Check if this message is part of a protected pair
            current_group = None
            for group_id, indices in pair_groups.items():
                if i in indices:
                    current_group = group_id
                    break
            
            if current_group:
                # Process the entire group
                group_indices = sorted(pair_groups[current_group])
                group_messages = [messages[idx] for idx in group_indices]
                group_metadata = [self.message_metadata[idx] for idx in group_indices]
                group_tokens = sum(self._count_message_tokens(messages[idx], token_counter) for idx in group_indices)
                
                # Check if we should keep this group
                group_importance_values = [self.message_metadata[idx].importance.value for idx in group_indices]
                group_importance = max(group_importance_values, key=lambda x: 
                    {"critical": 4, "high": 3, "medium": 2, "low": 1, "temp": 0}.get(x, 0)
                )
                should_keep_group = (
                    group_importance == MessageImportance.CRITICAL or
                    self.strategy.should_keep_message(msg, meta, context)
                )
                
                if should_keep_group and tokens_used + group_tokens <= self.target_tokens:
                    # Keep the entire group
                    optimized_messages.extend(group_messages)
                    optimized_metadata.extend(group_metadata)
                    tokens_used += group_tokens
                    self.logger.debug(f"Kept tool call pair group: {group_indices}")
                else:
                    # Skip the entire group
                    tokens_saved += group_tokens
                    messages_removed += len(group_indices)
                    self.logger.debug(f"Removed tool call pair group: {group_indices}")
                
                # Skip to after this group
                i = max(group_indices) + 1
                continue
            
            # Single message processing
            if i in protected_indices:
                # Always keep protected messages
                optimized_messages.append(msg)
                optimized_metadata.append(meta)
                tokens_used += msg_tokens
            elif self.strategy.should_keep_message(msg, meta, context) and tokens_used + msg_tokens <= self.target_tokens:
                # Keep this message
                optimized_messages.append(msg)
                optimized_metadata.append(meta)
                tokens_used += msg_tokens
            elif self.enable_summarization and meta.can_summarize and not meta.summary:
                # Try to summarize
                summary = self._summarize_message(msg)
                summary_tokens = token_counter(summary)
                
                if tokens_used + summary_tokens <= self.target_tokens:
                    # Create summarized message
                    summarized_msg = msg.copy()
                    summarized_msg['content'] = summary
                    optimized_messages.append(summarized_msg)
                    
                    # Update metadata
                    meta.summary = summary
                    optimized_metadata.append(meta)
                    
                    tokens_used += summary_tokens
                    tokens_saved += msg_tokens - summary_tokens
                    messages_summarized += 1
                else:
                    # Skip this message
                    tokens_saved += msg_tokens
                    messages_removed += 1
            else:
                # Skip this message
                tokens_saved += msg_tokens
                messages_removed += 1
            
            i += 1
        
        # Update metadata list
        self.message_metadata = optimized_metadata
        
        # Update statistics
        self.stats['messages_removed'] += messages_removed
        self.stats['messages_summarized'] += messages_summarized
        self.stats['tokens_saved'] += tokens_saved
        self.stats['memory_optimizations'] += 1
        
        optimization_info = {
            'action': 'optimized',
            'original_tokens': total_tokens,
            'final_tokens': tokens_used,
            'tokens_saved': tokens_saved,
            'messages_removed': messages_removed,
            'messages_summarized': messages_summarized,
            'memory_pressure_before': memory_pressure,
            'memory_pressure_after': self.calculate_memory_pressure(tokens_used),
            'tool_pairs_preserved': len(tool_call_pairs)
        }
        
        self.logger.info(f"Memory optimization completed: {optimization_info}")
        
        # Final validation: ensure tool call integrity is maintained
        final_pairs = self._tool_call_pairs
        if len(final_pairs) != len([pair for pair in tool_call_pairs.values() if all(idx < len(optimized_messages) for idx in pair)]):
            self.logger.warning("Tool call/response integrity may be compromised")
        
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
                    'tool_call_id': meta.tool_call_id
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
                tool_call_id=meta['tool_call_id']
            )
            for meta in metadata_list
        ]
        
        return manager