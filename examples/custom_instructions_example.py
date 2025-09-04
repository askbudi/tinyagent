#!/usr/bin/env python3
"""
Example demonstrating the comprehensive custom instruction system for TinyAgent.

This example shows how to use custom instructions in various ways:
1. String-based custom instructions
2. File-based custom instructions  
3. Auto-detection of AGENTS.md files
4. Custom instruction configuration
5. Integration with both TinyAgent and TinyCodeAgent
"""

import asyncio
import os
import tempfile
import shutil
from pathlib import Path


async def demo_string_based_instructions():
    """Demonstrate custom instructions from string."""
    print("=== Demo 1: String-based Custom Instructions ===")
    
    from tinyagent import TinyAgent
    
    # Custom instructions as a string
    custom_instructions = """
You are a helpful AI assistant with the following special behaviors:
1. Always be enthusiastic and positive
2. Use emojis appropriately in your responses  
3. Provide detailed explanations for technical topics
4. End responses with a motivational note
"""
    
    # Create agent with custom instructions
    agent = TinyAgent(
        model="gpt-5-mini",
        custom_instructions=custom_instructions,
        system_prompt="You are a helpful assistant. <user_specified_instruction></user_specified_instruction> Help users with their questions.",
        temperature=0.7
    )
    
    # Check that custom instructions were applied
    system_content = agent.messages[0]["content"]
    print("System prompt contains custom instructions:")
    print("- 'enthusiastic and positive' found:", "enthusiastic and positive" in system_content)
    print("- 'Use emojis appropriately' found:", "Use emojis appropriately" in system_content)
    print("- 'motivational note' found:", "motivational note" in system_content)
    print()


async def demo_file_based_instructions():
    """Demonstrate custom instructions from file."""
    print("=== Demo 2: File-based Custom Instructions ===")
    
    # Create temporary instruction file
    temp_dir = Path(tempfile.mkdtemp())
    instruction_file = temp_dir / "my_instructions.md"
    
    with open(instruction_file, 'w') as f:
        f.write("""# Custom Agent Instructions

You are a specialized coding assistant with these capabilities:

## Core Behavior
- Focus on Python development best practices
- Always provide type hints in code examples
- Explain complex concepts with simple analogies
- Suggest performance optimizations when relevant

## Code Style
- Follow PEP 8 standards
- Use descriptive variable names
- Add comprehensive docstrings
- Include error handling

## Response Format
- Start with a brief summary
- Provide step-by-step explanations
- Include practical examples
- End with next steps or recommendations
""")
    
    try:
        from tinyagent.code_agent import TinyCodeAgent
        
        # Create code agent with file-based instructions
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            custom_instructions=str(instruction_file),
            local_execution=True
        )
        
        # Check system prompt
        system_content = agent.messages[0]["content"]
        print("System prompt contains file-based instructions:")
        print("- 'Python development best practices' found:", "Python development best practices" in system_content)
        print("- 'type hints' found:", "type hints" in system_content)
        print("- 'PEP 8 standards' found:", "PEP 8 standards" in system_content)
        print()
        
        await agent.close()
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)


async def demo_auto_detection():
    """Demonstrate auto-detection of AGENTS.md files."""
    print("=== Demo 3: Auto-detection of AGENTS.md ===")
    
    # Create temporary directory with AGENTS.md
    temp_dir = Path(tempfile.mkdtemp())
    agents_file = temp_dir / "AGENTS.md"
    
    with open(agents_file, 'w') as f:
        f.write("""# Project-Specific Agent Instructions

This agent is working on a data analysis project.

## Domain Focus
- Statistical analysis and visualization
- Data cleaning and preprocessing
- Machine learning model evaluation
- Report generation and insights

## Communication Style
- Be concise but thorough
- Use data-driven language
- Provide statistical context
- Suggest visualization approaches

## Tools and Libraries
- Prefer pandas for data manipulation
- Use matplotlib/seaborn for visualization
- Recommend scikit-learn for ML tasks
- Consider performance implications
""")
    
    # Change to temp directory so auto-detection works
    original_cwd = os.getcwd()
    try:
        os.chdir(temp_dir)
        
        from tinyagent import TinyAgent
        
        # Create agent with auto-detection enabled (default)
        agent = TinyAgent(
            model="gpt-5-mini",
            enable_custom_instructions=True,  # This is the default
            system_prompt="You are an AI assistant. <user_specified_instruction></user_specified_instruction>",
            temperature=0.5
        )
        
        # Check that auto-detected instructions were applied
        system_content = agent.messages[0]["content"]
        print("Auto-detected AGENTS.md instructions:")
        print("- 'data analysis project' found:", "data analysis project" in system_content)
        print("- 'Statistical analysis' found:", "Statistical analysis" in system_content)
        print("- 'pandas for data manipulation' found:", "pandas for data manipulation" in system_content)
        print()
        
        await agent.close()
        
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir)


