"""
Message Cleanup Hook for TinyAgent

This hook removes the 'created_at' field from each message before they are sent to the LLM
when the 'llm_start' event is triggered. This is useful for providers that don't
support the 'created_at' field in messages.

IMPORTANT: This hook only modifies the messages sent to the LLM, not the conversation history.
The agent's conversation history (agent.messages) remains unchanged and pristine.

Usage:
    from tinyagent.hooks.message_cleanup import MessageCleanupHook
    
    # Add to agent
    agent.add_callback(MessageCleanupHook())
"""

import logging
from typing import Any, Dict, List, Optional


class MessageCleanupHook:
    """
    A TinyAgent callback hook that removes 'created_at' fields from messages
    before they are sent to the LLM when the 'llm_start' event is triggered.
    
    This is particularly useful for LLM providers that don't support the
    'created_at' field in message objects, such as Groq.
    
    IMPORTANT: This hook follows the TinyAgent hook architecture where:
    - agent.messages (conversation history) remains unchanged
    - Only kwargs["messages"] (LLM call messages) are modified
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the MessageCleanupHook.
        
        Args:
            logger: Optional logger to use for debugging
        """
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug("MessageCleanupHook initialized")
    
    async def __call__(self, event_name: str, agent: Any, *args, **kwargs) -> None:
        """
        Process events from the TinyAgent.
        
        This method handles both the new interface (kwargs_dict as positional arg)
        and the legacy interface (**kwargs) for backward compatibility.
        
        Args:
            event_name: The name of the event
            agent: The TinyAgent instance
            *args: Variable positional arguments (may contain kwargs_dict)
            **kwargs: Variable keyword arguments (legacy interface)
        """
        if event_name == "llm_start":
            # For llm_start events, expect kwargs_dict as the first positional argument
            if args and isinstance(args[0], dict):
                # New interface: kwargs_dict passed as positional argument
                kwargs_dict = args[0]
                await self._handle_llm_start(agent, kwargs_dict)
            else:
                # Legacy interface: should not happen for llm_start, but handle gracefully
                self.logger.warning("llm_start event received with legacy interface, ignoring")
        # Ignore all other events silently
    
    async def _handle_llm_start(self, agent: Any, kwargs_dict: Dict[str, Any]) -> None:
        """
        Handle the llm_start event by cleaning up messages that will be sent to the LLM.
        
        IMPORTANT: This method ONLY modifies kwargs_dict["messages"] (LLM call messages).
        It does NOT modify agent.messages (conversation history) to maintain data integrity.

        Args:
            agent: The TinyAgent instance
            kwargs_dict: Dictionary of event data including 'messages' that can be modified in place
        """
        self.logger.debug("Handling llm_start event - cleaning up LLM messages")
        
        # Only modify messages in kwargs_dict - these are the messages going to LLM
        if "messages" not in kwargs_dict:
            self.logger.debug("No 'messages' in kwargs_dict to clean up")
            return
        
        messages = kwargs_dict["messages"]
        if not messages:
            self.logger.debug("No messages to clean up")
            return
        
        # Clean up each message by removing 'created_at' field
        cleaned_messages = []
        for message in messages:
            if isinstance(message, dict):
                # Create a copy of the message without 'created_at'
                cleaned_message = {k: v for k, v in message.items() if k != 'created_at'}
                cleaned_messages.append(cleaned_message)
                
                # Log if we removed a created_at field
                if 'created_at' in message:
                    self.logger.debug(f"Removed 'created_at' field from message with role: {message.get('role', 'unknown')}")
            else:
                # If message is not a dict, keep it as is
                cleaned_messages.append(message)
        
        # Update ONLY the messages in kwargs_dict (what goes to LLM)
        # DO NOT modify agent.messages (conversation history)
        self.logger.debug(f"About to assign cleaned_messages to kwargs_dict['messages']")
        self.logger.debug(f"cleaned_messages: {cleaned_messages}")
        self.logger.debug(f"kwargs_dict['messages'] before assignment: {kwargs_dict['messages']}")
        kwargs_dict["messages"] = cleaned_messages
        self.logger.debug(f"kwargs_dict['messages'] after assignment: {kwargs_dict['messages']}")
        self.logger.debug(f"Updated LLM messages: {len(cleaned_messages)} messages cleaned")


def create_message_cleanup_hook(logger: Optional[logging.Logger] = None) -> MessageCleanupHook:
    """
    Convenience function to create a MessageCleanupHook instance.
    
    Args:
        logger: Optional logger to use
        
    Returns:
        MessageCleanupHook instance
    """
    return MessageCleanupHook(logger=logger) 