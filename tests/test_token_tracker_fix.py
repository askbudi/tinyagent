#!/usr/bin/env python3
"""
Test that TokenTracker works with the new hook interface.
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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def main():
    """Test TokenTracker with the new hook interface."""
    logger.info("=== Testing TokenTracker with New Hook Interface ===")
    
    try:
        from tinyagent import TinyAgent
        from tinyagent.hooks.token_tracker import TokenTracker
        
        # Create agent
        agent = TinyAgent(
            model="claude-3-5-sonnet-20241022",
            system_prompt="You are a helpful assistant.",
            temperature=0.1
        )
        
        # Add TokenTracker
        tracker = TokenTracker(name="test_tracker")
        agent.add_callback(tracker)
        
        # Variables to capture what gets sent to LLM
        captured_messages = None
        
        async def capture_llm_call(**kwargs):
            nonlocal captured_messages
            logger.info("=== LLM CALL CAPTURED ===")
            
            # Capture the actual messages passed to LLM
            captured_messages = copy.deepcopy(kwargs.get("messages", []))
            
            logger.info(f"Number of messages: {len(captured_messages)}")
            
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
        
        # Test running the agent - this should not throw any TokenTracker errors
        logger.info("=== RUNNING TEST ===")
        await agent.run("Hello, how are you?", max_turns=1)
        
        logger.info("=== VERIFICATION ===")
        logger.info("✅ SUCCESS: TokenTracker did not throw any errors")
        
        # Print tracker summary
        tracker.print_summary()
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return False
    finally:
        if 'agent' in locals():
            await agent.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    print(f"\nTest {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)