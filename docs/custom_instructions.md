# TinyAgent Custom Instruction System

The TinyAgent Custom Instruction System provides a powerful and flexible way to customize agent behavior through external instructions. This system supports multiple sources, automatic detection, and fine-grained configuration options.

## Features Overview

- ✅ **String and File Support**: Load instructions from strings or files
- ✅ **Automatic AGENTS.md Detection**: Auto-detect and load `AGENTS.md` files
- ✅ **Configurable Enable/Disable**: Turn the system on/off with proper warnings
- ✅ **Placeholder Support**: Insert instructions using `<user_specified_instruction></user_specified_instruction>`
- ✅ **Custom Filename Configuration**: Use custom filenames beyond `AGENTS.md`
- ✅ **Directory Control**: Specify execution directory for auto-detection
- ✅ **Subagent Inheritance**: Control whether subagents inherit custom instructions
- ✅ **Comprehensive Logging**: Detailed logging and warning messages
- ✅ **Error Handling**: Graceful fallback when instruction loading fails
- ✅ **Runtime Management**: Enable/disable and reload instructions at runtime

## Basic Usage

### String-Based Instructions

```python
from tinyagent import TinyAgent

# Define custom instructions as a string
custom_instructions = """
You are a helpful coding assistant with these special behaviors:
1. Always provide type hints in Python code
2. Include comprehensive error handling
3. Write detailed docstrings
4. Suggest performance optimizations when relevant
"""

agent = TinyAgent(
    model="gpt-5-mini",
    custom_instructions=custom_instructions,
    system_prompt="You are a helpful assistant. <user_specified_instruction></user_specified_instruction>",
    temperature=0.7
)
```

### File-Based Instructions

```python
from tinyagent import TinyAgent

# Load instructions from a file
agent = TinyAgent(
    model="gpt-5-mini",
    custom_instructions="/path/to/my_instructions.md",
    system_prompt="Base prompt. <user_specified_instruction></user_specified_instruction>",
)
```

### Automatic AGENTS.md Detection

```python
from tinyagent import TinyAgent

# Will automatically detect and load AGENTS.md from current directory
agent = TinyAgent(
    model="gpt-5-mini",
    enable_custom_instructions=True,  # This is the default
    system_prompt="You are an assistant. <user_specified_instruction></user_specified_instruction>",
)
```

## Configuration Options

### Basic Configuration

```python
from tinyagent import TinyAgent

agent = TinyAgent(
    model="gpt-5-mini",
    # Custom instruction parameters
    custom_instructions="Your custom instructions here",
    enable_custom_instructions=True,
    custom_instruction_config={
        "auto_detect_agents_md": True,
        "custom_filename": "AGENTS.md",
        "inherit_to_subagents": True,
        "execution_directory": "/path/to/project"
    }
)
```

### Advanced Configuration

```python
from tinyagent import TinyAgent

# Custom configuration for specific use cases
config = {
    "auto_detect_agents_md": True,
    "custom_filename": "TEAM_INSTRUCTIONS.txt",  # Custom filename
    "execution_directory": "/path/to/project/root",
    "inherit_to_subagents": False  # Prevent subagent inheritance
}

agent = TinyAgent(
    model="gpt-5-mini",
    enable_custom_instructions=True,
    custom_instruction_config=config
)
```

## TinyCodeAgent Integration

The custom instruction system works seamlessly with TinyCodeAgent:

```python
from tinyagent.code_agent import TinyCodeAgent

coding_instructions = """
You are a senior Python developer focused on:

## Code Quality
- Write clean, maintainable code
- Use appropriate design patterns
- Implement comprehensive error handling
- Follow PEP 8 standards

## Testing Philosophy
- Write testable code
- Suggest unit tests
- Consider integration scenarios
- Think about edge cases

## Performance Considerations
- Optimize for readability first
- Suggest performance improvements
- Consider memory usage
- Think about scalability
"""

agent = TinyCodeAgent(
    model="gpt-5-mini",
    custom_instructions=coding_instructions,
    local_execution=True,
    enable_python_tool=True,
    enable_shell_tool=True
)
```

