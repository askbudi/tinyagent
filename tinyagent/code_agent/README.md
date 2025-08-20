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

### Using Local Models with Ollama

TinyCodeAgent supports local models through Ollama for code execution tasks without requiring cloud APIs.

#### Prerequisites

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull code-optimized models:
   ```bash
   ollama pull codellama       # Best for code generation
   ollama pull deepseek-coder  # Specialized for coding
   ollama pull mixtral         # Good for complex reasoning
   ollama pull llama2          # General purpose alternative
   ```

#### Basic Ollama Setup

```python
import asyncio
from tinyagent import TinyCodeAgent

async def main():
    # Initialize with Ollama model
    agent = TinyCodeAgent(
        model="ollama/codellama",  # Code-optimized model
        api_key=None,  # No API key needed
        provider="seatbelt",  # Local sandbox execution
        enable_python_tool=True,
        enable_shell_tool=True,
        enable_file_tools=True
    )
    
    try:
        result = await agent.run("""
        Create a Python class for a binary search tree with insert, 
        search, and traversal methods. Test it with sample data.
        """)
        print(result)
    finally:
        await agent.close()

asyncio.run(main())
```

#### Advanced Ollama Configuration

```python
from tinyagent import TinyCodeAgent
from tinyagent.hooks.rich_ui_callback import RichUICallback

async def main():
    # Enhanced configuration for local development
    agent = TinyCodeAgent(
        model="ollama/deepseek-coder",  # Specialized coding model
        api_key=None,
        
        # Provider configuration for local execution
        provider="seatbelt",
        provider_config={
            "python_env_path": "/usr/local/bin/python3",
            "additional_read_dirs": ["/path/to/your/project"],
            "additional_write_dirs": ["/path/to/output"],
            "bypass_shell_safety": True  # More permissive for local dev
        },
        
        # Model-specific parameters
        model_kwargs={
            "api_base": "http://localhost:11434",
            "num_ctx": 4096,  # Context window
            "temperature": 0.1,  # Lower for more deterministic code
            "top_p": 0.9,
            "repeat_penalty": 1.05
        },
        
        # Enable all code tools
        enable_python_tool=True,
        enable_shell_tool=True, 
        enable_file_tools=True,
        enable_todo_write=True,
        
        # Local settings
        default_workdir="/path/to/your/project",
        auto_git_checkpoint=True,
        
        # UI enhancement
        ui="rich"
    )
    
    # Add rich terminal interface
    ui_callback = RichUICallback(
        show_thinking=True,
        show_tool_calls=True,
        markdown=True
    )
    agent.add_callback(ui_callback)
    
    try:
        result = await agent.run("""
        Analyze this Python project structure:
        1. Use glob to find all Python files
        2. Use grep to find all class definitions
        3. Create a dependency graph
        4. Generate refactoring suggestions
        """)
        print("Analysis complete:", result)
    finally:
        await agent.close()

asyncio.run(main())
```

#### Model Recommendations for Code Tasks

| Model | Best For | Performance | Resource Usage |
|-------|----------|-------------|----------------|
| `ollama/codellama` | General coding, debugging | Good | Medium |
| `ollama/deepseek-coder` | Complex code analysis, architecture | Excellent | High |
| `ollama/mixtral` | Code reasoning, explanations | Very Good | High |
| `ollama/llama2` | Simple scripts, learning | Fair | Low |
| `ollama/phi` | Quick code snippets | Fair | Very Low |

#### Performance Optimization for Code Tasks

```python
# Optimize for coding tasks
agent = TinyCodeAgent(
    model="ollama/codellama",
    model_kwargs={
        "num_ctx": 8192,      # Larger context for code files
        "temperature": 0.1,    # Deterministic for code generation
        "top_k": 10,          # Focused token selection
        "top_p": 0.8,         # Conservative sampling
        "repeat_penalty": 1.1, # Avoid repetitive code
        "num_thread": 8,      # Use available CPU cores
        "num_gpu": 1 if "cuda" else 0  # GPU acceleration if available
    },
    
    # Optimize for local execution
    provider="seatbelt",
    truncation_config={
        "max_tokens": 8000,   # Handle longer code outputs
        "max_lines": 500,
        "enabled": True
    }
)
```

#### Code-Specific Examples

