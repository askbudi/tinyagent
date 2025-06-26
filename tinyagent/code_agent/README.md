# TinyCodeAgent

A specialized TinyAgent for code execution tasks with pluggable execution providers.

## Overview

TinyCodeAgent provides a high-level interface for creating AI agents that can execute Python code using various backend providers. It's designed with enterprise-grade software engineering practices in mind:

- **Extensible Provider System**: Easily add new execution providers (Modal, Docker, local, cloud functions, etc.)
- **Clean Architecture**: Separation of concerns with modular components
- **Enterprise Ready**: Production-ready code with proper error handling and logging
- **Minimal Code Changes**: Adding new providers requires minimal changes to user code

## Quick Start

### Basic Usage

```python
import asyncio
from tinyagent import TinyCodeAgent

async def main():
    # Initialize with minimal configuration
    agent = TinyCodeAgent(
        model="gpt-4.1-mini",
        api_key="your-openai-api-key"
    )
    
    try:
        result = await agent.run("Calculate the factorial of 10 using Python")
        print(result)
    finally:
        await agent.close()

asyncio.run(main())
```

### With Custom Tools

```python
from tinyagent import TinyCodeAgent
from tinyagent.code_agent.tools import get_weather, get_traffic

agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    api_key="your-api-key",
    tools=[get_weather, get_traffic]
)
```

### With Gradio UI

```python
from tinyagent.code_agent.example import run_example
import asyncio

# Run the full example with Gradio interface
asyncio.run(run_example())
```

## Architecture

### Directory Structure

```
code_agent/
├── __init__.py              # Main exports
├── tiny_code_agent.py       # Main TinyCodeAgent class
├── example.py              # Usage examples
├── utils.py                # Utility functions
├── providers/              # Execution providers
│   ├── __init__.py
│   ├── base.py            # Abstract base class
│   └── modal_provider.py  # Modal.com provider
└── tools/                 # Example tools
    ├── __init__.py
    └── example_tools.py   # Weather & traffic tools
```

### Provider System

The provider system allows you to easily switch between different code execution backends:

```python
# Use Modal (default)
agent = TinyCodeAgent(provider="modal")

# Future providers (planned)
# agent = TinyCodeAgent(provider="docker")
# agent = TinyCodeAgent(provider="local")
# agent = TinyCodeAgent(provider="lambda")
```

### Adding New Providers

To add a new execution provider:

1. Create a new class inheriting from `CodeExecutionProvider`
2. Implement the abstract methods: `execute_python()` and `cleanup()`
3. Register it in the `TinyCodeAgent._create_provider()` method

```python
from .providers.base import CodeExecutionProvider

class DockerProvider(CodeExecutionProvider):
    async def execute_python(self, code_lines, timeout=120):
        # Implementation here
        pass
    
    async def cleanup(self):
        # Cleanup here
        pass
```

## Configuration

### Basic Configuration

```python
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    api_key="your-api-key",
    provider="modal",
    tools=[],
    authorized_imports=["requests", "pandas", "numpy"],
    check_string_obfuscation=True  # Control string obfuscation detection
)
```

### Provider-Specific Configuration

```python
# Modal provider configuration
modal_config = {
    "modal_secrets": {"OPENAI_API_KEY": "your-key"},
    "pip_packages": ["requests", "pandas"],
    "sandbox_name": "my-sandbox",
    "check_string_obfuscation": False  # Allow base64 and other string manipulations
}

agent = TinyCodeAgent(
    provider="modal",
    provider_config=modal_config
)
```

## Features

### Code Execution
- Secure sandboxed Python execution
- Session persistence across executions
- Error handling and debugging support
- Automatic dependency management
- Configurable security checks for legitimate use cases

### Integration
- Gradio UI support for interactive chat
- MCP (Model Context Protocol) server support
- Logging and monitoring
- File upload/download capabilities

### Tools
- Built-in example tools (weather, traffic)
- Easy tool addition and management
- Tool metadata translation for code agents

## Examples

### Simple Query
```python
result = await agent.run("Create a simple web scraper for news headlines")
```

### Data Analysis
```python
result = await agent.run("""
Analyze this dataset and create visualizations:
- Load the CSV file I uploaded
- Create bar charts and scatter plots
- Generate summary statistics
""")
```

### Multi-City Weather Check
```python
result = await agent.run("""
Check the weather and traffic for Toronto, Montreal, 
New York, Paris, and San Francisco
""")
```

### Base64 Encoding/Decoding

By default, TinyCodeAgent blocks code that uses base64 encoding/decoding as a security measure. 
For legitimate use cases, you can disable this check:

```python
# Create agent with string obfuscation detection disabled
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    check_string_obfuscation=False  # Allow base64 encoding/decoding
)

# Or toggle at runtime
agent.set_check_string_obfuscation(False)  # Disable check
agent.set_check_string_obfuscation(True)   # Re-enable check
```

See `examples/base64_example.py` for a complete example.

## Best Practices

1. **Always use async/await**: TinyCodeAgent is designed for async operation
2. **Close resources**: Call `await agent.close()` when done
3. **Handle errors**: Wrap agent calls in try/except blocks
4. **Use logging**: Configure LoggingManager for debugging
5. **Provider configuration**: Use appropriate secrets management for production

## Development

### Running Tests
```bash
# Run the simple example
python -m tinyagent.code_agent.example

# Run with environment setup
export OPENAI_API_KEY="your-key"
python -m tinyagent.code_agent.example
```

### Contributing
- Follow the coding criteria in the cursor_rules
- Add examples to new features
- Use "gpt-4.1-mini" as default model in examples
- Include proper error handling and logging

## Requirements

- Python 3.8+
- TinyAgent framework
- Modal account (for Modal provider)
- OpenAI API key or compatible LLM API

## Future Roadmap

- [ ] Docker execution provider
- [ ] Local execution provider  
- [ ] AWS Lambda provider
- [ ] Google Cloud Functions provider
- [ ] Enhanced security features
- [ ] Performance optimizations
- [ ] More example tools and templates 