## Placeholder System

The system supports flexible placeholder replacement:

### Default Placeholder

```python
system_prompt = "You are an assistant. <user_specified_instruction></user_specified_instruction> Help users."

# Custom instructions will replace the placeholder
agent = TinyAgent(
    model="gpt-5-mini",
    custom_instructions="Be enthusiastic and helpful!",
    system_prompt=system_prompt
)
```

### Custom Placeholders

```python
from tinyagent.core.custom_instructions import CustomInstructionLoader

loader = CustomInstructionLoader()
loader.load_instructions("Custom behavior instructions")

# Use a custom placeholder
system_prompt = "Start {{CUSTOM_BEHAVIOR}} End"
result = loader.apply_to_system_prompt(system_prompt, "{{CUSTOM_BEHAVIOR}}")
# Result: "Start Custom behavior instructions End"
```

### No Placeholder (Append Mode)

If no placeholder is found, instructions are appended:

```python
system_prompt = "You are a helpful assistant."
# With custom instructions, becomes:
# "You are a helpful assistant.\n\n## Custom Instructions\n[your instructions]"
```

## Runtime Management

You can manage custom instructions at runtime:

```python
from tinyagent import TinyAgent

agent = TinyAgent(model="gpt-5-mini")

# Check current state
config = agent.custom_instruction_loader.get_config()
print(f"Enabled: {config['enabled']}")
print(f"Has instructions: {config['has_instructions']}")

# Load instructions at runtime
agent.custom_instruction_loader.load_instructions("New runtime instructions!")

# Apply to a new system prompt
new_prompt = agent.custom_instruction_loader.apply_to_system_prompt(
    "Base prompt <user_specified_instruction></user_specified_instruction>"
)

# Enable/disable at runtime
agent.custom_instruction_loader.enable(False)  # Disable
agent.custom_instruction_loader.enable(True)   # Re-enable
```

## AGENTS.md File Format

Create an `AGENTS.md` file in your project root:

```markdown
# Project Custom Instructions

Brief description of the project context and agent role.

## Core Expertise
- Domain-specific knowledge areas
- Technical specializations
- Key responsibilities

## Behavior Guidelines
- Communication style preferences
- Response format requirements
- Specific behaviors to exhibit

## Technical Standards
- Coding standards to follow
- Libraries and frameworks to prefer
- Architecture patterns to use

## Example Format
```python
# Code examples showing preferred patterns
def example_function() -> str:
    """Well-documented function example."""
    return "Example"
```

Your instructions can include:
- Markdown formatting
- Code examples
- Lists and structure
- Technical specifications
```

## Error Handling

The system provides graceful error handling:

```python
from tinyagent import TinyAgent
from tinyagent.core.custom_instructions import CustomInstructionError

try:
    agent = TinyAgent(
        model="gpt-5-mini",
        custom_instructions="/nonexistent/file.md"
    )
except CustomInstructionError as e:
    print(f"Custom instruction error: {e}")
    # Agent will still be created with default behavior
```

## Logging and Debugging

Enable logging to see what's happening:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

from tinyagent import TinyAgent

agent = TinyAgent(
    model="gpt-5-mini",
    custom_instructions="Test instructions"
)

# Check the configuration
config = agent.custom_instruction_loader.get_config()
print("Configuration:", config)

# Get instruction details
print("Instructions:", agent.custom_instruction_loader.get_instructions())
print("Source:", agent.custom_instruction_loader.get_instruction_source())
```

## Best Practices

### 1. Use Clear, Structured Instructions

```markdown
# Good: Structured and specific
## Role
You are a data science assistant.

## Expertise
- Statistical analysis using Python
- Data visualization with matplotlib/seaborn
- Machine learning model evaluation