```python
# Code analysis and refactoring
result = await agent.run("""
Use the file tools to analyze this codebase:
1. Find all Python files with glob
2. Search for TODO comments with grep
3. Read the main module files
4. Suggest refactoring improvements
5. Create implementation plan with todos
""")

# Algorithm implementation
result = await agent.run("""
Implement and test these algorithms:
1. Quicksort with visualization
2. Dijkstra's shortest path
3. Binary search with edge cases
4. Create performance benchmarks
""")

# Full-stack development
result = await agent.run("""
Create a simple web API:
1. Design FastAPI application structure
2. Implement database models with SQLAlchemy
3. Create REST endpoints with validation
4. Add unit tests and documentation
5. Use file tools to organize the code properly
""")
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

### Using the Bash tool (updated API)

The bash tool now accepts a single command string and optional working directory:

```python
# Good: single command string
# bash(command="ls -la")
# bash(command="npm test", absolute_workdir="/abs/path/to/project")
```

Prefer specialized tools for file operations and search:
- Use `read_file`, `write_file`, `update_file` for file manipulation (sandboxed)
- Use `glob` for file pattern matching (sandboxed)
- Use `grep` for content search (sandboxed)

### File tools (sandboxed)

File tools route through the provider (Seatbelt/Modal), keeping operations sandboxed:

```python
# read_file(file_path="/abs/path/to/README.md", start_line=1, max_lines=100)
# write_file(file_path="/abs/path/to/notes.txt", content="Hello", create_dirs=True)
# update_file(file_path="/abs/path/to/app.py", old_content="foo()", new_content="bar()", expected_matches=1)
# glob(pattern="**/*.py", absolute_path="/abs/path/to/repo")
# grep(pattern="TODO", absolute_path="/abs/path/to/repo", output_mode="files_with_matches")
```

These tools integrate with universal tool control hooks, enabling approval flows (e.g., display diffs for `write_file`/`update_file`).

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

### Automatic Git Checkpoints

TinyCodeAgent can automatically create Git checkpoints after each successful shell command execution. This helps track changes made by the agent and provides a safety net for reverting changes if needed.

```python
# Enable during initialization
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    auto_git_checkpoint=True  # Enable automatic Git checkpoints
)

# Or enable/disable later
agent.enable_auto_git_checkpoint(True)   # Enable
agent.enable_auto_git_checkpoint(False)  # Disable

# Check current status
is_enabled = agent.get_auto_git_checkpoint_status()
```

Each checkpoint includes:
- Descriptive commit message with the command description
- Timestamp of when the command was executed
- The actual command that was run

This feature is particularly useful for:
- Tracking changes during development sessions
- Creating a history of agent actions
- Providing a safety net to revert changes if needed
- Documenting the agent's workflow for audit purposes

## Hook System Integration

TinyCodeAgent inherits the full TinyAgent hook system. You can add any TinyAgent hooks to enhance functionality:

### Adding Hooks to TinyCodeAgent

```python
from tinyagent import TinyCodeAgent
from tinyagent.hooks.token_tracker import TokenTracker
from tinyagent.hooks.rich_ui_callback import RichUICallback
from tinyagent.hooks.message_cleanup import MessageCleanupHook

# Create agent
agent = TinyCodeAgent(model="gpt-4.1-mini")

# Add token tracking
tracker = TokenTracker(name="code_agent")
agent.add_callback(tracker)

# Add rich terminal UI
ui = RichUICallback()
agent.add_callback(ui)

# Add message cleanup for certain providers
cleanup = MessageCleanupHook()
agent.add_callback(cleanup)

# Use normally
result = await agent.run("Create a data visualization script")

# View token usage
tracker.print_summary()
```

### Available Hooks

All TinyAgent hooks work with TinyCodeAgent:
- **TokenTracker**: Track token usage and costs
- **RichUICallback**: Rich terminal display
- **GradioCallback**: Web-based interface
- **MessageCleanupHook**: Clean message fields for certain providers
- **AnthropicPromptCacheCallback**: Prompt caching for Claude models
- **JupyterNotebookCallback**: Jupyter integration

See the [main README](../../README.md) for detailed hook documentation.

## Best Practices

1. **Always use async/await**: TinyCodeAgent is designed for async operation
2. **Close resources**: Call `await agent.close()` when done
3. **Handle errors**: Wrap agent calls in try/except blocks
4. **Use logging**: Configure LoggingManager for debugging
5. **Provider configuration**: Use appropriate secrets management for production
6. **Hook usage**: Add appropriate hooks for monitoring, UI, and token tracking

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