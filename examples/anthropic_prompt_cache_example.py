"""
Anthropic Prompt Cache Example for TinyAgent

This example demonstrates the Anthropic prompt caching feature that automatically
adds cache control to large messages for Claude models.
"""

import asyncio
import logging
import os

from tinyagent import TinyAgent
from tinyagent.hooks import anthropic_prompt_cache

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_example():
    """Basic example showing Anthropic prompt cache callback."""
    logger.info("=== Anthropic Prompt Cache Example ===")
    
    # Create agent with Claude model
    agent = TinyAgent(
        model="claude-3-5-sonnet-20241022",
        system_prompt="You are a helpful assistant.",
        temperature=0.1
    )
    
    # Add Anthropic prompt cache callback - that's it!
    cache_callback = anthropic_prompt_cache()
    agent.add_callback(cache_callback)
    
    try:
        # Test with a short message (won't trigger caching)
        logger.info("--- Short Message Test ---")
        short_response = await agent.run("Hello! How are you?")
        logger.info(f"Short response: {short_response[:100]}...")
        
        # Test with a long message (will trigger caching)
        logger.info("--- Long Message Test ---")
        long_prompt = "Please analyze the following text in detail: " + "This is sample content for analysis. " * 100
        long_response = await agent.run(long_prompt)
        logger.info(f"Long response: {long_response[:100]}...")
        logger.info("Cache control should have been added to the long message.")
        
        # Test with follow-up (might benefit from caching)
        follow_up = await agent.run("Can you summarize your previous analysis?")
        logger.info(f"Follow-up response: {follow_up[:100]}...")
        
    finally:
        await agent.close()


async def code_analysis_example():
    """Example with code analysis that benefits from caching."""
    logger.info("=== Code Analysis Example ===")
    
    agent = TinyAgent(
        model="claude-3-5-sonnet-20241022",
        system_prompt="You are a code analysis expert.",
        temperature=0.1
    )
    
    # Add Anthropic prompt cache callback
    cache_callback = anthropic_prompt_cache()
    agent.add_callback(cache_callback)
    
    try:
        # Simulate analyzing a large codebase
        large_code = '''
def process_data(data):
    """Process incoming data."""
    results = []
    for item in data:
        if validate_item(item):
            processed = transform_item(item)
            results.append(processed)
    return results

def validate_item(item):
    """Validate a single item."""
    return item is not None and len(item) > 0

def transform_item(item):
    """Transform a single item."""
    return item.upper().strip()
        ''' * 50  # Make it large enough to trigger caching
        
        prompt = f"Please analyze this Python code and suggest improvements:\n\n{large_code}"
        
        response = await agent.run(prompt)
        logger.info(f"Code analysis response: {len(response)} characters")
        logger.info("Large code analysis should have triggered caching.")
        
        # Follow-up question that might benefit from cache
        follow_up = await agent.run("What are the main security concerns with this code?")
        logger.info(f"Follow-up: {follow_up[:100]}...")
        
    finally:
        await agent.close()


async def claude_4_example():
    """Example showing Claude 4 model support."""
    logger.info("=== Claude 4 Model Example ===")
    
    # Example with Claude 4 model
    agent = TinyAgent(
        model="claude-sonnet-4-20250514",  # Actual Claude 4 model
        system_prompt="You are a helpful assistant.",
        temperature=0.1
    )
    
    # Add cache callback (will work with Claude 4 models)
    cache_callback = anthropic_prompt_cache()
    agent.add_callback(cache_callback)
    
    try:
        long_prompt = "Explain machine learning in detail: " + "Please be thorough. " * 100
        response = await agent.run(long_prompt)
        logger.info(f"Claude 4 response: {response[:100]}...")
        logger.info("Cache control should be added for Claude 4 models.")
        
    except Exception as e:
        logger.info(f"Claude 4 example failed (model may not be available yet): {e}")
    finally:
        await agent.close()


async def main():
    """Run all examples."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("ANTHROPIC_API_KEY not set. Set it to see caching in action.")
        logger.info("Example: export ANTHROPIC_API_KEY='your-key-here'")
        return
    
    try:
        await basic_example()
        await asyncio.sleep(1)
        
        await code_analysis_example()
        await asyncio.sleep(1)
        
        await claude_4_example()
        
    except Exception as e:
        logger.error(f"Error in examples: {e}")
    
    logger.info("Anthropic Prompt Cache Examples Complete")


if __name__ == "__main__":
    asyncio.run(main())