async def demo_custom_configuration():
    """Demonstrate custom instruction configuration options."""
    print("=== Demo 4: Custom Configuration Options ===")
    
    # Create temporary directory with custom filename
    temp_dir = Path(tempfile.mkdtemp())
    custom_file = temp_dir / "TEAM_INSTRUCTIONS.txt"
    
    with open(custom_file, 'w') as f:
        f.write("""Team-specific instructions for AI assistant:

1. This is a startup environment - be agile and flexible
2. Focus on MVP (Minimum Viable Product) approaches
3. Consider scalability but prioritize speed to market
4. Use modern tech stack and best practices
5. Be collaborative and suggest alternatives
6. Think in terms of user experience and business value
""")
    
    try:
        from tinyagent import TinyAgent
        
        # Create agent with custom configuration
        agent = TinyAgent(
            model="gpt-5-mini",
            enable_custom_instructions=True,
            custom_instruction_config={
                "auto_detect_agents_md": True,
                "custom_filename": "TEAM_INSTRUCTIONS.txt",  # Custom filename
                "execution_directory": str(temp_dir),  # Custom directory
                "inherit_to_subagents": True  # Enable inheritance
            },
            system_prompt="Base prompt. <user_specified_instruction></user_specified_instruction>",
            temperature=0.3
        )
        
        # Check configuration
        config = agent.custom_instruction_loader.get_config()
        print("Custom instruction configuration:")
        print(f"- Custom filename: {config['custom_filename']}")
        print(f"- Execution directory: {config['execution_directory']}")
        print(f"- Auto-detect enabled: {config['auto_detect_agents_md']}")
        print(f"- Has instructions: {config['has_instructions']}")
        print()
        
        # Check system prompt
        system_content = agent.messages[0]["content"]
        print("Custom filename instructions applied:")
        print("- 'startup environment' found:", "startup environment" in system_content)
        print("- 'MVP' found:", "MVP" in system_content)
        print("- 'scalability' found:", "scalability" in system_content)
        print()
        
        await agent.close()
        
    finally:
        shutil.rmtree(temp_dir)


async def demo_disabled_instructions():
    """Demonstrate disabling custom instructions."""
    print("=== Demo 5: Disabled Custom Instructions ===")
    
    from tinyagent import TinyAgent
    
    # Create agent with custom instructions disabled
    agent = TinyAgent(
        model="gpt-5-mini",
        custom_instructions="This should be ignored when disabled",
        enable_custom_instructions=False,  # Explicitly disable
        system_prompt="Original system prompt with <user_specified_instruction></user_specified_instruction> placeholder.",
        temperature=0.0
    )
    
    # Check that custom instructions were NOT applied
    system_content = agent.messages[0]["content"]
    print("Custom instructions disabled:")
    print("- Original placeholder removed:", "<user_specified_instruction>" not in system_content)
    print("- Custom instructions not applied:", "This should be ignored" not in system_content)
    print("- System prompt content:", repr(system_content))
    print()
    
    await agent.close()


