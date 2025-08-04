#!/usr/bin/env python3
"""
Test TinyAgent's real run() method to verify hook modifications work correctly.
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
    """Test TinyAgent's real implementation."""
    logger.info("=== Testing Real TinyAgent Hook Behavior ===")
    
    try:
        from tinyagent import TinyAgent
        from tinyagent.hooks.message_cleanup import MessageCleanupHook
        
        # Create agent
        agent = TinyAgent(
            model="claude-3-5-sonnet-20241022",
            system_prompt="Test system",
            temperature=0.1
        )
        
        # Add cleanup hook with debug logging
        debug_logger = logging.getLogger("cleanup_debug")
        debug_logger.setLevel(logging.DEBUG)
        cleanup_hook = MessageCleanupHook(logger=debug_logger)
        agent.add_callback(cleanup_hook)
        
        # Variables to capture what gets sent to LLM
        captured_messages = None
        
        # Store original method
        original_method = agent._litellm_with_retry
        
        async def capture_llm_call(**kwargs):
            nonlocal captured_messages
            logger.info("=== REAL LLM CALL CAPTURED ===")
            logger.info(f"kwargs keys: {list(kwargs.keys())}")
            
            # Capture the actual messages passed to LLM
            captured_messages = copy.deepcopy(kwargs.get("messages", []))
            
            logger.info(f"Number of messages: {len(captured_messages)}")
            for i, msg in enumerate(captured_messages):
                logger.info(f"Message {i}: {msg}")
            
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
        
        # Run the agent with a real run() call
        logger.info("=== RUNNING AGENT WITH REAL run() METHOD ===")
        result = await agent.run("Test message that should have created_at removed", max_turns=1)
        logger.info(f"Agent run result: {result}")
        
        # Check results
        logger.info("=== VERIFICATION ===")
        
        # Check agent.messages (conversation history should preserve created_at)
        user_msg_in_history = None
        for msg in agent.messages:
            if msg.get("role") == "user":
                user_msg_in_history = msg
                break
        
        logger.info(f"User message in conversation history: {user_msg_in_history}")
        
        if user_msg_in_history and "created_at" in user_msg_in_history:
            logger.info("✅ SUCCESS: Conversation history preserves created_at field")
        else:
            logger.error("❌ FAILURE: Conversation history missing created_at field")
        
        # Check captured LLM messages (should NOT have created_at)
        user_msg_to_llm = None
        if captured_messages:
            for msg in captured_messages:
                if msg.get("role") == "user":
                    user_msg_to_llm = msg
                    break
        
        logger.info(f"User message sent to LLM: {user_msg_to_llm}")
        
        if user_msg_to_llm and "created_at" not in user_msg_to_llm:
            logger.info("✅ SUCCESS: LLM messages had created_at field removed by hook")
        else:
            logger.error("❌ FAILURE: LLM messages still have created_at field")
        
        # Overall result
        history_ok = user_msg_in_history and "created_at" in user_msg_in_history
        llm_ok = user_msg_to_llm and "created_at" not in user_msg_to_llm
        
        if history_ok and llm_ok:
            logger.info("🎉 SUCCESS: Hook architecture is working correctly!")
            return True
        else:
            logger.error("❌ FAILURE: Hook architecture has issues")
            return False
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)