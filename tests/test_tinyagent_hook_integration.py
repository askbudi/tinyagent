#!/usr/bin/env python3
"""
Test to verify that TinyAgent properly uses modified messages from hooks.
This test runs the actual TinyAgent flow and captures what gets sent to the LLM.
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

async def test_tinyagent_hook_integration():
    """Test that TinyAgent properly uses modified messages from hooks."""
    logger.info("=== Testing TinyAgent Hook Integration ===")
    
    try:
        from tinyagent import TinyAgent
        from tinyagent.hooks import anthropic_prompt_cache
        
        # Create agent
        agent = TinyAgent(
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a helpful assistant.",
            temperature=0.1
        )
        
        # Add the prompt cache callback
        cache_callback = anthropic_prompt_cache()
        agent.add_callback(cache_callback)
        
        # Variables to capture the state
        messages_before_hooks = None
        messages_sent_to_llm = None
        hook_was_called = False
        
        # Custom hook to capture the original messages state
        class MessageCaptureHook:
            def __init__(self):
                self.captured_messages = None
                
            async def __call__(self, event_name: str, agent_instance, **kwargs):
                nonlocal messages_before_hooks, hook_was_called
                if event_name == "llm_start":
                    hook_was_called = True
                    # Capture the messages at the start of hook processing
                    messages = kwargs.get("messages", [])
                    messages_before_hooks = [msg.copy() for msg in messages]
                    logger.info(f"🔍 Hook received {len(messages)} messages")
                    
                    # Log the state of messages before any modifications
                    for i, msg in enumerate(messages):
                        content = msg.get("content", "")
                        role = msg.get("role", "unknown")
                        if isinstance(content, str):
                            logger.info(f"  Message {i} ({role}): string content, length={len(content)}")
                        elif isinstance(content, list):
                            logger.info(f"  Message {i} ({role}): list content with {len(content)} blocks")
                        else:
                            logger.info(f"  Message {i} ({role}): {type(content)} content")
        
        # Add our capture hook BEFORE the cache hook so it sees the original state
        capture_hook = MessageCaptureHook()
        # Insert at the beginning of callbacks list so it runs before the cache hook
        agent.callbacks.insert(0, capture_hook)
        
        # Mock the LLM call to capture what actually gets sent
        original_litellm_method = agent._litellm_with_retry
        
        async def mock_litellm_call(**kwargs):
            nonlocal messages_sent_to_llm
            
            # Capture the messages that would be sent to LLM
            messages_sent_to_llm = kwargs.get("messages", [])
            logger.info(f"🚀 LLM call intercepted - received {len(messages_sent_to_llm)} messages")
            
            # Log detailed information about what reached the LLM
            for i, msg in enumerate(messages_sent_to_llm):
                content = msg.get("content", "")
                role = msg.get("role", "unknown")
                
                if isinstance(content, str):
                    logger.info(f"  LLM Message {i} ({role}): string content, length={len(content)}")
                elif isinstance(content, list):
                    logger.info(f"  LLM Message {i} ({role}): list content with {len(content)} blocks")
                    # Check for cache control
                    for j, block in enumerate(content):
                        if isinstance(block, dict):
                            has_cache = "cache_control" in block
                            if has_cache:
                                logger.info(f"    Block {j}: ✅ HAS cache_control = {block['cache_control']}")
                            else:
                                logger.info(f"    Block {j}: type={block.get('type', 'unknown')}, no cache_control")
                else:
                    logger.info(f"  LLM Message {i} ({role}): {type(content)} content")
            
            # Return a mock response
            class MockResponse:
                def __init__(self):
                    self.choices = [MockChoice()]
            
            class MockChoice:
                def __init__(self):
                    self.message = MockMessage()
            
            class MockMessage:
                def __init__(self):
                    self.content = "Mock response for testing hook integration."
                    self.tool_calls = []
            
            return MockResponse()
        
        # Replace the LLM method with our mock
        agent._litellm_with_retry = mock_litellm_call
        
        # Create a long prompt that should trigger caching
        long_prompt = "Please analyze this content: " + "This is test content for prompt caching analysis. " * 100
        
        logger.info(f"📤 Starting TinyAgent run with prompt length: {len(long_prompt)} chars")
        
        try:
            # Run the agent
            result = await agent.run(long_prompt, max_turns=1)
            logger.info(f"📥 Agent completed with result: {result}")
            
            # Now analyze what happened
            logger.info("\n=== ANALYSIS ===")
            
            if not hook_was_called:
                logger.error("❌ FAILURE: Hook was never called!")
                return False
            
            if messages_before_hooks is None:
                logger.error("❌ FAILURE: Failed to capture messages before hooks!")
                return False
                
            if messages_sent_to_llm is None:
                logger.error("❌ FAILURE: Failed to capture messages sent to LLM!")
                return False
            
            logger.info(f"📊 Messages before hooks: {len(messages_before_hooks)}")
            logger.info(f"📊 Messages sent to LLM: {len(messages_sent_to_llm)}")
            
            # Compare the last message (user message) before and after hooks
            if len(messages_before_hooks) >= 2 and len(messages_sent_to_llm) >= 2:
                original_user_msg = messages_before_hooks[-1]
                llm_user_msg = messages_sent_to_llm[-1]
                
                original_content = original_user_msg.get("content", "")
                llm_content = llm_user_msg.get("content", "")
                
                logger.info(f"🔍 Original user message content type: {type(original_content)}")
                logger.info(f"🔍 LLM user message content type: {type(llm_content)}")
                
                # Check if the hook modified the message
                if isinstance(original_content, str) and isinstance(llm_content, list):
                    logger.info("✅ SUCCESS: Message was transformed from string to list by hooks!")
                    
                    # Check if cache control was added
                    if llm_content and isinstance(llm_content[0], dict) and "cache_control" in llm_content[0]:
                        logger.info("✅ SUCCESS: Cache control found in LLM message!")
                        logger.info(f"   Cache control: {llm_content[0]['cache_control']}")
                        return True
                    else:
                        logger.error("❌ FAILURE: Cache control not found in transformed message!")
                        return False
                        
                elif isinstance(original_content, str) and isinstance(llm_content, str):
                    logger.error("❌ FAILURE: Message was not modified by hooks!")
                    logger.error("   This indicates hooks are not properly modifying the messages that reach LLM")
                    return False
                else:
                    logger.warning(f"⚠️  Unexpected: original={type(original_content)}, llm={type(llm_content)}")
                    return False
            else:
                logger.error("❌ FAILURE: Insufficient messages captured!")
                return False
                
        finally:
            await agent.close()
            
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        return False

async def test_tinyagent_without_hooks():
    """Control test: TinyAgent without hooks should send original messages."""
    logger.info("\n=== Testing TinyAgent WITHOUT Hooks (Control) ===")
    
    try:
        from tinyagent import TinyAgent
        
        # Create agent WITHOUT any hooks
        agent = TinyAgent(
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a helpful assistant.",
            temperature=0.1
        )
        
        # Variables to capture state
        messages_sent_to_llm = None
        
        # Mock the LLM call
        async def mock_litellm_call(**kwargs):
            nonlocal messages_sent_to_llm
            messages_sent_to_llm = kwargs.get("messages", [])
            logger.info(f"🚀 Control LLM call - received {len(messages_sent_to_llm)} messages")
            
            for i, msg in enumerate(messages_sent_to_llm):
                content = msg.get("content", "")
                role = msg.get("role", "unknown")
                logger.info(f"  Message {i} ({role}): {type(content)} content")
            
            # Return mock response
            class MockResponse:
                def __init__(self):
                    self.choices = [MockChoice()]
            
            class MockChoice:
                def __init__(self):
                    self.message = MockMessage()
            
            class MockMessage:
                def __init__(self):
                    self.content = "Mock response for control test."
                    self.tool_calls = []
            
            return MockResponse()
        
        agent._litellm_with_retry = mock_litellm_call
        
        # Same long prompt
        long_prompt = "Please analyze this content: " + "This is test content for prompt caching analysis. " * 100
        
        logger.info(f"📤 Control test with prompt length: {len(long_prompt)} chars")
        
        try:
            result = await agent.run(long_prompt, max_turns=1)
            logger.info(f"📥 Control test completed: {result}")
            
            # Verify that messages remained unchanged
            if messages_sent_to_llm and len(messages_sent_to_llm) >= 2:
                user_msg = messages_sent_to_llm[-1]
                content = user_msg.get("content", "")
                
                if isinstance(content, str):
                    logger.info("✅ CONTROL SUCCESS: Message remained as string (no hook modifications)")
                    return True
                else:
                    logger.error(f"❌ CONTROL FAILURE: Message unexpectedly modified to {type(content)}")
                    return False
            else:
                logger.error("❌ CONTROL FAILURE: Failed to capture messages")
                return False
                
        finally:
            await agent.close()
            
    except Exception as e:
        logger.error(f"Control test failed: {e}", exc_info=True)
        return False

async def main():
    """Run both integration tests."""
    logger.info("Starting TinyAgent Hook Integration Tests\n")
    
    # Test with hooks
    success1 = await test_tinyagent_hook_integration()
    
    # Test without hooks (control)
    success2 = await test_tinyagent_without_hooks()
    
    logger.info("\n=== FINAL RESULTS ===")
    
    if success1 and success2:
        logger.info("🎉 ALL TESTS PASSED!")
        logger.info("✅ TinyAgent properly uses modified messages from hooks")
        logger.info("✅ Control test confirms hooks are responsible for modifications")
        return True
    else:
        logger.error("❌ SOME TESTS FAILED!")
        if not success1:
            logger.error("❌ Hook integration test failed")
        if not success2:
            logger.error("❌ Control test failed")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)