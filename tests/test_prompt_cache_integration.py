#!/usr/bin/env python3
"""
Integration test for Anthropic Prompt Cache with TinyAgent.
This test verifies that the cache control modifications actually reach the LLM.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def test_prompt_cache_integration():
    """Test that prompt caching actually modifies the messages sent to LLM."""
    logger.info("=== Testing Anthropic Prompt Cache Integration ===")
    
    try:
        from tinyagent import TinyAgent
        from tinyagent.hooks import anthropic_prompt_cache
        
        # Check if we have the required API key
        if not os.getenv("ANTHROPIC_API_KEY"):
            logger.warning("ANTHROPIC_API_KEY not set. This test will show the hook behavior without making actual API calls.")
            test_mode = "mock"
        else:
            test_mode = "real"
            logger.info("ANTHROPIC_API_KEY found. Will test with real API calls.")
        
        # Create agent with Claude model
        agent = TinyAgent(
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a helpful assistant.",
            temperature=0.1,
            logger=logger
        )
        
        # Add Anthropic prompt cache callback with debug logging
        debug_logger = logging.getLogger("anthropic_cache_test")
        debug_logger.setLevel(logging.DEBUG)
        
        cache_callback = anthropic_prompt_cache(logger=debug_logger)
        agent.add_callback(cache_callback)
        
        # Add a callback to inspect messages before and after hooks
        class MessageInspectorCallback:
            def __init__(self):
                self.original_messages = None
                self.modified_messages = None
            
            async def __call__(self, event_name: str, agent, **kwargs):
                if event_name == "llm_start":
                    messages = kwargs.get("messages", [])
                    logger.info(f"📋 Messages received by LLM (count: {len(messages)}):")
                    
                    for i, msg in enumerate(messages):
                        content = msg.get("content", "")
                        role = msg.get("role", "unknown")
                        
                        if isinstance(content, str):
                            logger.info(f"  Message {i} ({role}): string content, length={len(content)}")
                        elif isinstance(content, list):
                            logger.info(f"  Message {i} ({role}): list content with {len(content)} blocks")
                            for j, block in enumerate(content):
                                if isinstance(block, dict):
                                    block_type = block.get("type", "unknown")
                                    has_cache = "cache_control" in block
                                    cache_info = f", cache_control={block.get('cache_control')}" if has_cache else ""
                                    logger.info(f"    Block {j}: type={block_type}, has_cache_control={has_cache}{cache_info}")
                        else:
                            logger.info(f"  Message {i} ({role}): {type(content)} content")
        
        inspector = MessageInspectorCallback()
        agent.add_callback(inspector)
        
        if test_mode == "real":
            # Test with a long message that should trigger caching
            long_prompt = "Please analyze this detailed text: " + "This is sample content for analysis. " * 200  # ~4000+ chars
            
            logger.info(f"🚀 Running agent with long prompt (length: {len(long_prompt)} chars)")
            logger.info("This should trigger prompt caching...")
            
            try:
                response = await agent.run(long_prompt)
                logger.info(f"✅ Agent completed successfully")
                logger.info(f"Response length: {len(response)} characters")
                
                # Check if we can see evidence of caching in the response (some models return cache usage info)
                # This is model-dependent and may not always be available
                
            except Exception as e:
                logger.error(f"❌ Agent run failed: {e}")
                return False
                
        else:
            # Mock mode - just test the hook behavior
            logger.info("🔧 Running in mock mode - testing hook behavior only")
            
            # Simulate what happens in the agent loop
            long_content = "Test content for caching. " * 200  # ~4000+ chars
            mock_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": long_content}
            ]
            
            logger.info(f"Original message content type: {type(mock_messages[-1]['content'])}")
            
            # Call the hook directly
            await cache_callback("llm_start", agent, messages=mock_messages)
            
            logger.info(f"After hook - message content type: {type(mock_messages[-1]['content'])}")
            
            # Verify the modification
            last_message = mock_messages[-1]
            content = last_message.get("content")
            
            if isinstance(content, list) and content:
                first_block = content[0]
                if isinstance(first_block, dict) and "cache_control" in first_block:
                    logger.info("✅ Cache control successfully added to message!")
                    logger.info(f"Cache control: {first_block['cache_control']}")
                    return True
                else:
                    logger.error("❌ Cache control not found in first content block")
                    return False
            else:
                logger.error("❌ Content was not converted to structured format")
                return False
        
        await agent.close()
        return True
        
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False

async def test_without_cache():
    """Test the same scenario without the cache callback to compare."""
    logger.info("\n=== Testing WITHOUT Prompt Cache (Control Group) ===")
    
    try:
        from tinyagent import TinyAgent
        
        # Create agent WITHOUT cache callback
        agent = TinyAgent(
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a helpful assistant.",
            temperature=0.1,
            logger=logger
        )
        
        # Add message inspector only (no cache callback)
        class MessageInspectorCallback:
            async def __call__(self, event_name: str, agent, **kwargs):
                if event_name == "llm_start":
                    messages = kwargs.get("messages", [])
                    logger.info(f"📋 Messages received by LLM WITHOUT cache (count: {len(messages)}):")
                    
                    for i, msg in enumerate(messages):
                        content = msg.get("content", "")
                        role = msg.get("role", "unknown")
                        
                        if isinstance(content, str):
                            logger.info(f"  Message {i} ({role}): string content, length={len(content)}")
                        elif isinstance(content, list):
                            logger.info(f"  Message {i} ({role}): list content with {len(content)} blocks")
                            # This should NOT happen without the cache callback
                            logger.warning("⚠️  Unexpected: found list content without cache callback!")
                        else:
                            logger.info(f"  Message {i} ({role}): {type(content)} content")
        
        inspector = MessageInspectorCallback()
        agent.add_callback(inspector)
        
        # Simulate the same test
        long_content = "Test content for caching. " * 200  # ~4000+ chars
        mock_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": long_content}
        ]
        
        # Manually call the callback to simulate what happens in agent loop
        await inspector("llm_start", agent, messages=mock_messages)
        
        # Verify no modification occurred
        last_message = mock_messages[-1]
        content = last_message.get("content")
        
        if isinstance(content, str):
            logger.info("✅ Control test passed: content remained as string (no cache modification)")
            return True
        else:
            logger.warning(f"⚠️  Unexpected: content type changed to {type(content)} without cache callback")
            return False
            
        await agent.close()
        
    except Exception as e:
        logger.error(f"Control test failed: {e}", exc_info=True)
        return False

async def main():
    """Run all integration tests."""
    logger.info("Starting Anthropic Prompt Cache Integration Tests")
    
    # Test with cache
    success1 = await test_prompt_cache_integration()
    
    # Test without cache (control)
    success2 = await test_without_cache()
    
    if success1 and success2:
        logger.info("🎉 All integration tests passed!")
        return True
    else:
        logger.error("❌ Some integration tests failed")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)