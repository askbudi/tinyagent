#!/usr/bin/env python3
"""
Test the updated Anthropic prompt caching that adds cache control to all substantial messages.
"""

import asyncio
import logging
import sys
import copy
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def main():
    """Test the updated multi-message caching behavior."""
    logger.info("=== Testing Multi-Message Anthropic Prompt Caching ===")
    
    try:
        from tinyagent import TinyAgent
        from tinyagent.hooks import anthropic_prompt_cache
        
        # Create agent
        agent = TinyAgent(
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a helpful assistant.",
            temperature=0.1
        )
        
        # Add cache hook with debug logging
        debug_logger = logging.getLogger("cache_debug")
        debug_logger.setLevel(logging.DEBUG)
        cache_hook = anthropic_prompt_cache(logger=debug_logger)
        agent.add_callback(cache_hook)
        
        # Variables to capture what gets sent to LLM
        captured_messages = None
        
        async def capture_llm_call(**kwargs):
            nonlocal captured_messages
            logger.info("=== LLM CALL CAPTURED ===")
            
            # Capture the actual messages passed to LLM
            captured_messages = copy.deepcopy(kwargs.get("messages", []))
            
            logger.info(f"Number of messages: {len(captured_messages)}")
            for i, msg in enumerate(captured_messages):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                content_type = type(content)
                
                if isinstance(content, str):
                    logger.info(f"Message {i+1} ({role}): {content_type} with {len(content)} chars")
                elif isinstance(content, list):
                    logger.info(f"Message {i+1} ({role}): {content_type} with {len(content)} blocks")
                    for j, block in enumerate(content):
                        if isinstance(block, dict) and "cache_control" in block:
                            logger.info(f"  Block {j+1}: HAS CACHE CONTROL - {block.get('cache_control')}")
                        else:
                            logger.info(f"  Block {j+1}: no cache control")
                else:
                    logger.info(f"Message {i+1} ({role}): {content_type}")
            
            class MockResponse:
                def __init__(self):
                    self.choices = [MockChoice()]
                    self.usage = MockUsage()
            
            class MockChoice:
                def __init__(self):
                    self.message = MockMessage()
            
            class MockMessage:
                def __init__(self):
                    self.content = "Mock response"
                    self.tool_calls = []
            
            class MockUsage:
                def __init__(self):
                    self.prompt_tokens = 10
                    self.completion_tokens = 5
                    self.total_tokens = 15
            
            return MockResponse()
        
        # Replace the LLM method with our capture function
        agent._litellm_with_retry = capture_llm_call
        
        # Test 1: Short system prompt + short user message (no caching expected)
        logger.info("=== TEST 1: Short messages ===")
        await agent.run("Hello, how are you?", max_turns=1)
        
        # Test 2: Add a long user message (should get cache control)
        logger.info("=== TEST 2: Long user message ===")
        long_message = "Please analyze this very long text: " + "This is sample content for analysis. " * 150  # >4000 chars
        await agent.run(long_message, max_turns=1)
        
        # Test 3: Multiple long messages in conversation
        logger.info("=== TEST 3: Multiple long messages ===")
        another_long_message = "Please continue with this additional analysis: " + "More sample content. " * 200  # >4000 chars
        await agent.run(another_long_message, max_turns=1)
        
        logger.info("=== TEST COMPLETE ===")
        logger.info("Check the logs above to verify cache control was added to messages >4000 characters")
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)