async def demo_placeholder_support():
    """Demonstrate placeholder support in system prompts."""
    print("=== Demo 6: Placeholder Support ===")
    
    from tinyagent import TinyAgent
    
    # Test default placeholder
    agent1 = TinyAgent(
        model="gpt-5-mini",
        custom_instructions="Default placeholder instructions here.",
        system_prompt="Start. <user_specified_instruction></user_specified_instruction> End.",
        temperature=0.0
    )
    
    print("Default placeholder (<user_specified_instruction></user_specified_instruction>):")
    print("- Instructions applied:", "Default placeholder instructions here" in agent1.messages[0]["content"])
    print("- Placeholder removed:", "<user_specified_instruction>" not in agent1.messages[0]["content"])
    print()
    
    # Test custom placeholder
    from tinyagent.core.custom_instructions import CustomInstructionLoader
    loader = CustomInstructionLoader()
    loader.load_instructions("Custom placeholder instructions here.")
    
    custom_prompt = "Begin {{INSTRUCTIONS}} Finish"
    result = loader.apply_to_system_prompt(custom_prompt, "{{INSTRUCTIONS}}")
    
    print("Custom placeholder ({{INSTRUCTIONS}}):")
    print("- Instructions applied:", "Custom placeholder instructions here" in result)
    print("- Custom placeholder removed:", "{{INSTRUCTIONS}}" not in result)
    print("- Final result:", repr(result))
    print()
    
    await agent1.close()


async def demo_tinycode_integration():
    """Demonstrate integration with TinyCodeAgent."""
    print("=== Demo 7: TinyCodeAgent Integration ===")
    
    from tinyagent.code_agent import TinyCodeAgent
    
    # Create coding-specific instructions
    coding_instructions = """
You are a senior software engineer specialized in:

## Python Excellence
- Write clean, maintainable code
- Use appropriate design patterns
- Implement proper error handling
- Follow SOLID principles

## Code Review Mindset
- Consider edge cases
- Think about performance implications
- Suggest optimizations
- Ensure code readability

## Testing Philosophy
- Write testable code
- Suggest unit tests
- Consider integration scenarios
- Think about mocking strategies
"""
    
    try:
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            custom_instructions=coding_instructions,
            local_execution=True,
            enable_python_tool=True,
            enable_shell_tool=False  # Focus on Python only for this demo
        )
        
        # Check integration
        system_content = agent.messages[0]["content"]
        print("TinyCodeAgent with custom instructions:")
        print("- 'senior software engineer' found:", "senior software engineer" in system_content)
        print("- 'SOLID principles' found:", "SOLID principles" in system_content)
        print("- 'unit tests' found:", "unit tests" in system_content)
        print("- Python tool enabled:", agent.get_python_tool_status())
        print("- Shell tool disabled:", not agent.get_shell_tool_status())
        print()
        
        await agent.close()
        
    except Exception as e:
        print(f"TinyCodeAgent demo skipped due to: {e}")


async def demo_runtime_management():
    """Demonstrate runtime management of custom instructions."""
    print("=== Demo 8: Runtime Management ===")
    
    from tinyagent import TinyAgent
    
    # Create agent initially without custom instructions
    agent = TinyAgent(
        model="gpt-5-mini",
        system_prompt="Base system prompt.",
        temperature=0.0
    )
    
    print("Initial state:")
    print(f"- Custom instructions enabled: {agent.custom_instruction_loader.is_enabled()}")
    print(f"- Has instructions: {bool(agent.custom_instruction_loader.get_instructions())}")
    print()
    
    # Enable and load instructions at runtime
    agent.custom_instruction_loader.enable(True)
    agent.custom_instruction_loader.load_instructions("Runtime loaded instructions!")
    
    print("After runtime loading:")
    print(f"- Custom instructions enabled: {agent.custom_instruction_loader.is_enabled()}")
    print(f"- Has instructions: {bool(agent.custom_instruction_loader.get_instructions())}")
    print(f"- Instructions content: {repr(agent.custom_instruction_loader.get_instructions())}")
    print()
    
    # Test apply to new prompt
    new_prompt = "New prompt: <user_specified_instruction></user_specified_instruction>"
    modified_prompt = agent.custom_instruction_loader.apply_to_system_prompt(new_prompt)
    print("Modified prompt:", repr(modified_prompt))
    print()
    
    await agent.close()


async def main():
    """Run all custom instruction demos."""
    print("🚀 TinyAgent Custom Instruction System Demo")
    print("=" * 50)
    print()
    
    try:
        await demo_string_based_instructions()
        await demo_file_based_instructions()
        await demo_auto_detection()
        await demo_custom_configuration()
        await demo_disabled_instructions()
        await demo_placeholder_support()
        await demo_tinycode_integration()
        await demo_runtime_management()
        
        print("✅ All demos completed successfully!")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())