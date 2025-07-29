"""
Message Cleanup Hook for TinyAgent

This hook removes the 'created_at' field from each message in the agent's messages
when the 'llm_start' event is triggered. This is useful for providers that don't
support the 'created_at' field in messages.

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
    when the 'llm_start' event is triggered.
    
    This is particularly useful for LLM providers that don't support the
    'created_at' field in message objects, such as Groq.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the MessageCleanupHook.
        
        Args:
            logger: Optional logger to use for debugging
        """
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug("MessageCleanupHook initialized")
    
    async def __call__(self, event_name: str, agent: Any, **kwargs: Any) -> None:
        """
        Process events from the TinyAgent.
        
        Args:
            event_name: The name of the event
            agent: The TinyAgent instance
            **kwargs: Additional event data
        """
        if event_name == "llm_start":
            await self._handle_llm_start(agent, **kwargs)
    
    async def _handle_llm_start(self, agent: Any, **kwargs: Any) -> None:
        """
        Handle the llm_start event by cleaning up messages.
        
        Args:
            agent: The TinyAgent instance
            **kwargs: Additional event data including 'messages'
        """
        self.logger.debug("Handling llm_start event - cleaning up messages")
        
        # Get messages from kwargs or agent
        messages = kwargs.get("messages", getattr(agent, "messages", []))
        
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
        
        # Update the agent's messages
        if hasattr(agent, "messages"):
            agent.messages = cleaned_messages
            self.logger.debug(f"Updated agent messages: {len(cleaned_messages)} messages cleaned")
        
        # Also update the messages in kwargs if they exist
        if "messages" in kwargs:
            kwargs["messages"] = cleaned_messages
            self.logger.debug("Updated messages in kwargs")


def create_message_cleanup_hook(logger: Optional[logging.Logger] = None) -> MessageCleanupHook:
    """
    Convenience function to create a MessageCleanupHook instance.
    
    Args:
        logger: Optional logger to use
        
    Returns:
        MessageCleanupHook instance
    """
    return MessageCleanupHook(logger=logger) 