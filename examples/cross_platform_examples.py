#!/usr/bin/env python3
"""
Cross-Platform TinyCodeAgent Usage Examples

This file demonstrates how to use TinyCodeAgent with automatic cross-platform 
provider selection and various configuration options.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add tinyagent to path for examples
sys.path.insert(0, str(Path(__file__).parent.parent))

from tinyagent.code_agent.tiny_code_agent import TinyCodeAgent
from tinyagent.hooks.logging_manager import LoggingManager
from tinyagent import tool

# Example custom tool for demonstrations
@tool(name="simple_calculator", description="Perform basic arithmetic operations")
def simple_calculator(operation: str, a: float, b: float) -> float:
    """Simple calculator tool for demonstrations."""
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        return a / b if b != 0 else "Error: Division by zero"
    else:
        return "Error: Unknown operation"


async def example_1_auto_detection():
    """
    Example 1: Basic auto-detection
    
    Let TinyCodeAgent automatically detect and select the best provider
    for your platform.
    """
    print("="*80)
    print("EXAMPLE 1: Auto-Detection")
    print("="*80)
    
    # Create agent with auto-detection (default behavior)
    agent = TinyCodeAgent(
        model="gpt-4",
        api_key="your-api-key-here",
        local_execution=True,  # Use local sandboxing
        # provider=None is the default, enables auto-detection
    )
    
    print(f"Auto-selected provider: {agent.provider}")
    print(f"Available providers on this system: {TinyCodeAgent.get_available_providers()}")
    
    # Test with a simple Python task
    response = await agent.run("""
    Create a simple Python script that:
    1. Calculates the factorial of 5
    2. Generates a list of first 10 fibonacci numbers
    3. Prints both results
    """)
    
    print("Response:", response)
    await agent.close()


async def example_2_explicit_provider_with_fallback():
    """
    Example 2: Explicit provider selection with fallback
    
    Request a specific provider but allow fallback to others if unavailable.
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Explicit Provider with Fallback")
    print("="*80)
    
    try:
        # Try to use bubblewrap (Linux-only), but allow fallback
        agent = TinyCodeAgent(
            model="gpt-4",
            api_key="your-api-key-here",
            provider="bubblewrap",  # Prefer bubblewrap
            local_execution=True,
            provider_fallback=True,  # Allow fallback if bubblewrap unavailable
            tools=[simple_calculator]  # Add our custom tool
        )
        
        print(f"Requested: bubblewrap, Got: {agent.provider}")
        
        # Test with a task that uses both Python and shell
        response = await agent.run("""
        I need to do two things:
        1. Use the simple_calculator tool to calculate 15 * 23
        2. Create a Python script that lists files in the current directory
        3. Run a shell command to check the current date
        """)
        
        print("Response:", response)
        await agent.close()
        
    except RuntimeError as e:
        print(f"Provider selection failed: {e}")


async def example_3_platform_specific_configuration():
    """
    Example 3: Platform-specific provider configuration
    
    Configure providers with platform-specific settings.
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Platform-Specific Configuration")
    print("="*80)
    
    # Detect the best local provider first
    best_local = TinyCodeAgent.get_best_local_provider()
    
    if best_local == "seatbelt":
        # macOS configuration
        provider_config = {
            "additional_read_dirs": ["/tmp", os.path.expanduser("~/Documents")],
            "additional_write_dirs": ["/tmp"],
            "environment_variables": {
                "PROJECT_NAME": "Cross-Platform Demo",
                "PLATFORM": "macOS",
                "SANDBOX_TYPE": "seatbelt"
            }
        }
    elif best_local == "bubblewrap":
        # Linux configuration
        provider_config = {
            "additional_read_dirs": ["/tmp", "/home"],
            "additional_write_dirs": ["/tmp"],
            "environment_variables": {
                "PROJECT_NAME": "Cross-Platform Demo",
                "PLATFORM": "Linux",
                "SANDBOX_TYPE": "bubblewrap"
            }
        }
    else:
        # Fallback configuration
        provider_config = {}
    
    agent = TinyCodeAgent(
        model="gpt-4",
        api_key="your-api-key-here",
        provider=best_local,
        local_execution=True,
        provider_config=provider_config,
        user_variables={"demo_data": [1, 2, 3, 4, 5]}
    )
    
    print(f"Using provider: {agent.provider}")
    
    # Test environment variables and user variables
    response = await agent.run("""
    Check what environment variables and user variables are available:
    1. Print the PROJECT_NAME and PLATFORM environment variables
    2. Print the demo_data user variable
    3. Create a simple analysis of the demo_data
    """)
    
    print("Response:", response)
    await agent.close()


async def example_4_error_handling():
    """
    Example 4: Error handling and provider validation
    
    Demonstrate proper error handling for unsupported configurations.
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Error Handling")
    print("="*80)
    
    test_cases = [
        {
            "name": "Unsupported provider",
            "config": {"provider": "nonexistent", "local_execution": True}
        },
        {
            "name": "Provider without fallback",
            "config": {"provider": "bubblewrap", "local_execution": True, "provider_fallback": False}
        },
        {
            "name": "Valid configuration",
            "config": {"provider": "modal", "local_execution": False}
        }
    ]
    
    for test_case in test_cases:
        print(f"\n--- Testing: {test_case['name']} ---")
        try:
            agent = TinyCodeAgent(
                model="gpt-4",
                api_key="your-api-key-here",
                **test_case['config']
            )
            print(f"✅ Success: Agent created with provider '{agent.provider}'")
            await agent.close()
            
        except Exception as e:
            print(f"❌ Expected error: {e}")


