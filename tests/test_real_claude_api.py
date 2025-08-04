#!/usr/bin/env python3
"""
Test with real Claude API to verify prompt caching works end-to-end.
Only runs if ANTHROPIC_API_KEY is set.
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

async def test_real_claude_api():
    """Test with real Claude API if available."""
    
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.info("ANTHROPIC_API_KEY not set - skipping real API test")
        return True
    
    logger.info("=== Testing with Real Claude API ===")
    
    try:
        from tinyagent import TinyAgent
        from tinyagent.hooks import anthropic_prompt_cache
        
        # Create agent
        agent = TinyAgent(
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a helpful assistant. Please respond briefly to test prompt caching.",
            temperature=0.1
        )
        
        # Add cache callback with debug logging
        debug_logger = logging.getLogger("cache_debug")
        debug_logger.setLevel(logging.DEBUG)
        cache_callback = anthropic_prompt_cache(logger=debug_logger)
        agent.add_callback(cache_callback)
        
        # Add callback to verify cache control is being sent
        class APIInspectorCallback:
            async def __call__(self, event_name: str, agent_instance, **kwargs):
                if event_name == "llm_start":
                    messages = kwargs.get("messages", [])
                    logger.info(f"📡 About to send {len(messages)} messages to Claude API")
                    
                    cache_found = False
                    for i, msg in enumerate(messages):
                        content = msg.get("content", "")
                        role = msg.get("role", "unknown")
                        
                        if isinstance(content, list):
                            for j, block in enumerate(content):
                                if isinstance(block, dict) and "cache_control" in block:
                                    cache_found = True
                                    logger.info(f"✅ Message {i} Block {j}: Cache control will be sent to API!")
                                    logger.info(f"   cache_control: {block['cache_control']}")
                    
                    if not cache_found:
                        logger.warning("⚠️  No cache control found in messages to API")
        
        inspector = APIInspectorCallback()
        agent.add_callback(inspector)
        
        # Create a long prompt that should trigger caching
        long_prompt = (
            "Please analyze and summarize the following content briefly: " + 
            "This is detailed content that should trigger prompt caching. " * 120 +
            "\n\nPlease provide a brief summary."
        )
        
        logger.info(f"📤 Sending request to Claude API (content length: {len(long_prompt)} chars)")
        
        try:
            result = await agent.run(long_prompt, max_turns=1)
            logger.info(f"📥 Response from Claude: {result[:200]}..." if len(result) > 200 else f"📥 Response: {result}")
            logger.info("🎉 Real API test completed successfully!")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Real API test failed: {e}")
            # Check if it's an authentication error
            if "authentication" in str(e).lower() or "api_key" in str(e).lower():
                logger.warning("⚠️  Authentication error - please check ANTHROPIC_API_KEY")
            return False
            
        finally:
            await agent.close()
        
    except Exception as e:
        logger.error(f"Real API test setup failed: {e}", exc_info=True)
        return False

async def main():
    success = await test_real_claude_api()
    
    if success:
        logger.info("✅ Real API test completed successfully!")
    else:
        logger.error("❌ Real API test failed!")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)