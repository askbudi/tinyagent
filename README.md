# TinyAgent
Tiny Agent: 100 lines Agent with MCP and extendable hook system

[![AskDev.AI | Chat with TinyAgent](https://img.shields.io/badge/AskDev.AI-Chat_with_TinyAgent-blue?style=flat-square)](https://askdev.ai/github/askbudi/tinyagent)


![TinyAgent Logo](https://raw.githubusercontent.com/askbudi/tinyagent/main/public/logo.png)


[![AskDev.AI | Chat with TinyAgent](https://img.shields.io/badge/AskDev.AI-Chat_with_TinyAgent-blue?style=flat-square)](https://askdev.ai/github/askbudi/tinyagent)


Inspired by:
- [Tiny Agents blog post](https://huggingface.co/blog/tiny-agents)
- [12-factor-agents repository](https://github.com/humanlayer/12-factor-agents)
- Created by chatting to the source code of JS Tiny Agent using [AskDev.ai](https://askdev.ai/search)

## Quick Links
- [Build your own Tiny Agent](https://askdev.ai/github/askbudi/tinyagent)


## Live Projects using TinyAgent (🔥)
- [AskDev.AI](https://askdev.ai) - Understand, chat, and summarize codebase of any project on GitHub.
- [HackBuddy AI](https://huggingface.co/spaces/ask-dev/HackBuddyAI) - A Hackathon Assistant Agent, built with TinyCodeAgent and Gradio. Match invdividuals to teams based on their skills, interests and organizer preferences.

- [TinyCodeAgent Demo](https://huggingface.co/spaces/ask-dev/TinyCodeAgent) - A playground for TinyCodeAgent, built with tinyagent, Gradio and Modal.com

** Building something with TinyAgent? Let us know and I'll add it here!**


## Overview
This is a tiny agent framework that uses MCP and LiteLLM to interact with language models. You have full control over the agent, you can add any tools you like from MCP and extend the agent using its event system.

**Three Main Components:**
- **TinyAgent**: Core agent with MCP tool integration and extensible hooks
- **TinyCodeAgent**: Specialized agent for secure Python code execution with pluggable providers  
- **Subagent Tools**: Revolutionary parallel task execution system with context isolation and specialized workers

### What's new for developers

- **Sandboxed File Tools**: `read_file`, `write_file`, `update_file`, `glob`, `grep` now route through provider sandboxes (Seatbelt/Modal) for secure file operations
- **Enhanced Shell Tool**: Improved `bash` tool with better safety validation, platform-specific tips, and provider-backed execution
- **TodoWrite Tool**: Built-in task management system for tracking progress and organizing complex workflows
- **Provider System**: Pluggable execution backends (Modal.com, Seatbelt sandbox) with unified API
- **Universal Tool Hooks**: Control any tool execution via `before_tool_execution`/`after_tool_execution` callbacks
- **Subagent Tools**: Revolutionary parallel task execution with specialized workers and context isolation
- **Enhanced Security**: Comprehensive validation, sandboxing, and permission controls

## Installation

### Using pip
```bash
# Basic installation
pip install tinyagent-py

# Install with all optional dependencies
pip install tinyagent-py[all]

# Install with Code Agent support
pip install tinyagent-py[code]


# Install with PostgreSQL support
pip install tinyagent-py[postgres]

# Install with SQLite support
pip install tinyagent-py[sqlite]

# Install with Gradio UI support
pip install tinyagent-py[gradio]





```

### Using uv
```bash
# Basic installation
uv pip install tinyagent-py

# Install with Code Agent support
uv pip install tinyagent-py[code]


# Install with PostgreSQL support
uv pip install tinyagent-py[postgres]

# Install with SQLite support
uv pip install tinyagent-py[sqlite]

# Install with Gradio UI support
uv pip install tinyagent-py[gradio]

# Install with all optional dependencies
uv pip install tinyagent-py[all]

```

## Developer Boilerplate & Quick Start

### 🚀 TinyAgent with New Tools

```python
import asyncio
import os
from tinyagent import TinyAgent
from tinyagent.tools.subagent import create_general_subagent
from tinyagent.tools.todo_write import enable_todo_write_tool

async def create_enhanced_tinyagent():
    """Create a TinyAgent with all new tools and capabilities."""
    
    # Initialize TinyAgent
    agent = TinyAgent(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        enable_todo_write=True  # Enable TodoWrite tool by default
    )
    
    # Add a general-purpose subagent for parallel tasks
    helper_subagent = create_general_subagent(
        name="helper",
        model="gpt-4.1-mini",
        max_turns=20,
        enable_python=True,
        enable_shell=True
    )
    agent.add_tool(helper_subagent)
    
    # Connect to MCP servers for extended functionality
    await agent.connect_to_server("npx", ["@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    
    return agent

async def main():
    agent = await create_enhanced_tinyagent()
    
    try:
        # Example: Complex task with subagent delegation
        result = await agent.run("""
            I need help with a travel planning project:
            1. Create a todo list for this task
            2. Use the helper subagent to find 5 accommodations in Paris for December 2024
            3. Research transportation options between airports and city center
            4. Organize all findings into a structured report
            
            Make sure to track progress with the todo system.
        """)
        
        print("Result:", result)
    finally:
        await agent.close()

# Run the example
asyncio.run(main())
```

### 🛠️ TinyCodeAgent with File Tools & Providers

```python
import asyncio
import os
from tinyagent import TinyCodeAgent
from tinyagent.hooks.rich_code_ui_callback import RichCodeUICallback

async def create_enhanced_code_agent():
    """Create TinyCodeAgent with all file tools and provider features."""
    
    # Option 1: Using Seatbelt Provider (macOS sandbox)
    seatbelt_agent = TinyCodeAgent(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        provider="seatbelt",
        provider_config={
            "python_env_path": "/usr/local/bin/python3",
            "additional_read_dirs": ["/Users/username/projects"],
            "additional_write_dirs": ["/Users/username/projects/output"],
            "environment_variables": {"PROJECT_ROOT": "/Users/username/projects"}
        },
        # Enable all new tools
        enable_python_tool=True,
        enable_shell_tool=True, 
        enable_file_tools=True,
        enable_todo_write=True,
        # Working directory for operations
        default_workdir="/Users/username/projects",
        # Auto git checkpoints after shell commands
        auto_git_checkpoint=True,
        # Rich UI for better visualization
        ui="rich"
    )
    
    return seatbelt_agent

async def create_modal_code_agent():
    """Create TinyCodeAgent with Modal.com provider."""
    
    modal_agent = TinyCodeAgent(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        provider="modal",
        provider_config={
            "pip_packages": ["requests", "pandas", "matplotlib", "seaborn"],
            "bypass_shell_safety": False  # More restrictive for cloud execution
        },
        authorized_imports=["requests", "pandas", "matplotlib", "seaborn", "numpy"],
        enable_python_tool=True,
        enable_shell_tool=True,
        enable_file_tools=True,
        enable_todo_write=True,
        local_execution=False,  # Use Modal cloud execution
        truncation_config={
            "max_tokens": 5000,
            "max_lines": 300,
            "enabled": True
        }
    )
    
    return modal_agent

async def demonstrate_file_tools():
    """Demonstrate the new file tools functionality."""
    
    agent = await create_enhanced_code_agent()
    
    try:
        result = await agent.run("""
        I need to analyze a Python project structure:
        
        1. Use glob to find all Python files in the current directory
        2. Use grep to search for "class" definitions across all Python files
        3. Read the main configuration file if it exists
        4. Create a summary report of the project structure
        5. Track progress with todos
        
        Make sure to use the new file tools for secure operations.
        """)
        
        print("Analysis Result:", result)
        
    finally:
        await agent.close()

# Choose your provider
async def main():
    print("Demonstrating TinyCodeAgent with enhanced file tools...")
    await demonstrate_file_tools()

asyncio.run(main())
```

### 📁 File Tools Usage Examples

```python
import asyncio
from tinyagent import TinyCodeAgent

async def file_tools_examples():
    """Examples of using the new sandboxed file tools."""
    
    agent = TinyCodeAgent(
        model="gpt-4.1-mini",
        provider="seatbelt",  # or "modal"
        enable_file_tools=True
    )
    
    try:
        # Example 1: Project structure analysis
        await agent.run("""
        Use glob to find all Python files in this project:
        - Pattern: "**/*.py" 
        - Search in: "/Users/username/myproject"
        
        Then use grep to find all function definitions:
        - Pattern: "def "
        - Search in the same directory
        
        Finally, read the main.py file to understand the entry point.
        """)
        
        # Example 2: Safe file modification
        await agent.run("""
        I need to update a configuration file:
        1. Read config.json to see current settings
        2. Update the database URL using update_file tool
        3. Verify the changes were applied correctly
        
        Make sure to use exact string matching for safety.
        """)
        
        # Example 3: Code generation and file creation
        await agent.run("""
        Create a new Python module:
        1. Use write_file to create utils/helpers.py
        2. Add utility functions for string manipulation
        3. Include proper docstrings and type hints
        4. Create a simple test file for the utilities
        """)
        
    finally:
        await agent.close()

asyncio.run(file_tools_examples())
```

### 🔧 Grep and Glob Tool Examples

```python
# Glob tool examples
await agent.run("""
Find all JavaScript files in the frontend directory:
Use glob with pattern "**/*.{js,jsx}" in "/path/to/frontend"
""")

await agent.run("""
Find all markdown documentation:
Use glob with pattern "**/*.md" in "/path/to/project"
""")

# Grep tool examples  
await agent.run("""
Search for all TODO comments in the codebase:
Use grep with pattern "TODO|FIXME|XXX" and regex=True
Search in "/path/to/project" directory
Use output_mode="content" to see the actual lines
""")

await agent.run("""
Find all API endpoints in Python files:
Use grep with pattern "@app.route" 
Search only in Python files using glob="**/*.py"
""")
```

### 📋 TodoWrite Tool Integration

```python
import asyncio
from tinyagent import TinyAgent
from tinyagent.tools.todo_write import get_current_todos, get_todo_summary

async def todo_workflow_example():
    """Example of using TodoWrite for task management."""
    
    agent = TinyAgent(
        model="gpt-4.1-mini",
        enable_todo_write=True  # Enabled by default
    )
    
    try:
        # The agent can automatically use TodoWrite during complex tasks
        result = await agent.run("""
        I need to build a web scraping system:
        1. Create a todo list for this project
        2. Research the target website structure
        3. Implement the scraping logic with error handling
        4. Add data validation and cleaning
        5. Create output formatting and export functions
        6. Write tests for each component
        7. Update todos as you progress
        
        Use the TodoWrite tool to track all these steps.
        """)
        
        # Check current todos programmatically
        current_todos = get_current_todos()
        summary = get_todo_summary()
        
        print(f"Project Status: {summary}")
        print(f"Active Todos: {len(current_todos)}")
        
    finally:
        await agent.close()

asyncio.run(todo_workflow_example())
```

### 🔒 Universal Tool Control with Hooks

```python
import asyncio
from tinyagent import TinyCodeAgent
from tinyagent.code_agent.tools.file_tools import FileOperationApprovalHook, ProductionApprovalHook

class CustomFileHook(FileOperationApprovalHook):
    """Custom hook for file operation control."""
    
    async def before_tool_execution(self, event_name: str, agent, **kwargs):
        tool_name = kwargs.get("tool_name")
        tool_args = kwargs.get("tool_args", {})
        
        # Custom logic for file operations
        if tool_name in ["write_file", "update_file"]:
            file_path = tool_args.get("file_path", "")
            
            # Block operations on sensitive files
            if "secret" in file_path.lower() or "password" in file_path.lower():
                print(f"🚫 Blocked file operation on sensitive file: {file_path}")
                return {"proceed": False, "reason": "Sensitive file access denied"}
            
            # Log all file modifications
            print(f"📝 File operation: {tool_name} on {file_path}")
        
        return {"proceed": True}

async def controlled_agent_example():
    """Example of agent with file operation controls."""
    
    agent = TinyCodeAgent(
        model="gpt-4.1-mini", 
        provider="seatbelt",
        enable_file_tools=True
    )
    
    # Add custom file control hook
    file_hook = CustomFileHook(auto_approve=False)
    agent.add_callback(file_hook)
    
    try:
        await agent.run("""
        Analyze and modify some project files:
        1. Read the main application file
        2. Update version information in package.json
        3. Create a backup of important configuration
        
        The system will control which operations are allowed.
        """)
        
    finally:
        await agent.close()

asyncio.run(controlled_agent_example())
```

## Usage

### TinyAgent (Core Agent)
[![AskDev.AI | Chat with TinyAgent](https://img.shields.io/badge/AskDev.AI-Chat_with_TinyAgent-blue?style=flat-square)](https://askdev.ai/github/askbudi/tinyagent)


```python
from tinyagent import TinyAgent
from textwrap import dedent
import asyncio
import os

async def test_agent(task, model="o4-mini", api_key=None):
    # Initialize the agent with model and API key
    agent = TinyAgent(
        model=model,  # Or any model supported by LiteLLM
        api_key=os.environ.get("OPENAI_API_KEY") if not api_key else api_key  # Set your API key as an env variable
    )
    
    try:
        # Connect to an MCP server
        # Replace with your actual server command and args
        await agent.connect_to_server("npx", ["@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
        
        # Run the agent with a user query
        result = await agent.run(task)
        print("\nFinal result:", result)
        return result
    finally:
        # Clean up resources
        await agent.close()

# Example usage
task = dedent("""
I need accommodation in Toronto between 15th to 20th of May. Give me 5 options for 2 adults.
""")
await test_agent(task, model="gpt-4.1-mini")
```

## TinyCodeAgent - Advanced Code Execution with File Tools

TinyCodeAgent is a specialized agent for secure code execution with comprehensive file operations, multiple provider backends, and advanced tooling.

### Key New Features

- **🔒 Sandboxed File Operations**: Native `read_file`, `write_file`, `update_file`, `glob`, `grep` tools
- **🛠️ Provider System**: Switch between Modal.com (cloud) and Seatbelt (local sandbox) execution
- **📋 Built-in Task Management**: Integrated TodoWrite tool for tracking complex workflows  
- **🔧 Enhanced Shell Tool**: Improved `bash` tool with validation and platform-specific guidance
- **🎯 Universal Tool Hooks**: Control and audit any tool execution with callback system
- **⚡ Auto Git Checkpoints**: Automatic version control after shell commands
- **🖥️ Rich UI Integration**: Enhanced terminal and Jupyter interfaces

### Quick Start with Enhanced TinyCodeAgent

```python
import asyncio
from tinyagent import TinyCodeAgent

async def main():
    # Initialize with all new features enabled
    agent = TinyCodeAgent(
        model="gpt-4.1-mini",
        api_key="your-openai-api-key",
        provider="seatbelt",  # or "modal" for cloud execution
        
        # Enable all new tools
        enable_file_tools=True,      # read_file, write_file, update_file, glob, grep
        enable_shell_tool=True,      # Enhanced bash tool
        enable_todo_write=True,      # Task management
        
        # Provider-specific config
        provider_config={
            "additional_read_dirs": ["/path/to/your/project"],
            "additional_write_dirs": ["/path/to/output"],
            "python_env_path": "/usr/local/bin/python3"
        },
        
        # Auto git checkpoints
        auto_git_checkpoint=True,
        
        # Rich terminal UI
        ui="rich"
    )
    
    try:
        # Complex task with file operations and task tracking
        result = await agent.run("""
        I need to analyze and refactor a Python project:
        
        1. Use glob to find all Python files in the project
        2. Use grep to identify functions that need refactoring
        3. Read key files to understand the architecture  
        4. Create a refactoring plan with todos
        5. Implement improvements with file operations
        6. Run tests to verify changes
        
        Use the todo system to track progress throughout.
        """)
        
        print(result)
    finally:
        await agent.close()

asyncio.run(main())
```

### TinyCodeAgent with Gradio UI

Launch a complete web interface for interactive code execution:

```python
from tinyagent.code_agent.example import run_example
import asyncio

# Run the full example with Gradio interface
asyncio.run(run_example())
```

### Key Features

- **🔒 Secure Execution**: Sandboxed Python code execution using Modal.com or other providers
- **🔧 Extensible Providers**: Switch between Modal, Docker, local execution, or cloud functions
- **🎯 Built for Enterprise**: Production-ready with proper logging, error handling, and resource cleanup  
- **📁 File Support**: Upload and process files through the Gradio interface
- **🛠️ Custom Tools**: Add your own tools and functions easily
- **📊 Session Persistence**: Code state persists across executions

### Provider System

TinyCodeAgent uses a pluggable provider system - change execution backends with minimal code changes:

```python
# Use Modal (default) - great for production
agent = TinyCodeAgent(provider="modal")

# Future providers (coming soon)
# agent = TinyCodeAgent(provider="docker")
# agent = TinyCodeAgent(provider="local") 
# agent = TinyCodeAgent(provider="lambda")
```

### Example Use Cases

**Web Scraping:**
```python
result = await agent.run("""
What are trending spaces on huggingface today?
""")
# Agent will create a python tool to request HuggingFace API and find trending spaces
```

**Use code to solve a task:**
```python
response = await agent.run(dedent("""
Suggest me 13 tags for my Etsy Listing, each tag should be multiworded and maximum 20 characters. Each word should be used only once in the whole corpus, And tags should cover different ways people are searching for the product on Etsy.
- You should use your coding abilities to check your answer pass the criteria and continue your job until you get to the answer.
                                
My Product is **Wedding Invitation Set of 3, in sage green color, with a gold foil border.**
"""),max_turns=20)

print(response)
# LLM is not good at this task, counting characters, avoid duplicates, but with the power of code, tiny model like gpt-4.1-mini can do it without any problem.
```


### Full Configuration Options

```python
from tinyagent import TinyCodeAgent
from tinyagent.code_agent.tools.file_tools import ProductionApprovalHook

# Complete configuration example with all new features
agent = TinyCodeAgent(
    # Core configuration
    model="gpt-4.1-mini",
    api_key="your-api-key",
    
    # Provider selection and config
    provider="seatbelt",  # "modal", "seatbelt", or "local"
    provider_config={
        # Seatbelt-specific options
        "python_env_path": "/usr/local/bin/python3",
        "additional_read_dirs": ["/Users/username/projects", "/Users/username/data"],
        "additional_write_dirs": ["/Users/username/projects/output"],
        "environment_variables": {
            "PROJECT_ROOT": "/Users/username/projects",
            "DATA_PATH": "/Users/username/data"
        },
        "bypass_shell_safety": True,  # More permissive for local development
        
        # Modal-specific options (if using provider="modal")
        # "pip_packages": ["requests", "pandas", "matplotlib"],
        # "bypass_shell_safety": False,  # More restrictive for cloud
    },
    
    # Tool enablement (all True by default)
    enable_python_tool=True,         # Python code execution
    enable_shell_tool=True,          # Enhanced bash tool
    enable_file_tools=True,          # read_file, write_file, update_file, glob, grep
    enable_todo_write=True,          # Task management system
    
    # Python environment setup
    authorized_imports=["requests", "pandas", "numpy", "matplotlib", "seaborn"],
    pip_packages=["requests", "pandas", "matplotlib"],  # For Modal provider
    
    # File and shell operations
    default_workdir="/Users/username/projects",
    auto_git_checkpoint=True,        # Auto git commits after shell commands
    
    # Output control
    truncation_config={
        "max_tokens": 5000,
        "max_lines": 300, 
        "enabled": True
    },
    
    # UI and logging
    ui="rich",                       # "rich", "jupyter", or None
    log_manager=None,                # Optional LoggingManager instance
    
    # Security and validation
    check_string_obfuscation=True,   # Check for potential obfuscated code
    
    # Memory management
    summary_config={
        "max_messages": 50,
        "summary_model": "gpt-4.1-mini"
    }
)

# Add custom file operation controls
file_hook = ProductionApprovalHook()  # Requires approval for file modifications
agent.add_callback(file_hook)
```

### Provider-Specific Configuration

#### Seatbelt Provider (Local macOS Sandbox)
```python
seatbelt_config = {
    "python_env_path": "/usr/local/bin/python3",
    "additional_read_dirs": ["/path/to/read/access"],
    "additional_write_dirs": ["/path/to/write/access"], 
    "environment_variables": {"VAR": "value"},
    "bypass_shell_safety": True  # More permissive for local dev
}

agent = TinyCodeAgent(provider="seatbelt", provider_config=seatbelt_config)
```

#### Modal Provider (Cloud Execution)
```python
modal_config = {
    "pip_packages": ["requests", "pandas", "matplotlib"],
    "bypass_shell_safety": False,  # More restrictive for cloud
    "additional_safe_shell_commands": ["custom_cmd"],
}

agent = TinyCodeAgent(
    provider="modal", 
    provider_config=modal_config,
    local_execution=False  # Use Modal cloud (default)
)
```

### Automatic Git Checkpoints

TinyCodeAgent can automatically create Git checkpoints after each successful shell command execution. This helps track changes made by the agent and provides a safety net for reverting changes if needed.

```python
# Enable automatic Git checkpoints during initialization
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    auto_git_checkpoint=True  # Enable automatic Git checkpoints
)

# Or enable/disable it later
agent.enable_auto_git_checkpoint(True)  # Enable
agent.enable_auto_git_checkpoint(False)  # Disable

# Check current status
is_enabled = agent.get_auto_git_checkpoint_status()
```

Each checkpoint includes:
- Descriptive commit message with the command description
- Timestamp of when the command was executed
- The actual command that was run

For detailed documentation, see the [TinyCodeAgent README](tinyagent/code_agent/README.md).

## 🚀 Subagent Tools - Parallel Task Execution (New!)

The subagent system enables you to create specialized AI workers that can execute tasks in parallel with complete context isolation. Each subagent operates independently with its own conversation history, resource management, and cleanup.

### Quick Start with Subagents

```python
import asyncio
from tinyagent import TinyAgent
from tinyagent.tools.subagent import create_general_subagent, create_coding_subagent

async def main():
    # Create main agent
    main_agent = TinyAgent(
        model="gpt-4o-mini",
        api_key="your-api-key"
    )
    
    # Add a general-purpose subagent
    helper = create_general_subagent(
        name="helper",
        model="gpt-4.1-mini",
        max_turns=15,
        enable_python=True,
        enable_shell=True
    )
    main_agent.add_tool(helper)
    
    # Add a specialized coding subagent  
    coder = create_coding_subagent(
        name="coder",
        model="claude-3-sonnet",
        max_turns=25
    )
    main_agent.add_tool(coder)
    
    # Use subagents in parallel
    result = await main_agent.run("""
        I need help with a Python project:
        1. Use coder to implement a binary search algorithm
        2. Use helper to create unit tests for it
        3. Use helper to benchmark the performance
        
        Make sure both tasks run efficiently and provide comprehensive results.
    """)
    
    print(result)

asyncio.run(main())
```

### Specialized Subagent Types

The subagent system provides pre-configured factories for common use cases:

```python
from tinyagent.tools.subagent import (
    create_research_subagent,
    create_coding_subagent, 
    create_analysis_subagent,
    create_writing_subagent,
    create_planning_subagent
)

# Research subagent - optimized for information gathering
researcher = create_research_subagent(
    name="researcher",
    model="gpt-4o",
    max_turns=20
)

# Coding subagent - with Python/shell execution
coder = create_coding_subagent(
    name="coder", 
    model="claude-3-sonnet",
    local_execution=True,
    timeout=300  # 5 minute timeout
)

# Analysis subagent - for data analysis tasks
analyst = create_analysis_subagent(
    name="analyst",
    model="gpt-4.1-mini",
    enable_python_tool=True
)

# Writing subagent - for content creation
writer = create_writing_subagent(
    name="writer",
    model="claude-3-haiku",
    temperature=0.3
)

# Planning subagent - for strategy and planning
planner = create_planning_subagent(
    name="planner",
    model="gpt-4o",
    max_turns=15
)

# Add all subagents to your main agent
for subagent in [researcher, coder, analyst, writer, planner]:
    main_agent.add_tool(subagent)
```

### Advanced Configuration with Parent Inheritance

Subagents can automatically inherit configuration from their parent agent:

```python
from tinyagent.tools.subagent import SubagentConfig, create_subagent_tool

# Create main agent with callbacks and configuration
main_agent = TinyAgent(
    model="gpt-4o-mini",
    api_key="your-key",
    log_manager=my_log_manager,
    session_id="main-session"
)

# Create configuration that inherits from parent
config = SubagentConfig.from_parent_agent(
    parent_agent=main_agent,  # Inherits API keys, logging, session info
    model="claude-3-sonnet",  # Override specific parameters
    max_turns=20,
    enable_python_tool=True,
    timeout=300,              # 5 minute timeout
    working_directory="/tmp/subagent"
)

# Create custom subagent with inherited configuration
specialized_tool = create_subagent_tool(
    name="specialist", 
    config=config,
    description="A specialized agent for complex analysis tasks"
)
main_agent.add_tool(specialized_tool)
```

### Custom Agent Factories

For maximum flexibility, use custom agent factories to create any type of agent:

```python
from tinyagent.tools.subagent import SubagentConfig, create_subagent_tool
from tinyagent import TinyCodeAgent

def my_custom_factory(**kwargs):
    """Custom factory for creating specialized agents."""
    return TinyCodeAgent(
        provider="modal",  # Use Modal.com for execution
        provider_config={
            "image": "python:3.11-slim",
            "timeout": 180,
            "cpu_count": 2
        },
        tools=[custom_tool_1, custom_tool_2],  # Add custom tools
        **kwargs
    )

# Create subagent with custom factory
config = SubagentConfig(
    model="gpt-4.1-mini",
    max_turns=15,
    timeout=600
)

custom_subagent = create_subagent_tool(
    name="custom_executor",
    config=config,
    agent_factory=my_custom_factory,
    description="Custom subagent with Modal.com execution"
)

main_agent.add_tool(custom_subagent)
```

### Key Benefits of Subagents

- **🔄 Parallel Processing**: Execute multiple tasks concurrently with complete isolation
- **🧠 Specialized Intelligence**: Domain-specific agents optimized for particular tasks
- **🛡️ Resource Safety**: Automatic cleanup prevents memory leaks and resource exhaustion  
- **🔗 Seamless Integration**: Inherits parent configuration (API keys, callbacks, logging)
- **🎯 Context Isolation**: Independent conversation history per subagent
- **⚙️ Extensible**: Custom agent factories for any agent implementation
- **📊 Execution Tracking**: Complete metadata and execution logs
- **🏗️ Production Ready**: Timeout management, error handling, automatic cleanup

### Subagent vs Regular Tools

| Feature | Regular Tools | Subagents |
|---------|---------------|-----------|
| **Context** | Share parent's context | Independent context |
| **Conversation** | Single shared history | Per-subagent history |
| **Resource Management** | Manual cleanup | Automatic cleanup |
| **Parallel Execution** | Limited | Full support |
| **Specialization** | Generic | Domain-optimized |
| **Timeout Handling** | Basic | Advanced with cleanup |
| **Configuration** | Static | Dynamic with inheritance |

## How the TinyAgent Hook System Works

TinyAgent is designed to be **extensible** via a simple, event-driven hook (callback) system. This allows you to add custom logic, logging, UI, memory, or any other behavior at key points in the agent's lifecycle.

### How Hooks Work

- **Hooks** are just callables (functions or classes with `__call__`) that receive events from the agent.
- You register hooks using `agent.add_callback(hook)`.
- Hooks are called with:  
  `event_name, agent, **kwargs`
- Events include:  
  - `"agent_start"`: Agent is starting a new run
  - `"message_add"`: A new message is added to the conversation
  - `"llm_start"`: LLM is about to be called
  - `"llm_end"`: LLM call finished
  - `"agent_end"`: Agent is done (final result)
  - (MCPClient also emits `"tool_start"` and `"tool_end"` for tool calls)

Hooks can be **async** or regular functions. If a hook is a class with an async `__call__`, it will be awaited.

#### Example: Adding a Custom Hook

```python
def my_logger_hook(event_name, agent, **kwargs):
    print(f"[{event_name}] {kwargs}")

agent.add_callback(my_logger_hook)
```

#### Example: Async Hook

```python
async def my_async_hook(event_name, agent, **kwargs):
    if event_name == "agent_end":
        print("Agent finished with result:", kwargs.get("result"))

agent.add_callback(my_async_hook)
```

#### Example: Class-based Hook

```python
class MyHook:
    async def __call__(self, event_name, agent, **kwargs):
        if event_name == "llm_start":
            print("LLM is starting...")

agent.add_callback(MyHook())
```

### How to Extend the Hook System

- **Create your own hook**: Write a function or class as above.
- **Register it**: Use `agent.add_callback(your_hook)`.
- **Listen for events**: Check `event_name` and use `**kwargs` for event data.
- **See examples**: Each official hook (see below) includes a `run_example()` in its file.

### 🚨 Important: Hook Interface Guidelines

#### **New Hook Interface (Recommended)**

When creating hooks that need to modify LLM messages, use the new interface that supports both legacy and modern patterns:

```python
class MyHook:
    async def __call__(self, event_name: str, agent, *args, **kwargs):
        """
        Hook that works with both new and legacy interfaces.
        
        Args:
            event_name: The event name
            agent: The TinyAgent instance
            *args: May contain kwargs_dict for new interface
            **kwargs: Legacy interface or fallback
        """
        # Handle both interfaces for maximum compatibility
        if args and isinstance(args[0], dict):
            # New interface: kwargs_dict passed as positional argument
            event_kwargs = args[0]
        else:
            # Legacy interface: use **kwargs
            event_kwargs = kwargs
        
        if event_name == "llm_start":
            # ✅ CORRECT: Modify event_kwargs["messages"] (what goes to LLM)
            messages = event_kwargs.get("messages", [])
            
            # Example: Add cache control, clean up fields, etc.
            for message in messages:
                if isinstance(message, dict) and "created_at" in message:
                    del message["created_at"]  # Remove unsupported fields
```

#### **Legacy Hook Interface (Still Supported)**

```python
async def my_legacy_hook(event_name, agent, **kwargs):
    if event_name == "llm_start":
        # ⚠️  LIMITATION: Cannot modify messages sent to LLM
        # This interface is read-only for message modification
        messages = kwargs.get("messages", [])
        print(f"LLM will be called with {len(messages)} messages")
```

#### ❌ **DON'T: Modify Conversation History**
```python
async def bad_hook(event_name, agent, *args, **kwargs):
    if event_name == "llm_start":
        # ❌ WRONG: Don't modify agent.messages (conversation history)
        agent.messages = modified_messages  # This corrupts conversation history!
```

#### 🏗️ **Architecture Explanation**
- **`agent.messages`** = Pristine conversation history (read-only for hooks)
- **`event_kwargs["messages"]`** = Copy of messages sent to LLM this call (modifiable by new interface hooks)
- **Protection**: TinyAgent automatically protects `agent.messages` from hook corruption
- **Chain-friendly**: Multiple hooks can safely modify `event_kwargs["messages"]` in sequence
- **Backward Compatible**: Legacy hooks continue to work for read-only operations

#### 📝 **Use Cases for Message Modification**
- **Prompt Caching**: Add cache control headers for supported models (see `anthropic_prompt_cache`)
- **Field Cleanup**: Remove unsupported fields like `created_at` for certain providers (see `MessageCleanupHook`)
- **Content Preprocessing**: Transform message content before sending to LLM
- **Token Optimization**: Compress or format messages for token efficiency

#### 🔧 **Built-in Hooks Using New Interface**
All built-in hooks have been updated to use the new interface:
- ✅ `MessageCleanupHook`: Removes `created_at` fields from LLM messages
- ✅ `AnthropicPromptCacheCallback`: Adds cache control to large messages
- ✅ `TokenTracker`: Tracks token usage and costs
- ✅ `RichUICallback`: Rich terminal UI
- ✅ `GradioCallback`: Web-based chat interface
- ✅ `JupyterNotebookCallback`: Jupyter notebook integration

---

## 🚀 Anthropic Prompt Caching (New!)

TinyAgent now includes Anthropic prompt caching that automatically adds cache control to substantial messages for Claude models, helping reduce API costs.

### Quick Start

Enable caching with just one line:

```python
from tinyagent import TinyAgent
from tinyagent.hooks import anthropic_prompt_cache

agent = TinyAgent(model="claude-3-5-sonnet-20241022")

# Add Anthropic prompt caching
cache_callback = anthropic_prompt_cache()
agent.add_callback(cache_callback)

# Use normally - caching happens automatically for large messages
response = await agent.run("Long prompt here...")
```

### How It Works

- **Automatic Detection**: Only works with Claude-3 and Claude-4 models that support prompt caching
- **Smart Triggering**: Adds cache control only to messages over ~1000 tokens 
- **Simple Integration**: Uses TinyAgent's native callback system
- **No Configuration**: Works out of the box with sensible defaults

### Supported Models

- **Claude-3 models**: claude-3-5-sonnet, claude-3-5-haiku, claude-3-haiku, claude-3-sonnet, claude-3-opus
- **Claude-4 models**: claude-4-*, claude-4o-*, and any future Claude-4 variants

### Benefits

- **Cost Reduction**: Automatic caching for substantial messages
- **Zero Configuration**: Just add the callback and it works
- **Model-Aware**: Only activates for supported Claude models
- **Lightweight**: Minimal overhead and complexity

---

## List of Available Hooks & Tools

### Core Hooks
You can import and use these hooks from `tinyagent.hooks`:

| Hook Name                | Description                                      | Example Import                                  |
|--------------------------|--------------------------------------------------|-------------------------------------------------|
| `anthropic_prompt_cache` | Prompt caching for Claude-3/Claude-4 models     | `from tinyagent.hooks import anthropic_prompt_cache` |
| `MessageCleanupHook`     | Removes unsupported fields from LLM messages    | `from tinyagent.hooks.message_cleanup import MessageCleanupHook` |
| `TokenTracker`           | Comprehensive token usage and cost tracking     | `from tinyagent.hooks.token_tracker import TokenTracker` |
| `LoggingManager`         | Granular logging control for all modules         | `from tinyagent.hooks.logging_manager import LoggingManager` |
| `RichUICallback`         | Rich terminal UI (with [rich](https://github.com/Textualize/rich)) | `from tinyagent.hooks.rich_ui_callback import RichUICallback` |
| `GradioCallback` | Interactive browser-based chat UI: file uploads, live thinking, tool calls, token stats | `from tinyagent.hooks.gradio_callback import GradioCallback`         |
| `JupyterNotebookCallback` | Interactive Jupyter notebook integration        | `from tinyagent.hooks.jupyter_notebook_callback import JupyterNotebookCallback` |

### File Tools 🗂️ 
Sandboxed file operations from `tinyagent.code_agent.tools.file_tools`:

| Tool Function  | Description                                      | Example Import                                  |
|----------------|--------------------------------------------------|-------------------------------------------------|
| `read_file`    | Read text file content with line numbers and pagination | `from tinyagent.code_agent.tools.file_tools import read_file` |
| `write_file`   | Write content to files with directory creation support | `from tinyagent.code_agent.tools.file_tools import write_file` |
| `update_file`  | Safe file updates using exact string replacement | `from tinyagent.code_agent.tools.file_tools import update_file` |
| `glob_tool`    | Fast pattern matching for finding files         | `from tinyagent.code_agent.tools.file_tools import glob_tool` |
| `grep_tool`    | Content search with regex support (ripgrep-like) | `from tinyagent.code_agent.tools.file_tools import grep_tool` |

### Task Management 📋
Built-in todo system from `tinyagent.tools.todo_write`:

| Tool Function         | Description                                      | Example Import                                  |
|-----------------------|--------------------------------------------------|-------------------------------------------------|
| `todo_write`          | Create and manage structured task lists         | `from tinyagent.tools.todo_write import todo_write` |
| `enable_todo_write_tool` | Enable/disable TodoWrite tool for an agent   | `from tinyagent.tools.todo_write import enable_todo_write_tool` |
| `get_current_todos`   | Get current todo list programmatically          | `from tinyagent.tools.todo_write import get_current_todos` |
| `get_todo_summary`    | Get summary statistics of todo list             | `from tinyagent.tools.todo_write import get_todo_summary` |

### Subagent Tools 🚀
Revolutionary parallel task execution system from `tinyagent.tools.subagent`:

| Tool Function            | Description                                      | Example Import                                  |
|--------------------------|--------------------------------------------------|-------------------------------------------------|
| `create_general_subagent` | General-purpose subagent with Python/shell execution | `from tinyagent.tools.subagent import create_general_subagent` |
| `create_research_subagent` | Research-optimized subagent for information gathering | `from tinyagent.tools.subagent import create_research_subagent` |
| `create_coding_subagent`  | Coding-specialized subagent with execution capabilities | `from tinyagent.tools.subagent import create_coding_subagent` |
| `create_analysis_subagent` | Data analysis subagent with Python tools        | `from tinyagent.tools.subagent import create_analysis_subagent` |
| `create_writing_subagent` | Content creation and writing subagent           | `from tinyagent.tools.subagent import create_writing_subagent` |
| `create_planning_subagent` | Strategic planning and project management subagent | `from tinyagent.tools.subagent import create_planning_subagent` |
| `create_subagent_tool`    | Advanced subagent creation with custom configuration | `from tinyagent.tools.subagent import create_subagent_tool` |
| `SubagentConfig`         | Configuration class with parent inheritance      | `from tinyagent.tools.subagent import SubagentConfig` |

To see more details and usage, check the docstrings and `run_example()` in each hook file.

## Using the GradioCallback Hook

The `GradioCallback` hook lets you spin up a full-featured web chat interface for your agent in just a few lines. You get:

Features:
- **Browser-based chat** with streaming updates  
- **File uploads** (\*.pdf, \*.docx, \*.txt) that the agent can reference  
- **Live "thinking" view** so you see intermediate thoughts  
- **Collapsible tool-call sections** showing inputs & outputs  
- **Real-time token usage** (prompt, completion, total)  
- **Toggleable display options** for thinking & tool calls  
- **Non-blocking launch** for asyncio apps (`prevent_thread_lock=True`)

```python
import asyncio
from tinyagent import TinyAgent
from tinyagent.hooks.gradio_callback import GradioCallback
async def main():
    # 1. Initialize your agent
    agent = TinyAgent(model="gpt-4.1-mini", api_key="YOUR_API_KEY")
    # 2. (Optional) Add tools or connect to MCP servers
    # await agent.connect_to_server("npx", ["-y","@openbnb/mcp-server-airbnb","--ignore-robots-txt"])
    # 3. Instantiate the Gradio UI callback
    gradio_ui = GradioCallback(
    file_upload_folder="uploads/",
    show_thinking=True,
    show_tool_calls=True
    )
    # 4. Register the callback with the agent
    agent.add_callback(gradio_ui)
    # 5. Launch the web interface (non-blocking)
    gradio_ui.launch(
    agent,
    title="TinyAgent Chat",
    description="Ask me to plan a trip or fetch data!",
    share=False,
    prevent_thread_lock=True
    )
if __name__ == "__main__":
    asyncio.run(main())
```
---

## Build your own TinyAgent

You can chat with TinyAgent and build your own TinyAgent for your use case.

[![AskDev.AI | Chat with TinyAgent](https://img.shields.io/badge/AskDev.AI-Chat_with_TinyAgent-blue?style=flat-square)](https://askdev.ai/github/askbudi/tinyagent)

---

## Contributing Hooks

- Place new hooks in the `tinyagent/hooks/` directory.
- **Use the new hook interface** for maximum compatibility (see hook guidelines above).
- Add an example usage as `async def run_example()` in the same file.
- Use `"gpt-4.1-mini"` as the default model in examples.
- Include proper error handling and compatibility for both new and legacy interfaces.
- Test your hook with the compatibility test framework in `test_all_hooks_compatibility.py`.

---

## License

MIT License. See [LICENSE](LICENSE).