async def example_5_comprehensive_demo():
    """
    Example 5: Comprehensive cross-platform demo
    
    A complete example showing advanced usage with multiple features.
    """
    print("\n" + "="*80)
    print("EXAMPLE 5: Comprehensive Demo")
    print("="*80)
    
    # Set up logging for detailed output
    log_manager = LoggingManager(log_level="INFO")
    
    # Create agent with comprehensive configuration
    agent = TinyCodeAgent(
        model="gpt-4",
        api_key="your-api-key-here",
        log_manager=log_manager,
        
        # Auto-select best provider for local execution
        provider=None,
        local_execution=True,
        auto_provider_selection=True,
        provider_fallback=True,
        
        # Tool configuration
        tools=[simple_calculator],
        code_tools=[],
        
        # User variables
        user_variables={
            "sample_data": [10, 20, 30, 40, 50],
            "config": {"threshold": 25, "multiplier": 2}
        },
        
        # Provider-agnostic configuration
        provider_config={
            "bypass_shell_safety": True,
            "environment_variables": {
                "DEMO_MODE": "true",
                "LOG_LEVEL": "DEBUG"
            }
        },
        
        # Enhanced features
        enable_python_tool=True,
        enable_shell_tool=True,
        enable_file_tools=True,
        
        # Output management
        truncation_config={
            "max_tokens": 2000,
            "max_lines": 100,
            "enabled": True
        }
    )
    
    print(f"Agent configured with provider: {agent.provider}")
    print(f"System capabilities: {agent.system_capabilities}")
    
    # Complex task that exercises multiple features
    response = await agent.run("""
    I need you to perform a comprehensive data analysis task:
    
    1. First, use the simple_calculator tool to compute some basic statistics:
       - Calculate the sum of sample_data (10+20+30+40+50)
       - Calculate the average by dividing the sum by the count
    
    2. Then, create a Python script that:
       - Analyzes the sample_data using the config threshold
       - Identifies values above and below the threshold
       - Applies the multiplier to values above threshold
       - Creates a summary report
    
    3. Use shell commands to:
       - Check the current date and time
       - Show the current working directory
       - List the files in the current directory
    
    4. Finally, create a simple visualization or summary of the results
    
    Make sure to show your work step by step and explain what each part does.
    """)
    
    print("Comprehensive demo response:")
    print(response)
    
    await agent.close()


async def main():
    """Run all examples."""
    print("CROSS-PLATFORM TINYCODAGENT EXAMPLES")
    print("====================================")
    
    # Show system information
    print(f"Platform: {sys.platform}")
    print(f"Available providers: {TinyCodeAgent.get_available_providers()}")
    print(f"Best local provider: {TinyCodeAgent.get_best_local_provider()}")
    
    # Run examples
    await example_1_auto_detection()
    await example_2_explicit_provider_with_fallback()
    await example_3_platform_specific_configuration()
    await example_4_error_handling()
    
    # Comprehensive demo (commented out by default as it's longer)
    # await example_5_comprehensive_demo()
    
    print("\n" + "="*80)
    print("All examples completed!")
    print("="*80)


if __name__ == "__main__":
    # Note: These examples require actual API keys to work fully
    # For testing purposes, you can set dummy keys
    
    # Set a dummy API key for testing (replace with real key for actual use)
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    
    asyncio.run(main())