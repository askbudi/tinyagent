"""
Anthropic Prompt Cache Callback for TinyAgent

A callback that adds cache control to the last 4 messages with substantial content (>4000 characters)
before they're sent to the LLM for Anthropic Claude models that support prompt caching.

IMPORTANT: This hook only modifies the messages sent to the LLM, not the conversation history.
The agent's conversation history (agent.messages) remains unchanged and pristine.
"""

import logging
from typing import Dict, List, Optional, Any


class AnthropicPromptCacheCallback:
    """
    Callback that adds cache control to the last 4 substantial messages for Anthropic Claude models.
    
    This callback checks if the model supports prompt caching (Claude 3.5+, Claude 3.7+, Claude 4+),
    then adds cache_control to the last 4 messages with >4000 characters before sending to the LLM.
    
    IMPORTANT: This hook follows the TinyAgent hook architecture where:
    - agent.messages (conversation history) remains unchanged
    - Only kwargs["messages"] (LLM call messages) are modified
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # Ensure debug logging is enabled
        
        # Model patterns that support prompt caching
        self.supported_model_patterns = [
            "claude-4-sonnet",
            "claude-4-haiku",
            "claude-4-opus",
            "claude-opus-4",
            "claude-sonnet-4", 
            "claude-3-7-sonnet",
            "claude-3-5-sonnet",
            "claude-3-5-haiku"
        ]
        self.logger.debug(f"AnthropicPromptCacheCallback initialized with patterns: {self.supported_model_patterns}")
    
    async def __call__(self, event_name: str, agent, *args, **kwargs):
        """
        Main callback entry point.
        
        This method handles both the new interface (kwargs_dict as positional arg)
        and the legacy interface (**kwargs) for backward compatibility.
        """
        self.logger.debug(f"Callback invoked with event: {event_name}")
        if event_name == "llm_start":
            self.logger.debug("Event is llm_start, proceeding with cache control logic")
            # For llm_start events, expect kwargs_dict as the first positional argument
            if args and isinstance(args[0], dict):
                # New interface: kwargs_dict passed as positional argument
                kwargs_dict = args[0]
                await self._add_cache_control(agent, kwargs_dict)
            else:
                # Legacy interface: should not happen for llm_start, but handle gracefully
                self.logger.warning("llm_start event received with legacy interface, ignoring")
        else:
            self.logger.debug(f"Ignoring event: {event_name}")
    
    async def _add_cache_control(self, agent, kwargs_dict: Dict[str, Any]):
        """Add cache control to all messages that meet the criteria."""
        try:
            # Check if this is an Anthropic model that supports caching
            model = getattr(agent, 'model', '')
            self.logger.debug(f"Agent model: '{model}'")
            
            if not self._is_supported_model(model):
                self.logger.debug(f"Model '{model}' does not support prompt caching - skipping")
                return
            
            self.logger.debug(f"Model '{model}' supports prompt caching")
            
            messages = kwargs_dict.get("messages", [])
            self.logger.debug(f"Found {len(messages)} messages in kwargs_dict")
            
            if not messages:
                self.logger.debug("No messages found - skipping cache control")
                return
            
            # Find messages that qualify for cache control (Anthropic limit: max 4 messages)
            qualifying_messages = []
            for i, message in enumerate(messages):
                self.logger.debug(f"Checking message {i+1}/{len(messages)}: role={message.get('role', 'unknown')}")
                self.logger.debug(f"Message {i+1} content type: {type(message.get('content', 'N/A'))}")
                
                if self._should_add_cache_control(message):
                    self.logger.debug(f"Message {i+1} qualifies for cache control")
                    qualifying_messages.append((i, message))
                else:
                    self.logger.debug(f"Message {i+1} does not meet criteria for cache control - skipping")
            
            # Apply cache control to only the last 4 qualifying messages (Anthropic limit)
            max_cache_messages = 4
            messages_to_cache = qualifying_messages[-max_cache_messages:] if len(qualifying_messages) > max_cache_messages else qualifying_messages
            
            cache_added_count = 0
            for i, message in messages_to_cache:
                self.logger.debug(f"Adding cache control to message {i+1}")
                original_content = message.get("content")
                self._add_cache_to_message(message)
                new_content = message.get("content")
                self.logger.debug(f"Cache control added to message {i+1} - content changed from {type(original_content)} to {type(new_content)}")
                cache_added_count += 1
            
            if len(qualifying_messages) > max_cache_messages:
                self.logger.info(f"Found {len(qualifying_messages)} qualifying messages, but only cached the last {max_cache_messages} due to Anthropic limit")
            
            if cache_added_count > 0:
                self.logger.info(f"✓ Added cache control to {cache_added_count} message(s) for model {model}")
            else:
                self.logger.debug("No messages met criteria for cache control")
                
        except Exception as e:
            self.logger.error(f"Error in AnthropicPromptCacheCallback: {e}", exc_info=True)
    
    def _is_supported_model(self, model: str) -> bool:
        """Check if the model supports prompt caching."""
        model_lower = model.lower()
        self.logger.debug(f"Checking model '{model}' (lowercase: '{model_lower}') against patterns: {self.supported_model_patterns}")
        
        for pattern in self.supported_model_patterns:
            if pattern in model_lower:
                self.logger.debug(f"✓ Model '{model}' matches pattern '{pattern}'")
                return True
        
        self.logger.debug(f"✗ Model '{model}' does not match any supported patterns")
        return False
    
    def _should_add_cache_control(self, message: Dict[str, Any]) -> bool:
        """Check if we should add cache control to this message."""
        content = message.get("content", "")
        self.logger.debug(f"Checking if message should have cache control - content type: {type(content)}")
        # Only add cache control if content is substantial (rough token estimate)
        if isinstance(content, str):
            content_length = len(content)
            should_cache = content_length > 4000  # ~1000 tokens minimum
            self.logger.debug(f"String content length: {content_length}, should cache: {should_cache}")
            return should_cache
        elif isinstance(content, list):
            total_length = 0
            self.logger.debug(f"List content with {len(content)} blocks")
            for i, block in enumerate(content):
                if isinstance(block, dict):
                    # Check for text in various possible keys
                    text_content = block.get("text", "") or block.get("content", "") or str(block)
                    block_length = len(str(text_content))
                    total_length += block_length
                    self.logger.debug(f"Block {i}: dict with text length {block_length}")
                else:
                    block_length = len(str(block))
                    total_length += block_length
                    self.logger.debug(f"Block {i}: {type(block)} with length {block_length}")
            
            should_cache = total_length > 4000
            self.logger.debug(f"Total content length: {total_length}, should cache: {should_cache}")
            return should_cache
        
        self.logger.debug(f"Unknown content type {type(content)}, not caching")
        return False
    
    def _add_cache_to_message(self, message: Dict[str, Any]) -> None:
        """Add cache control to a message."""
        content = message.get("content")
        self.logger.debug(f"Adding cache control to message with content type: {type(content)}")
        
        if isinstance(content, str):
            self.logger.debug(f"Converting string content (length: {len(content)}) to structured format")
            # Convert string content to structured format for cache control
            new_content = [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
            message["content"] = new_content
            self.logger.debug(f"✓ Converted string to structured content with cache control")
        elif isinstance(content, list) and content:
            self.logger.debug(f"Adding cache control to last block of {len(content)} content blocks")
            # Add cache control to the last content block
            last_block = content[-1]
            if isinstance(last_block, dict):
                last_block["cache_control"] = {"type": "ephemeral"}
                self.logger.debug(f"✓ Added cache control to last block (type: {last_block.get('type', 'unknown')})")
            else:
                self.logger.debug(f"✗ Last block is not a dict (type: {type(last_block)}), cannot add cache control")
        else:
            self.logger.debug(f"✗ Cannot add cache control to content type: {type(content)}")


def anthropic_prompt_cache(logger: Optional[logging.Logger] = None) -> AnthropicPromptCacheCallback:
    """
    Create an Anthropic prompt cache callback for TinyAgent.
    
    Usage:
        cache_callback = anthropic_prompt_cache()
        agent.add_callback(cache_callback)
    
    Args:
        logger: Optional logger instance
        
    Returns:
        AnthropicPromptCacheCallback instance
    """
    return AnthropicPromptCacheCallback(logger)


async def run_example():
    """Example usage of the Anthropic prompt cache callback."""
    import os
    from tinyagent import TinyAgent
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set. Please set it to run this example.")
        return
    
    # Create agent with Anthropic model
    agent = TinyAgent(
        model="claude-3-5-sonnet-20241022",
        system_prompt="You are a helpful assistant.",
        temperature=0.1
    )
    
    # Add Anthropic prompt cache callback
    cache_callback = anthropic_prompt_cache()
    agent.add_callback(cache_callback)
    
    try:
        # Test with a long message that should trigger caching
        long_prompt = "Please analyze this text: " + "This is sample text. " * 200
        response = await agent.run(long_prompt)
        
        print(f"Response length: {len(response)} characters")
        print("Cache control should have been added to qualifying messages (max 4).")
        
        # Test with multiple long messages in a conversation
        response2 = await agent.run("Please continue the analysis: " + "Additional text. " * 200)
        print("Multiple long messages - cache control added to last 4 qualifying messages.")
        
        # Test with a short message that shouldn't trigger caching
        short_response = await agent.run("Hello!")
        print("Short message - no cache control added.")
        
    finally:
        await agent.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_example())