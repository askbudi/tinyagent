#!/usr/bin/env python3
"""
Test specifically for MessageCleanupHook to debug the created_at issue.
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
    """Test MessageCleanupHook specifically."""
    logger.info("=== Testing MessageCleanupHook ===")
    
    try:
        from tinyagent import TinyAgent
        from tinyagent.hooks.message_cleanup import MessageCleanupHook
        
        # Create agent
        agent = TinyAgent(
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a helpful assistant.",
            temperature=0.1
        )
        
        # Add ONLY cleanup hook with debug logging
        debug_logger = logging.getLogger("cleanup_debug")
        debug_logger.setLevel(logging.DEBUG)
        cleanup_hook = MessageCleanupHook(logger=debug_logger)
        agent.add_callback(cleanup_hook)
        
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
                created_at = msg.get("created_at", "NOT_PRESENT")
                
                logger.info(f"Message {i+1} ({role}): created_at = {created_at}")
                if "created_at" in msg:
                    logger.error(f"❌ Message {i+1} STILL HAS created_at: {msg['created_at']}")
                else:
                    logger.info(f"✅ Message {i+1} has NO created_at (good)")
            
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
        
        # Test: Run agent and check if created_at is removed
        logger.info("=== RUNNING AGENT ===")
        await agent.run("Test message", max_turns=1)
        
        # Verify results
        logger.info("=== VERIFICATION ===")
        
        # Check conversation history (should preserve created_at)
        user_msg_in_history = None
        for msg in agent.messages:
            if msg.get("role") == "user":
                user_msg_in_history = msg
                break
        
        if user_msg_in_history and "created_at" in user_msg_in_history:
            logger.info("✅ SUCCESS: Conversation history preserves created_at field")
        else:
            logger.error("❌ FAILURE: Conversation history missing created_at field")
        
        # Check LLM messages (should NOT have created_at)
        cleanup_working = True
        if captured_messages:
            for i, msg in enumerate(captured_messages):
                if "created_at" in msg:
                    logger.error(f"❌ FAILURE: Message {i+1} sent to LLM still has created_at")
                    cleanup_working = False
                    
        if cleanup_working:
            logger.info("✅ SUCCESS: MessageCleanupHook removed all created_at fields from LLM messages")
        else:
            logger.error("❌ FAILURE: MessageCleanupHook did not remove created_at fields")
        
        return cleanup_working
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)