## Communication Style
- Provide code examples
- Explain statistical concepts clearly
- Suggest alternative approaches
```

### 2. Include Relevant Context

```markdown
# Good: Context-aware
You are working on a financial analysis project where:
- Data comes from Bloomberg API
- Regulatory compliance is critical
- Performance metrics must be documented
- All calculations need audit trails
```

### 3. Specify Technical Preferences

```python
# Good: Technical specifics
"""
## Code Standards
- Use pandas for data manipulation
- Prefer SQLAlchemy for database operations
- Include type hints for all functions
- Write unit tests for critical functions

## Error Handling
- Use specific exception types
- Log errors with context
- Provide user-friendly error messages
- Include recovery suggestions
"""
```

### 4. Test Your Instructions

```python
# Always test that instructions work as expected
agent = TinyAgent(
    model="gpt-5-mini",
    custom_instructions=your_instructions,
    system_prompt="Test: <user_specified_instruction></user_specified_instruction>"
)

# Verify the system prompt
print("System prompt contains expected text:", 
      "your_key_phrase" in agent.messages[0]["content"])
```

## Troubleshooting

### Common Issues

1. **Instructions Not Applied**
   ```python
   # Check if custom instructions are enabled
   print("Enabled:", agent.custom_instruction_loader.is_enabled())
   
   # Check if instructions were loaded
   print("Has instructions:", bool(agent.custom_instruction_loader.get_instructions()))
   ```

2. **File Not Found**
   ```python
   # Use absolute paths for clarity
   import os
   instruction_path = os.path.abspath("my_instructions.md")
   
   agent = TinyAgent(
       model="gpt-5-mini",
       custom_instructions=instruction_path
   )
   ```

3. **Placeholder Not Replaced**
   ```python
   # Ensure your system prompt includes the placeholder
   system_prompt = "Base prompt. <user_specified_instruction></user_specified_instruction>"
   
   # Or check if placeholder exists after processing
   final_prompt = agent.messages[0]["content"]
   print("Placeholder removed:", "<user_specified_instruction>" not in final_prompt)
   ```

### Debug Information

```python
from tinyagent import TinyAgent

agent = TinyAgent(
    model="gpt-5-mini",
    custom_instructions="test"
)

# Get comprehensive debug info
config = agent.custom_instruction_loader.get_config()
print("Debug Info:")
for key, value in config.items():
    print(f"  {key}: {value}")
```

## API Reference

### CustomInstructionLoader

```python
from tinyagent.core.custom_instructions import CustomInstructionLoader

# Create loader
loader = CustomInstructionLoader(
    enabled=True,
    auto_detect_agents_md=True,
    custom_filename="AGENTS.md",
    inherit_to_subagents=True,
    execution_directory="/path/to/dir"
)

# Core methods
loader.load_instructions(instructions)  # Load from string or file
loader.apply_to_system_prompt(prompt, placeholder)  # Apply to prompt
loader.get_instructions()  # Get current instructions
loader.get_instruction_source()  # Get source of instructions
loader.is_enabled()  # Check if enabled
loader.enable(True/False)  # Enable/disable
loader.get_config()  # Get configuration dict
```

### TinyAgent Parameters

```python
TinyAgent(
    # ... other parameters ...
    custom_instructions=None,  # Instructions as string or file path
    enable_custom_instructions=True,  # Enable/disable feature
    custom_instruction_config=None  # Configuration dictionary
)
```

### TinyCodeAgent Parameters

```python
TinyCodeAgent(
    # ... other parameters ...
    custom_instructions=None,  # Instructions as string or file path
    enable_custom_instructions=True,  # Enable/disable feature
    custom_instruction_config=None  # Configuration dictionary
)
```

## Migration Guide

If you're upgrading from a previous version:

### Before (Manual System Prompt Modification)
```python
system_prompt = f"""
{base_prompt}

Additional instructions:
{my_custom_instructions}
"""

agent = TinyAgent(model="gpt-5-mini", system_prompt=system_prompt)
```

### After (Custom Instruction System)
```python
agent = TinyAgent(
    model="gpt-5-mini",
    custom_instructions=my_custom_instructions,
    system_prompt=f"{base_prompt} <user_specified_instruction></user_specified_instruction>"
)
```

## Examples

See the complete examples in:
- `examples/custom_instructions_example.py` - Comprehensive demonstration
- `demo_custom_instructions.py` - Simple auto-detection demo
- `tests/test_custom_instructions.py` - Test suite with usage examples