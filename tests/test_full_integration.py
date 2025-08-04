#!/usr/bin/env python3
"""
Full integration test to verify prompt caching works end-to-end in TinyAgent.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def test_full_integration():
    """Test prompt caching in a real TinyAgent scenario."""
    logger.info("=== Full Integration Test for Anthropic Prompt Cache ===")
    
    try:
        from tinyagent import TinyAgent
        from tinyagent.hooks import anthropic_prompt_cache
        
        # Check if we should run with real API or mock
        has_api_key = os.getenv("ANTHROPIC_API_KEY") is not None
        
        if not has_api_key:
            logger.info("No ANTHROPIC_API_KEY - running mock test")
            
            # Create agent
            agent = TinyAgent(
                model="claude-3-5-sonnet-20241022",
                system_prompt="You are a helpful assistant for testing prompt caching.",
                temperature=0.1
            )
            
            # Add cache callback
            cache_callback = anthropic_prompt_cache()
            agent.add_callback(cache_callback)
            
            # Add a callback to capture the actual messages sent to LLM
            captured_messages = []
            
            class LLMMessageCapture:
                async def __call__(self, event_name: str, agent, **kwargs):
                    if event_name == "llm_start":
                        messages = kwargs.get("messages", [])
                        # Make a deep copy to capture the state
                        import copy
                        captured_messages.clear()
                        captured_messages.extend(copy.deepcopy(messages))
                        
                        logger.info(f"🔍 Captured {len(messages)} messages for LLM call:")
                        for i, msg in enumerate(messages):
                            content = msg.get("content", "")
                            role = msg.get("role", "unknown")
                            
                            if isinstance(content, list) and content:
                                has_cache = any("cache_control" in block for block in content if isinstance(block, dict))
                                if has_cache:
                                    logger.info(f"  Message {i} ({role}): ✅ HAS CACHE CONTROL")
                                    for j, block in enumerate(content):
                                        if isinstance(block, dict) and "cache_control" in block:
                                            logger.info(f"    Block {j}: cache_control = {block['cache_control']}")
                                else:
                                    logger.info(f"  Message {i} ({role}): list content without cache control")
                            elif isinstance(content, str):
                                logger.info(f"  Message {i} ({role}): string content (length: {len(content)})")
                            else:
                                logger.info(f"  Message {i} ({role}): {type(content)} content")
            
            capture_callback = LLMMessageCapture()
            agent.add_callback(capture_callback)
            
            # Mock the LLM call to avoid actual API usage
            original_method = agent._litellm_with_retry
            
            async def mock_llm_call(**kwargs):
                # Just return a mock response structure
                class MockResponse:
                    def __init__(self):
                        self.choices = [MockChoice()]
                
                class MockChoice:
                    def __init__(self):
                        self.message = MockMessage()
                
                class MockMessage:
                    def __init__(self):
                        self.content = "This is a mock response for testing prompt caching integration."
                        self.tool_calls = []
                
                logger.info("🔧 Mock LLM call intercepted - checking messages...")
                messages = kwargs.get("messages", [])
                
                # Verify that we received the modified messages
                found_cache_control = False
                for msg in messages:
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and "cache_control" in block:
                                found_cache_control = True
                                logger.info(f"✅ VERIFIED: Cache control found in LLM call! {block['cache_control']}")
                                break
                
                if not found_cache_control:
                    logger.warning("⚠️  No cache control found in LLM call messages")
                
                return MockResponse()
            
            # Replace the method temporarily
            agent._litellm_with_retry = mock_llm_call
            
            # Test with a long message that should trigger caching
            long_prompt = "Please analyze this detailed content: " + "This is sample text for analysis. " * 200
            
            logger.info(f"📤 Sending long prompt (length: {len(long_prompt)} chars)")
            
            try:
                result = await agent.run(long_prompt, max_turns=1)
                logger.info(f"📥 Received response: {result}")
                
                # Verify that cache control was applied
                if captured_messages:
                    last_message = captured_messages[-1]
                    content = last_message.get("content", "")
                    
                    if isinstance(content, list) and content:
                        for block in content:
                            if isinstance(block, dict) and "cache_control" in block:
                                logger.info("🎉 SUCCESS: Cache control was successfully applied to messages sent to LLM!")
                                return True
                        
                        logger.error("❌ FAILURE: No cache control found in captured messages")
                        return False
                    else:
                        logger.error(f"❌ FAILURE: Expected list content, got {type(content)}")
                        return False
                else:
                    logger.error("❌ FAILURE: No messages were captured")
                    return False
                    
            finally:
                await agent.close()
        
        else:
            logger.info("ANTHROPIC_API_KEY found - running real API test")
            
            # Create agent with real API
            agent = TinyAgent(
                model="claude-3-5-sonnet-20241022",
                system_prompt="You are a helpful assistant. Respond briefly to test prompt caching.",
                temperature=0.1
            )
            
            # Add cache callback
            cache_callback = anthropic_prompt_cache()
            agent.add_callback(cache_callback)
            
            # Add debug callback to see messages
            class DebugCallback:
                async def __call__(self, event_name: str, agent, **kwargs):
                    if event_name == "llm_start":
                        messages = kwargs.get("messages", [])
                        logger.info(f"🔍 Sending {len(messages)} messages to LLM")
                        
                        for i, msg in enumerate(messages):
                            content = msg.get("content", "")
                            if isinstance(content, list):
                                has_cache = any("cache_control" in block for block in content if isinstance(block, dict))
                                logger.info(f"  Message {i}: ✅ Cache control applied" if has_cache else f"  Message {i}: No cache control")
            
            debug_callback = DebugCallback()
            agent.add_callback(debug_callback)
            
            # Test with a long message
            long_prompt = "Please provide a brief response to confirm prompt caching is working. " + "Additional context: " + "This is filler text. " * 100
            
            logger.info(f"📤 Sending request to Claude (content length: {len(long_prompt)} chars)")
            
            try:
                result = await agent.run(long_prompt, max_turns=1)
                logger.info(f"📥 Response received: {result[:100]}..." if len(result) > 100 else f"📥 Response: {result}")
                logger.info("🎉 Real API test completed successfully!")
                return True
                
            except Exception as e:
                logger.error(f"❌ Real API test failed: {e}")
                return False
            finally:
                await agent.close()
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False

async def main():
    success = await test_full_integration()
    if success:
        logger.info("🎉 Full integration test PASSED!")
    else:
        logger.error("❌ Full integration test FAILED!")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)