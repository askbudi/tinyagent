# TinyAgent
🛠️ **Build Your Own AI Coding Assistant** - Break free from vendor lock-in and create powerful agents with *any* AI model you choose

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


## 🚀 The Vision: Your AI, Your Choice, Your Rules

Tired of being locked into specific AI providers? Want the power of advanced coding assistants without the constraints? TinyAgent gives you **complete freedom** to build intelligent agents that work with *any* AI model - from OpenAI and Anthropic to your own local Ollama models.

**This isn't just another AI wrapper.** It's your gateway to building the coding assistant of your dreams:

### 🎯 Why TinyAgent Changes Everything

- **🔓 Model Freedom**: Switch between GPT-5, Claude-4, Llama, or any 100+ models instantly
- **🏠 Local Privacy**: Run everything locally with Ollama - your code never leaves your machine  
- **🛡️ Production Security**: Enterprise-grade sandboxing across macOS, Linux, and Windows
- **⚡ Parallel Intelligence**: Multiple specialized AI agents working together on complex tasks
- **🔧 Complete Control**: Extend, customize, and hook into every aspect of agent behavior

**Three Revolutionary Components:**
- **TinyAgent**: Your universal AI interface - one API, infinite models
- **TinyCodeAgent**: Secure code execution with cross-platform sandboxing
- **Subagent Swarm**: Parallel specialized workers that collaborate intelligently

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

async def create_enhanced_tinyagent():
    """Create a TinyAgent with all new tools and capabilities."""
    
    # Initialize TinyAgent (TodoWrite is enabled by default)
    agent = TinyAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        enable_todo_write=True  # Enable TodoWrite tool (True by default)
    )
    
    # Add a general-purpose subagent for parallel tasks
    helper_subagent = create_general_subagent(
        name="helper",
        model="gpt-5-mini",
        max_turns=20,
        enable_python=True,
        enable_shell=True
    )
    agent.add_tool(helper_subagent)
    
    # Check available tools
    available_tools = list(agent.custom_tool_handlers.keys())
    print(f"Available tools: {available_tools}")  # ['TodoWrite', 'helper']
    
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
        model="gpt-5-mini",
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
        # REQUIRED: Local execution for Seatbelt provider
        local_execution=True,
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
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        provider="modal",
        provider_config={
            "pip_packages": ["requests", "pandas", "matplotlib", "seaborn"]
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
        # Check available tools
        available_tools = list(agent.custom_tool_handlers.keys())
        print(f"Available tools: {available_tools}")
        
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
        model="gpt-4o-mini",
        local_execution=True,  # Auto-selects best provider
        enable_file_tools=True
    )
    
    try:
        # Check available tools
        available_tools = list(agent.custom_tool_handlers.keys())
        print(f"Available file tools: {available_tools}")
        
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
        model="gpt-5-mini",
        enable_todo_write=True  # Enabled by default
    )
    
    try:
        # Check that TodoWrite tool is available
        available_tools = list(agent.custom_tool_handlers.keys())
        print(f"Available tools: {available_tools}")  # Should include 'TodoWrite'
        
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
        model="gpt-5-mini", 
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

## 📚 Complete Examples Collection

<details>
<summary>Click to expand complete working examples for all TinyAgent features</summary>

### 1. Basic TinyAgent Example

```python
import asyncio
import os
from tinyagent import TinyAgent

async def example_1_basic_tinyagent():
    """✅  Basic TinyAgent example."""
    print("Example 1: Basic TinyAgent")
    
    agent = TinyAgent(
        model="gpt-5-mini",
        api_key=os.environ.get("OPENAI_API_KEY"),
        system_prompt="You are a helpful assistant."
    )
    
    try:
        # The TodoWrite tool is automatically enabled by default
        available_tools = list(agent.custom_tool_handlers.keys())
        print(f"Available tools: {available_tools}")
        
        # For actual use, you would call:
        # result = await agent.run("Your task here")
        # print(result)
        
        print("✅ Success: Basic TinyAgent initialized correctly")
        
    finally:
        await agent.close()

asyncio.run(example_1_basic_tinyagent())
```

### 2. Enhanced TinyAgent with Subagents

```python
import asyncio
import os
from tinyagent import TinyAgent
from tinyagent.tools.subagent import create_general_subagent, create_coding_subagent

async def example_2_enhanced_tinyagent():
    """✅  Enhanced TinyAgent with subagents."""
    print("Example 2: Enhanced TinyAgent with Subagents")
    
    # Create agent with TodoWrite enabled by default
    agent = TinyAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        enable_todo_write=True  # This is True by default
    )
    
    # Add a general-purpose subagent
    helper_subagent = create_general_subagent(
        name="helper",
        model="gpt-5-mini", 
        max_turns=20,
        enable_python=True,
        enable_shell=True
    )
    agent.add_tool(helper_subagent)
    
    # Add a coding subagent
    coder = create_coding_subagent(
        name="coder",
        model="gpt-5-mini",
        max_turns=25
    )
    agent.add_tool(coder)
    
    try:
        # Check available tools - they are in custom_tool_handlers
        available_tools = list(agent.custom_tool_handlers.keys())
        print(f"Available tools: {available_tools}")
        
        # For MCP server connections (if needed):
        # await agent.connect_to_server("npx", ["@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
        
        print("✅ Success: Enhanced TinyAgent with subagents")
        
    finally:
        await agent.close()

asyncio.run(example_2_enhanced_tinyagent())
```

### 3. Basic TinyCodeAgent Example

```python
import asyncio
import os
from tinyagent import TinyCodeAgent

async def example_3_basic_tinycodeagent():
    """✅  Basic TinyCodeAgent example."""
    print("Example 3: Basic TinyCodeAgent")
    
    agent = TinyCodeAgent(
        model="gpt-5-mini",
        api_key=os.environ.get("OPENAI_API_KEY"),
        provider="seatbelt",
        enable_python_tool=True,
        enable_shell_tool=True,
        enable_file_tools=True,
        enable_todo_write=True,
        local_execution=True  # REQUIRED for Seatbelt provider
    )
    
    try:
        # Check available tools - they are in custom_tool_handlers
        available_tools = list(agent.custom_tool_handlers.keys())
        print(f"Available tools: {available_tools}")
        
        # For actual use:
        # result = await agent.run("Write a Python function to calculate factorial")
        # print(result)
        
        print("✅ Success: TinyCodeAgent initialized correctly")
        
    finally:
        await agent.close()

asyncio.run(example_3_basic_tinycodeagent())
```

### 4. Enhanced TinyCodeAgent with Full Configuration

```python
import asyncio
import os
from tinyagent import TinyCodeAgent

async def example_4_enhanced_tinycodeagent():
    """✅  Enhanced TinyCodeAgent with all features."""
    print("Example 4: Enhanced TinyCodeAgent")
    
    agent = TinyCodeAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        provider="seatbelt",
        provider_config={
            "python_env_path": "/usr/bin/python3",
            "additional_read_dirs": ["/tmp"],
            "additional_write_dirs": ["/tmp"],
            "environment_variables": {"TEST_VAR": "test_value"}
        },
        enable_python_tool=True,
        enable_shell_tool=True, 
        enable_file_tools=True,
        enable_todo_write=True,
        local_execution=True,  # REQUIRED for Seatbelt
        default_workdir="/tmp",
        auto_git_checkpoint=False,  # Can be enabled if needed
        ui=None  # Can use "rich" for enhanced UI
    )
    
    try:
        available_tools = list(agent.custom_tool_handlers.keys())
        print(f"Available tools: {available_tools}")
        
        print("✅ Success: Enhanced TinyCodeAgent with all features")
        
    finally:
        await agent.close()

asyncio.run(example_4_enhanced_tinycodeagent())
```

### 5. Modal Provider Example

```python
import asyncio
import os
from tinyagent import TinyCodeAgent

async def example_5_modal_provider():
    """✅  TinyCodeAgent with Modal provider."""
    print("Example 5: TinyCodeAgent with Modal Provider")
    
    agent = TinyCodeAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        provider="modal",
        provider_config={
            "pip_packages": ["requests", "pandas"],
        },
        enable_python_tool=True,
        enable_shell_tool=True,
        enable_file_tools=True,
        enable_todo_write=True,
        local_execution=False  # Cloud execution for Modal
    )
    
    try:
        available_tools = list(agent.custom_tool_handlers.keys())
        print(f"Available tools: {available_tools}")
        
        print("✅ Success: Modal provider configured")
        
    finally:
        await agent.close()

asyncio.run(example_5_modal_provider())
```

### 6. Storage Persistence Example

```python
import asyncio
import os
import tempfile
from tinyagent import TinyAgent
from tinyagent.storage.sqlite_storage import SqliteStorage

async def example_6_storage_persistence():
    """✅  Storage persistence example."""
    print("Example 6: Storage Persistence")
    
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db.close()
    
    try:
        storage = SqliteStorage(db_path=temp_db.name)
        
        # Create agent with storage
        agent = TinyAgent(
            model="gpt-5-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
            session_id="test-session",
            user_id="test-user",
            storage=storage
        )
        
        # Add a message
        agent.messages.append({
            "role": "user", 
            "content": "Test message for persistence"
        })
        
        # Save the session
        await agent.save_agent()
        original_count = len(agent.messages)
        print(f"Saved {original_count} messages")
        
        await agent.close()
        
        # Create new agent with same session to test loading
        agent2 = TinyAgent(
            model="gpt-5-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
            session_id="test-session",
            user_id="test-user", 
            storage=storage
        )
        
        # Load the session
        await agent2.init_async()
        loaded_count = len(agent2.messages)
        
        print(f"Loaded {loaded_count} messages")
        
        if loaded_count == original_count:
            print("✅ Success: Session persistence working")
        else:
            print("❌ Failed: Session not properly loaded")
            
        await agent2.close()
        
    finally:
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)

asyncio.run(example_6_storage_persistence())
```

### 7. Hook System Example

```python
import asyncio
import os
from tinyagent import TinyAgent
from tinyagent.hooks.token_tracker import TokenTracker
from tinyagent.hooks import anthropic_prompt_cache

async def example_7_hook_system():
    """✅  Hook system example."""
    print("Example 7: Hook System")
    
    agent = TinyAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Add various hooks
    token_tracker = TokenTracker(name="test_tracker")
    agent.add_callback(token_tracker)
    
    # Add Anthropic prompt caching for Claude models
    # cache_callback = anthropic_prompt_cache()
    # agent.add_callback(cache_callback)
    
    # Custom hook
    def custom_hook(event_name, agent, **kwargs):
        if event_name == "agent_start":
            print(f"   Custom hook: Agent starting")
    
    agent.add_callback(custom_hook)
    
    try:
        print(f"Callbacks added: {len(agent.callbacks)}")
        print("✅ Success: Hook system working")
        
    finally:
        await agent.close()

asyncio.run(example_7_hook_system())
```

### 8. Ollama Models Example

```python
import asyncio
import os
from tinyagent import TinyAgent, TinyCodeAgent

async def example_8_ollama_models():
    """✅  Ollama models example."""
    print("Example 8: Ollama Models")
    
    # TinyAgent with Ollama
    agent = TinyAgent(
        model="ollama/llama2",
        api_key=None,  # No API key needed for local models
        temperature=0.7
    )
    
    try:
        print(f"Model: {agent.model}")
        print(f"API Key: {agent.api_key}")
        print("✅ Success: Ollama model configured")
        
    finally:
        await agent.close()
    
    # TinyCodeAgent with Ollama
    code_agent = TinyCodeAgent(
        model="ollama/codellama",
        api_key=None,
        provider="seatbelt",
        local_execution=True,
        enable_python_tool=True,
        enable_shell_tool=True,
        enable_file_tools=True
    )
    
    try:
        available_tools = list(code_agent.custom_tool_handlers.keys())
        print(f"CodeAgent tools: {available_tools}")
        print("✅ Success: Ollama CodeAgent configured")
        
    finally:
        await code_agent.close()

asyncio.run(example_8_ollama_models())
```

### 9. File Tools Usage Example

```python
import asyncio
import os
import tempfile
import shutil
from tinyagent import TinyCodeAgent

async def example_9_file_tools_usage():
    """✅  File tools usage example."""
    print("Example 9: File Tools Usage")
    
    temp_dir = tempfile.mkdtemp(prefix="tinyagent_test_")
    
    try:
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
            provider="seatbelt",
            enable_file_tools=True,
            provider_config={
                "additional_read_dirs": [temp_dir],
                "additional_write_dirs": [temp_dir]
            },
            local_execution=True
        )
        
        # Check file tools are available
        file_tools = ['read_file', 'write_file', 'update_file', 'glob', 'grep']
        available_file_tools = [tool for tool in file_tools 
                              if tool in agent.custom_tool_handlers]
        
        print(f"Available file tools: {available_file_tools}")
        
        if len(available_file_tools) == len(file_tools):
            print("✅ Success: All file tools available")
        else:
            print("❌ Some file tools missing")
        
        await agent.close()
        
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

asyncio.run(example_9_file_tools_usage())
```

### 10. Git Checkpoints Example

```python
import asyncio
import os
from tinyagent import TinyCodeAgent

async def example_10_git_checkpoints():
    """✅  Git checkpoints example."""
    print("Example 10: Git Checkpoints")
    
    agent = TinyCodeAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        auto_git_checkpoint=True  # Enable auto git checkpoints
    )
    
    try:
        # Test checkpoint controls
        is_enabled = agent.get_auto_git_checkpoint_status()
        print(f"Git checkpoints enabled: {is_enabled}")
        
        # Test toggle
        agent.enable_auto_git_checkpoint(False)
        is_disabled = agent.get_auto_git_checkpoint_status()
        print(f"Git checkpoints after disable: {is_disabled}")
        
        agent.enable_auto_git_checkpoint(True)
        is_reenabled = agent.get_auto_git_checkpoint_status()
        print(f"Git checkpoints after re-enable: {is_reenabled}")
        
        print("✅ Success: Git checkpoint controls working")
        
    finally:
        await agent.close()

asyncio.run(example_10_git_checkpoints())
```

### Key Corrections Summary

**Important Notes from Testing:**

1. **Tools Access**: Tools are stored in `agent.custom_tool_handlers` (dict), not `agent.tools`
2. **Seatbelt Provider**: TinyCodeAgent with Seatbelt provider REQUIRES `local_execution=True`
3. **TodoWrite Tool**: Automatically added when `enable_todo_write=True` (default)
4. **Storage Loading**: Use `agent.init_async()` to load existing sessions
5. **Messages**: Access conversation via `agent.messages` (list)
6. **File Tools**: Added as custom tools, not in mcp_client.tools
7. **Subagents**: Added as custom tools with their names as keys
8. **Modal Provider**: Works with `local_execution=False` (cloud execution)
9. **Hooks**: Added to `agent.callbacks` list
10. **Git Checkpoints**: Have dedicated control methods

</details>

## Using Local Models with Ollama

TinyAgent supports local models through Ollama via LiteLLM integration. This allows you to run models locally without requiring API keys or cloud services.

### Prerequisites

1. Install Ollama from [ollama.ai](https://ollama.ai)
2. Pull the model you want to use:
   ```bash
   ollama pull qwen2.5-coder:7b
   ollama pull codellama
   ollama pull gpt-oss:20b
   # or any other model from Ollama library
   ```

### Basic Usage with Ollama

```python
import asyncio
from tinyagent import TinyAgent

async def main():
    # Initialize TinyAgent with Ollama model
    # Format: "ollama/<model-name>"
    agent = TinyAgent(
        model="ollama/qwen2.5-coder:7b",  # or "ollama/codellama", "ollama/mixtral", etc.
        api_key=None,  # No API key needed for local models
        temperature=0.7,
        system_prompt="You are a helpful AI assistant running locally."
    )
    
    try:
        # Connect to MCP servers if needed
        await agent.connect_to_server("npx", ["@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
        
        # Run the agent
        result = await agent.run("What can you help me with today?")
        print("Response:", result)
    finally:
        await agent.close()

asyncio.run(main())
```

### TinyCodeAgent with Ollama

```python
import asyncio
from tinyagent import TinyCodeAgent

async def main():
    # Use code-optimized models for better results
    agent = TinyCodeAgent(
        model="ollama/qwen2.5-coder:7b",  # qwen2.5-coder:7b is optimized for code tasks
        api_key=None,
        provider="seatbelt",  # or "modal" for cloud execution
        enable_python_tool=True,
        enable_shell_tool=True,
        enable_file_tools=True
    )
    
    try:
        result = await agent.run("""
        Write a Python function to calculate fibonacci numbers
        and test it with the first 10 numbers.
        """)
        print("Result:", result)
    finally:
        await agent.close()

asyncio.run(main())
```

### Advanced Ollama Configuration

```python
from tinyagent import TinyAgent

# Custom Ollama endpoint (if not using default)
agent = TinyAgent(
    model="ollama/llama2",
    api_key=None,
    model_kwargs={
        "api_base": "http://localhost:11434",  # Custom Ollama server
        "num_predict": 2048,  # Max tokens to generate
        "top_k": 40,
        "top_p": 0.9,
        "repeat_penalty": 1.1
    }
)

# Using with hooks and callbacks
from tinyagent.hooks.rich_ui_callback import RichUICallback

agent = TinyAgent(
    model="ollama/mixtral",
    api_key=None,
    temperature=0.5
)

# Add rich UI for better visualization
ui = RichUICallback()
agent.add_callback(ui)
```

### Recommended Ollama Models

| Model | Best For | Command |
|-------|----------|---------|
| `llama2` | General purpose tasks | `ollama pull llama2` |
| `codellama` | Code generation and analysis | `ollama pull codellama` |
| `mixtral` | Advanced reasoning, larger context | `ollama pull mixtral` |
| `mistral` | Fast, efficient general tasks | `ollama pull mistral` |
| `phi` | Lightweight, fast responses | `ollama pull phi` |
| `deepseek-coder` | Specialized code tasks | `ollama pull deepseek-coder` |

### Performance Tips

1. **Model Selection**: Choose models based on your task:
   - Use `codellama` or `deepseek-coder` for code-heavy tasks
   - Use `mixtral` for complex reasoning
   - Use `phi` or `mistral` for faster responses

2. **Resource Management**: Local models use your machine's resources:
   ```python
   # Adjust temperature for more deterministic outputs
   agent = TinyAgent(
       model="ollama/codellama",
       temperature=0.1,  # Lower = more deterministic
       model_kwargs={
           "num_thread": 8,  # Adjust based on your CPU
           "num_gpu": 1,     # If you have GPU support
       }
   )
   ```

3. **Context Length**: Be mindful of context limits:
   ```python
   # Configure for longer contexts if needed
   agent = TinyAgent(
       model="ollama/mixtral",
       model_kwargs={
           "num_ctx": 4096,  # Context window size
       }
   )
   ```

## Custom Instructions System 📝

TinyAgent supports a flexible custom instruction system that allows you to append project-specific, domain-specific, or context-specific instructions to your agent's system prompt. This feature is perfect for customizing agent behavior, adding specialized knowledge, or maintaining consistent behavior across your project.

### Key Features

- **🎯 Flexible Input**: Support for both string input and file paths
- **📁 Automatic AGENTS.md Loading**: Auto-detects project instructions
- **🔧 Enable/Disable Control**: Runtime configuration with proper logging
- **🏷️ Placeholder Support**: Smart insertion at specific locations in system prompts
- **🎛️ Configurable Paths**: Custom filenames and locations
- **🔗 Subagent Integration**: Control inheritance for specialized workers

### Quick Start

#### Basic Usage with String Instructions

```python
import asyncio
from tinyagent import TinyAgent

async def main():
    # Add custom instructions directly as a string
    custom_instructions = """
    You are working on a Python web application project.
    Always consider:
    - Security best practices
    - Performance implications
    - Code maintainability
    - Follow PEP 8 style guidelines
    """
    
    agent = TinyAgent(
        model="gpt-5-mini",
        api_key="your-api-key",
        custom_instruction=custom_instructions,
        enable_custom_instruction=True
    )
    
    result = await agent.run("Help me refactor this Django view function")
    print(result)

asyncio.run(main())
```

#### Automatic AGENTS.md Loading

Create an `AGENTS.md` file in your project directory:

```markdown
# Project Instructions for AI Agents

You are assisting with the TinyAgent Python framework project.

## Context
- This is an AI agent framework focused on modularity and extensibility
- Code should follow Python best practices and be well-documented
- Always consider backward compatibility when making changes

## Coding Standards
- Use type hints consistently
- Write comprehensive docstrings
- Add appropriate error handling
- Follow the existing project structure

## Testing Requirements
- Write unit tests for new functionality
- Use pytest for testing
- Maintain test coverage above 80%
```

Then initialize your agent with automatic loading:

```python
from tinyagent import TinyAgent

# Will automatically load AGENTS.md if present in current directory
agent = TinyAgent(
    model="gpt-5-mini",
    api_key="your-api-key",
    enable_custom_instruction=True,  # Enable auto-loading (default: True)
    custom_instruction_file="AGENTS.md"  # Default filename
)
```

#### Custom File Locations

```python
from tinyagent import TinyCodeAgent

# Use custom instruction file from different location
agent = TinyCodeAgent(
    model="gpt-5-mini",
    provider="seatbelt",
    enable_custom_instruction=True,
    custom_instruction_file="config/my_agent_instructions.md",
    custom_instruction_directory="/path/to/project"
)
```

### Advanced Configuration

#### Custom Placeholder Support

If your system prompt contains the placeholder `<user_specified_instruction></user_specified_instruction>`, custom instructions will be inserted there. Otherwise, they're appended to the end.

```python
# Custom system prompt with placeholder
custom_prompt = """
You are a helpful AI assistant.

<user_specified_instruction></user_specified_instruction>

Always be concise and helpful.
"""

agent = TinyAgent(
    model="gpt-5-mini",
    system_prompt=custom_prompt,
    custom_instruction="Focus on Python development best practices.",
    enable_custom_instruction=True
)
```

#### Runtime Configuration

```python
from tinyagent import TinyAgent

agent = TinyAgent(
    model="gpt-5-mini",
    # Custom instruction configuration
    enable_custom_instruction=True,
    custom_instruction="Initial instructions here",
    custom_instruction_file="AGENTS.md",
    custom_instruction_directory="./config",
    custom_instruction_placeholder="<custom_guidance></custom_guidance>",
    custom_instruction_subagent_inheritance=True
)

# Update instructions at runtime
agent.set_custom_instruction("Updated project guidelines")

# Reload from file
agent.reload_custom_instruction()

# Disable/enable dynamically
agent.enable_custom_instruction(False)  # Disable
agent.enable_custom_instruction(True)   # Re-enable
```

### TinyCodeAgent Integration

TinyCodeAgent fully supports custom instructions with specialized integration:

```python
from tinyagent import TinyCodeAgent

# Project-specific coding instructions
coding_instructions = """
## Code Execution Guidelines
- Always validate input parameters
- Use secure coding practices
- Implement proper error handling
- Write self-documenting code with clear variable names

## Project Context
- Working with financial data - be extra careful with calculations
- All monetary values should use Decimal type
- Log all significant operations for audit trail
"""

agent = TinyCodeAgent(
    model="gpt-5-mini",
    provider="modal",
    custom_instruction=coding_instructions,
    enable_custom_instruction=True,
    enable_python_tool=True,
    enable_shell_tool=True
)
```

### Subagent Inheritance Control

Control whether subagents inherit custom instructions:

```python
from tinyagent import TinyAgent
from tinyagent.tools.subagent import create_general_subagent

# Main agent with project instructions
main_agent = TinyAgent(
    model="gpt-5-mini",
    custom_instruction="Main project guidelines",
    enable_custom_instruction=True,
    custom_instruction_subagent_inheritance=True  # Subagents will inherit
)

# Create subagent - will automatically inherit custom instructions
helper = create_general_subagent(
    name="helper",
    model="gpt-5-mini",
    max_turns=15
)
main_agent.add_tool(helper)

# For selective inheritance control
specific_agent = TinyAgent(
    model="gpt-5-mini",
    custom_instruction="Specialized guidelines for this agent only",
    custom_instruction_subagent_inheritance=False  # Don't pass to subagents
)
```

### File Format Support

Custom instruction files support multiple formats:

#### Markdown Format (Recommended)
```markdown
# Agent Instructions

## Project Context
Brief description of the project and its goals.

## Guidelines
- Specific behaviors and preferences
- Technical requirements
- Quality standards

## Examples
Code examples or usage patterns to follow.
```

#### Plain Text Format
```text
Project: E-commerce Platform Development

Guidelines:
- Follow REST API best practices
- Use proper HTTP status codes
- Implement comprehensive error handling
- Write OpenAPI documentation for all endpoints

Security Requirements:
- Always validate and sanitize input
- Implement proper authentication checks
- Use parameterized queries for database access
```

### Logging and Warnings

The custom instruction system provides comprehensive logging:

```python
import logging
from tinyagent import TinyAgent

# Enable debug logging to see custom instruction loading
logging.basicConfig(level=logging.DEBUG)

agent = TinyAgent(
    model="gpt-5-mini",
    enable_custom_instruction=True,
    custom_instruction_file="AGENTS.md"
)

# Log messages you'll see:
# INFO: Custom instruction loaded from AGENTS.md (1234 characters)
# WARNING: Custom instruction is enabled but AGENTS.md file not found
# INFO: Custom instruction disabled, ignoring AGENTS.md file
```

### Configuration Options Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `custom_instruction` | `str \| None` | `None` | Direct instruction string or file path |
| `enable_custom_instruction` | `bool` | `True` | Enable/disable custom instruction system |
| `custom_instruction_file` | `str` | `"AGENTS.md"` | Default filename to search for |
| `custom_instruction_directory` | `str` | `"."` | Directory to search for instruction files |
| `custom_instruction_placeholder` | `str` | `"<user_specified_instruction></user_specified_instruction>"` | Placeholder for instruction insertion |
| `custom_instruction_subagent_inheritance` | `bool` | `True` | Whether subagents inherit instructions |

### Best Practices

1. **📁 Use AGENTS.md**: Keep project instructions in a standard `AGENTS.md` file at your project root
2. **📝 Be Specific**: Write clear, actionable instructions rather than vague guidance
3. **🔄 Version Control**: Include instruction files in version control for team consistency
4. **🎯 Context Matters**: Tailor instructions to your specific use case and domain
5. **🧪 Test Changes**: Test how instruction changes affect agent behavior
6. **📊 Monitor Logs**: Use logging to verify instructions are loaded correctly

### Common Use Cases

- **🏢 Enterprise Compliance**: Add company-specific guidelines and policies
- **🔧 Development Standards**: Enforce coding standards and best practices
- **📚 Domain Knowledge**: Include specialized knowledge for specific fields
- **🎨 Style Guidelines**: Maintain consistent output formatting and tone
- **🔐 Security Requirements**: Emphasize security practices and requirements
- **📖 Documentation Standards**: Specify documentation formats and requirements

### Error Handling

The system gracefully handles various error conditions:

```python
# File not found - logs warning and continues
agent = TinyAgent(
    model="gpt-5-mini",
    enable_custom_instruction=True,
    custom_instruction_file="missing_file.md"
)
# WARNING: Custom instruction file not found: missing_file.md

# Invalid file path - falls back to string interpretation
agent = TinyAgent(
    model="gpt-5-mini", 
    custom_instruction="/invalid/path/instructions.md"
)
# INFO: Treating custom_instruction as direct string content

# Empty or malformed files - logs warning
# WARNING: Custom instruction file is empty or unreadable
```

The custom instruction system is designed to be robust and fail gracefully, ensuring your agents continue to work even when instruction files have issues.

## Session Persistence with Storage

TinyAgent supports persistent sessions across runs using various storage backends. This allows you to resume conversations, maintain conversation history, and preserve agent state between application restarts.

### Available Storage Systems

TinyAgent provides several storage backend options:

- **SQLite Storage** (`sqlite_storage.py`) - Local file-based database, great for development and single-user applications
- **PostgreSQL Storage** (`postgres_storage.py`) - Production-ready relational database for multi-user applications
- **Redis Storage** (`redis_storage.py`) - In-memory database for high-performance, cache-like storage
- **JSON File Storage** (`json_file_storage.py`) - Simple file-based storage for development and testing

### SQLite Storage Example

Here's a complete example using SQLite storage for session persistence:

```python
import asyncio
import os
from tinyagent import TinyAgent
from tinyagent.storage.sqlite_storage import SqliteStorage

async def persistent_agent_example():
    """Example showing how to use SQLite storage for session persistence."""
    
    # Initialize SQLite storage
    # This will create a local database file to store sessions
    storage = SqliteStorage(
        db_path="./agent_sessions.db",  # Local SQLite database file
        table_name="tny_agent_sessions"  # Custom table name (optional)
    )
    
    # Create agent with persistent storage
    # If session_id exists, it will resume the previous conversation
    agent = TinyAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        session_id="user-123-chat",  # Unique session identifier
        user_id="user-123",  # Optional user identifier
        storage=storage,  # Enable persistent storage
        temperature=1.0,
        metadata={
            "user_name": "Alice",
            "application": "customer-support",
            "version": "1.0"
        }
    )
    
    try:
        # First run - will create new session or resume existing one
        print("=== First Interaction ===")
        result1 = await agent.run("Hello! My name is Alice. What can you help me with?")
        print(f"Agent: {result1}")
        
        # Second run - state is automatically persisted
        print("\n=== Second Interaction ===")
        result2 = await agent.run("Do you remember my name from our previous conversation?")
        print(f"Agent: {result2}")
        
        # Check current conversation length
        print(f"\nConversation has {len(agent.messages)} messages")
        
        # You can also manually save at any point
        await agent.save_agent()
        print("Session manually saved!")
        
    finally:
        # Clean up resources
        await agent.close()

# Run the example
asyncio.run(persistent_agent_example())
```

### Resuming Sessions

You can resume a previous session by using the same `session_id`:

```python
import asyncio
from tinyagent import TinyAgent
from tinyagent.storage.sqlite_storage import SqliteStorage

async def resume_session_example():
    """Example showing how to resume a previous session."""
    
    storage = SqliteStorage(db_path="./agent_sessions.db")
    
    # Resume existing session
    agent = TinyAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        session_id="user-123-chat",  # Same session ID as before
        user_id="user-123",
        storage=storage
    )
    
    # Load the existing session
    await agent.init_async()
    
    try:
        # This will continue from where the previous conversation left off
        print(f"Resumed session with {len(agent.messages)} previous messages")
        
        result = await agent.run("Can you summarize our conversation so far?")
        print(f"Agent: {result}")
        
    finally:
        await agent.close()

asyncio.run(resume_session_example())
```

### Multiple User Sessions

Handle multiple users with separate sessions:

```python
import asyncio
from tinyagent import TinyAgent
from tinyagent.storage.sqlite_storage import SqliteStorage

async def multi_user_example():
    """Example showing multiple user sessions."""
    
    storage = SqliteStorage(db_path="./multi_user_sessions.db")
    
    # User 1 session
    agent1 = TinyAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        session_id="chat-session-1",
        user_id="user-alice",
        storage=storage,
        temperature=1.0,
        metadata={"user_name": "Alice", "role": "developer"}
    )
    
    # User 2 session  
    agent2 = TinyAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"), 
        session_id="chat-session-2",
        user_id="user-bob",
        storage=storage,
        temperature=1.0,
        metadata={"user_name": "Bob", "role": "manager"}
    )
    
    try:
        # Each user gets their own isolated conversation
        result1 = await agent1.run("Hi, I'm Alice and I'm working on a Python project.")
        result2 = await agent2.run("Hello, I'm Bob and I need help with project management.")
        
        print(f"Alice's agent: {result1}")
        print(f"Bob's agent: {result2}")
        
    finally:
        await agent1.close()
        await agent2.close()

asyncio.run(multi_user_example())
```

### Advanced Storage Configuration

```python
import asyncio
from tinyagent import TinyAgent
from tinyagent.storage.sqlite_storage import SqliteStorage
from tinyagent.hooks.rich_ui_callback import RichUICallback

async def advanced_storage_example():
    """Advanced example with custom storage configuration."""
    
    # Initialize storage with custom table name and path
    storage = SqliteStorage(
        db_path="./data/conversations/agent.db",  # Custom path (directories will be created)
        table_name="custom_sessions"  # Custom table name
    )
    
    # Create agent with comprehensive configuration
    agent = TinyAgent(
        model="gpt-5-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        session_id="advanced-session",
        user_id="power-user",
        storage=storage,
        
        # Additional configuration
        metadata={
            "application": "ai-assistant",
            "version": "2.0",
            "user_tier": "premium",
            "features": ["code_execution", "file_access"]
        },
        
        # Enable tool persistence (experimental)
        persist_tool_configs=True,
        
        # Add conversation summarization for long sessions
        summary_config={
            "model": "gpt-5-mini",
            "max_messages": 50,  # Summarize when over 50 messages
            "system_prompt": "Provide a concise summary of this conversation."
        }
    )
    
    # Add rich UI for better visualization
    ui = RichUICallback(show_thinking=True, show_tool_calls=True)
    agent.add_callback(ui)
    
    try:
        # Connect to tools/services
        await agent.connect_to_server("npx", ["@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
        
        # Run agent with complex task
        result = await agent.run("""
        I'm planning a trip to Tokyo. Can you help me:
        1. Find 3 good accommodation options
        2. Research local transportation
        3. Suggest must-visit attractions
        4. Create a 3-day itinerary
        
        Keep track of all this information for our future conversations.
        """)
        
        print(f"Result: {result}")
        
        # Check storage metadata
        print(f"\nSession metadata: {agent.metadata}")
        print(f"Messages in conversation: {len(agent.messages)}")
        
    finally:
        await agent.close()

asyncio.run(advanced_storage_example())
```

### Storage Installation Requirements

Different storage backends may require additional dependencies:

```bash
# SQLite (included with Python, no extra installation needed)
pip install tinyagent-py[sqlite]

# PostgreSQL
pip install tinyagent-py[postgres]

# Redis  
pip install tinyagent-py[redis]

# All storage backends
pip install tinyagent-py[all]
```

### Best Practices for Storage

1. **Session ID Management**: Use meaningful, unique session IDs (e.g., `user-{user_id}-{chat_type}-{timestamp}`)

2. **Resource Cleanup**: Always call `await agent.close()` to properly close storage connections

3. **Error Handling**: Wrap storage operations in try/except blocks

4. **Database Maintenance**: For production systems, implement regular database maintenance and backups

5. **Security**: Store database credentials securely using environment variables or secret management systems

6. **Performance**: For high-traffic applications, consider using Redis or PostgreSQL instead of SQLite

## Usage

### TinyAgent (Core Agent)
[![AskDev.AI | Chat with TinyAgent](https://img.shields.io/badge/AskDev.AI-Chat_with_TinyAgent-blue?style=flat-square)](https://askdev.ai/github/askbudi/tinyagent)


```python
from tinyagent import TinyAgent
from textwrap import dedent
import asyncio
import os

async def test_agent(task, model="gpt-5-mini", api_key=None):
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
await test_agent(task, model="gpt-5-mini")
```

## 🔒 Cross-Platform Sandboxing & Security

TinyAgent provides comprehensive cross-platform sandboxing with multiple provider options for secure code execution. Choose the best sandbox for your platform and requirements:

### 🌍 Universal Provider Support

| Provider | Platform | Security Model | Best For |
|----------|----------|----------------|----------|
| **🍎 SeatbeltProvider** | macOS | Native seatbelt sandbox | macOS development, local execution |
| **🐧 BubblewrapProvider** | Linux | Bubblewrap namespaces | Linux servers, CI/CD pipelines |
| **🐳 DockerProvider** | All (Windows/macOS/Linux) | Container isolation | Universal compatibility, Windows |
| **☁️ ModalProvider** | All | Cloud isolation | Production workloads, scaling |

### 🚀 Quick Setup Examples

#### Zero Configuration (Recommended)
```python
from tinyagent import TinyCodeAgent

# Automatically selects best provider for your platform
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    local_execution=True  # Auto: macOS→Seatbelt, Linux→Bubblewrap, Windows→Docker
)

result = await agent.execute_python(["print('Hello from secure sandbox!')"])
```

#### Explicit Provider Selection
```python
# Force Docker (works everywhere)
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="docker",
    provider_config={
        "memory_limit": "1g",
        "enable_network": False,
        "environment_variables": {"PROJECT_ROOT": "/workspace"}
    }
)

# Platform-specific with fallback
agent = TinyCodeAgent(
    model="gpt-4o-mini", 
    provider="bubblewrap",  # Try Linux native first
    provider_fallback=True,  # Fall back to docker if unavailable
    local_execution=True
)
```

## 📋 Platform-Specific Setup Instructions

### 🍎 macOS - SeatbeltProvider (Native)

**Requirements:**
- macOS 10.14 or later
- No additional installation needed (uses built-in `sandbox-exec`)

**Setup:**
```python
from tinyagent import TinyCodeAgent

agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="seatbelt",
    provider_config={
        "python_env_path": "/usr/local/bin/python3",
        "additional_read_dirs": ["/Users/username/projects"],
        "additional_write_dirs": ["/Users/username/projects/output"],
        "environment_variables": {
            "PROJECT_ROOT": "/Users/username/projects",
            "GITHUB_TOKEN": "your-token"  # For git operations
        },
        "bypass_shell_safety": True  # Enable shell commands
    },
    local_execution=True  # Required for seatbelt
)
```

**Security Features:**
- ✅ Process isolation with seatbelt profiles
- ✅ Filesystem access control (read-only system directories)
- ✅ Network isolation (configurable)
- ✅ Git operations with credential management
- ✅ Environment variable isolation

**Testing:**
```bash
# Verify seatbelt is available
which sandbox-exec
# Should return: /usr/bin/sandbox-exec

# Test basic sandboxing
sandbox-exec -f /usr/share/sandbox/pure.sb echo "Hello Sandbox"
```

### 🐧 Linux - BubblewrapProvider (Native)

**Requirements:**
- Linux kernel 3.8+ with user namespaces enabled
- Bubblewrap package installed

**Installation:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install bubblewrap

# CentOS/RHEL/Fedora
sudo dnf install bubblewrap
# or: sudo yum install bubblewrap

# Alpine Linux
sudo apk add bubblewrap

# Arch Linux
sudo pacman -S bubblewrap
```

**Setup:**
```python
from tinyagent import TinyCodeAgent

agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="bubblewrap",
    provider_config={
        "additional_read_dirs": ["/home/user/projects"],
        "additional_write_dirs": ["/home/user/projects/output"],
        "environment_variables": {
            "PROJECT_ROOT": "/home/user/projects",
            "GITHUB_USERNAME": "username",
            "GITHUB_TOKEN": "your-token"
        },
        "bypass_shell_safety": False  # Enable security checks
    },
    local_execution=True  # Required for bubblewrap
)
```

**Security Features:**
- ✅ Namespace isolation (PID, user, IPC, UTS, network)
- ✅ Filesystem isolation with bind mounts
- ✅ Process privilege dropping
- ✅ Resource limits and controls
- ✅ No root privileges required

**Testing:**
```bash
# Verify bubblewrap installation
bwrap --version
# Should show version info

# Test basic sandboxing
bwrap --ro-bind / / --dev /dev --proc /proc --tmpfs /tmp echo "Hello Bubblewrap"

# Verify user namespaces are enabled
cat /proc/sys/kernel/unprivileged_userns_clone
# Should return: 1
```

**Docker Testing Environment:**
```bash
# Use our pre-built Docker testing infrastructure
cd /path/to/tinyagent
git clone <repo-url> && cd tinyagent/docker-testing

# Test on specific distribution
./scripts/build-test-single.sh ubuntu-22-04

# Test across all Linux distributions
./scripts/run-all-tests.sh
```

### 🐳 Universal - DockerProvider (Cross-Platform) - **ENHANCED**

**Requirements:**
- Docker Desktop (Windows/macOS) or Docker Engine (Linux)
- Python packages: `docker`, `cloudpickle`

**Installation:**

**Windows:**
```powershell
# Install Docker Desktop
winget install Docker.DockerDesktop
# Or download from: https://docker.com/products/docker-desktop

# Install Python dependencies
pip install docker cloudpickle
```

**macOS:**
```bash
# Install Docker Desktop
brew install --cask docker
# Or download from: https://docker.com/products/docker-desktop

# Install Python dependencies
pip install docker cloudpickle
```

**Linux:**
```bash
# Install Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (avoid sudo)
sudo usermod -aG docker $USER
newgrp docker

# Install Python dependencies
pip install docker cloudpickle
```

**🆕 Enhanced Setup (Unified API):**
```python
from tinyagent import TinyCodeAgent

# 🌟 Zero Configuration (Recommended)
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="docker",
    working_directory="/path/to/your/project"  # 🔄 Auto-mounted to /workspace
)

# ✨ Dynamic System Context: AI knows it's in container with correct info
# 🗂️ Unified File Operations: Same API as native providers
# 🔧 Automatic Volume Mounting: Based on working directory

# 🏗️ Pre-configured Templates
from tinyagent.code_agent.providers.docker_provider import DockerProvider

# Data Science Optimized
ds_agent = DockerProvider.for_data_science(
    working_directory="/data/project",
    environment_variables={"JUPYTER_ENABLE_LAB": "yes"}
)

# Web Development Optimized  
web_agent = DockerProvider.for_web_development(
    working_directory="/web/project",
    environment_variables={"NODE_ENV": "development"}
)
```

**🔧 Advanced Configuration:**
```python
from tinyagent.code_agent.providers.docker_image_builder import DockerImageBuilder

# Custom Image Builder
builder = DockerImageBuilder("python:3.11-slim")
builder.add_system_packages("git", "curl", "nodejs")
builder.add_python_packages("fastapi", "pandas", "matplotlib")
builder.set_environment(API_URL="http://localhost:8000")

agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="docker",
    provider_config={
        "dockerfile_content": builder.generate_dockerfile(),
        "docker_image": builder.get_image_tag(),
        "build_image": True,
        "working_directory": "/my/project",
        "enable_network": True,
        "memory_limit": "2g",
        "cpu_limit": "2.0"
    }
)

# 📝 Inline Dockerfile
custom_dockerfile = """
FROM python:3.11-slim
RUN apt-get update && apt-get install -y git nodejs npm
RUN pip install fastapi uvicorn pandas
ENV NODE_ENV=development
USER 1000:1000
WORKDIR /workspace
"""

agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="docker",
    provider_config={
        "dockerfile_content": custom_dockerfile,
        "build_image": True
    }
)
```

**🎯 Key Enhanced Features:**

1. **🔄 Dynamic System Context**
   ```python
   # Container info is automatically injected:
   # 🐳 Container Environment: /workspace  
   # 🖥️ Platform: Linux x86_64
   # 🐍 Python: 3.11.5
   # 👤 User: tinyagent
   ```

2. **🗂️ Unified File Operations**
   ```python
   # Same API across all providers
   await agent.execute_python([
       "with open('data.txt', 'w') as f:",      # Works in container
       "    f.write('Hello!')",
       "print('File written to:', os.getcwd())" # Shows container context
   ])
   
   # Host paths automatically mapped
   await agent.execute_python([
       f"with open('{host_project_path}/file.txt', 'r') as f:",  # Auto-resolved
       "    content = f.read()"
   ])
   ```

3. **⚙️ Configuration Templates**
   ```python
   from tinyagent.code_agent.providers.docker_image_builder import DockerConfigBuilder
   
   # Fluent configuration API
   config = (DockerConfigBuilder()
       .for_machine_learning()
       .with_resources(memory="4g", cpus="4.0")
       .with_network_access(True)
       .with_custom_packages(
           system_packages=["git", "vim"],
           python_packages=["torch", "transformers"]
       )
       .build_config())
   
   agent = TinyCodeAgent(provider="docker", provider_config=config)
   ```

**🛡️ Enhanced Security Features:**
- ✅ Container isolation (process, filesystem, network)
- ✅ Non-root execution (UID 1000) with capability dropping
- ✅ Dynamic resource limits (memory, CPU, processes)
- ✅ Read-only filesystem with controlled mounts
- ✅ Network isolation (configurable)
- ✅ **NEW**: Working directory sandboxing with transparent path mapping
- ✅ **NEW**: Custom image building with security hardening

**🧪 Testing:**
```bash
# Verify Docker installation
docker --version
docker info

# Test enhanced provider
python -c "
from tinyagent.code_agent.providers.docker_provider import DockerProvider
print('✅ DockerProvider available:', DockerProvider.is_supported())
"

# Test with actual execution (requires Docker)
python -c "
import asyncio
from tinyagent import TinyCodeAgent

async def test():
    agent = TinyCodeAgent(provider='docker', working_directory='.')
    result = await agent.execute_python(['print(\"🐳 Docker container working!\")'])
    print(result.get('printed_output', ''))

asyncio.run(test())
"
```

**📚 Comprehensive Documentation:**
- [Enhanced DockerProvider Guide](docs/docker_provider_enhanced.md)
- Dynamic system context and unified API examples
- Custom image building and configuration templates
- Migration guide from basic DockerProvider usage

### ☁️ Cloud - ModalProvider (Production)

**Requirements:**
- Modal account and API key
- Internet connection

**Setup:**
```bash
# Install Modal
pip install modal

# Authenticate
modal token new
```

```python
from tinyagent import TinyCodeAgent

agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="modal",
    provider_config={
        "pip_packages": ["requests", "pandas", "matplotlib", "seaborn"],
        "timeout": 300,
        "cpu_count": 2,
        "memory_mb": 2048
    },
    local_execution=False  # Uses Modal cloud
)
```

## 🔧 Advanced Provider Configuration

### Environment Variables
```python
# Set environment variables for all providers
common_env = {
    "PROJECT_ROOT": "/workspace",
    "API_KEY": "your-secret-key",
    "GITHUB_TOKEN": "ghp_xxxx",  # For git operations
    "CUSTOM_CONFIG": "production"
}

agent = TinyCodeAgent(
    provider="auto",  # Auto-select best provider
    provider_config={
        "environment_variables": common_env,
        "additional_read_dirs": ["/data"],
        "additional_write_dirs": ["/output"]
    }
)
```

### Git Operations Support
```python
# Configure git operations across all providers
git_config = {
    "environment_variables": {
        "GIT_AUTHOR_NAME": "TinyAgent",
        "GIT_AUTHOR_EMAIL": "agent@example.com",
        "GITHUB_USERNAME": "your-username",
        "GITHUB_TOKEN": "your-token"
    }
}

agent = TinyCodeAgent(
    provider="auto",
    provider_config=git_config
)

# Git operations work across all providers
result = await agent.execute_shell(["git", "clone", "https://github.com/user/repo.git"])
```

### Security Best Practices

#### 1. Principle of Least Privilege
```python
# Only grant necessary directory access
secure_config = {
    "additional_read_dirs": ["/app/data"],        # Only data directory
    "additional_write_dirs": ["/app/output"],     # Only output directory
    "bypass_shell_safety": False,                # Enable command filtering
    "enable_network": False                      # Disable network access
}
```

#### 2. Environment Isolation
```python
# Clean environment with only necessary variables
clean_env = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "PYTHONPATH": "/app",
    "PROJECT_ENV": "sandbox"
    # Don't include sensitive host environment
}
```

#### 3. Resource Limits
```python
# Prevent resource exhaustion
resource_limits = {
    "memory_limit": "512m",     # Limit memory usage
    "cpu_limit": "1.0",        # Limit CPU usage
    "timeout": 180,            # 3 minute timeout
    "max_processes": 10        # Process limit (Docker)
}
```

## 🧪 Testing Your Sandbox Setup

### Automated Testing
```python
import asyncio
from tinyagent import TinyCodeAgent

async def test_sandbox():
    """Test sandbox functionality across providers."""
    
    providers = ["auto", "seatbelt", "bubblewrap", "docker", "modal"]
    
    for provider in providers:
        try:
            agent = TinyCodeAgent(
                model="gpt-4o-mini",
                provider=provider,
                provider_fallback=True  # Allow fallback
            )
            
            # Test Python execution
            result = await agent.execute_python([
                "import platform",
                "print(f'Running on: {platform.system()}')",
                "print('Sandbox test successful!')"
            ])
            
            print(f"✅ {provider}: {result['printed_output'].strip()}")
            
        except Exception as e:
            print(f"❌ {provider}: {str(e)}")
        
        finally:
            if 'agent' in locals():
                await agent.cleanup()

# Run the test
asyncio.run(test_sandbox())
```

### Manual Testing
```python
# Test filesystem isolation
result = await agent.execute_python([
    "import os",
    "print('Current directory:', os.getcwd())",
    "print('Can access /etc/passwd:', os.path.exists('/etc/passwd'))",
    "print('Can write to /tmp:', os.access('/tmp', os.W_OK))"
])

# Test network isolation (should fail if disabled)
result = await agent.execute_python([
    "import requests",
    "response = requests.get('https://httpbin.org/ip', timeout=5)",
    "print('Network access:', response.status_code)"
])

# Test shell command filtering
result = await agent.execute_shell(["rm", "-rf", "/"])  # Should be blocked
result = await agent.execute_shell(["ls", "-la"])       # Should work
```

## TinyCodeAgent - Advanced Code Execution with File Tools

TinyCodeAgent is a specialized agent for secure code execution with comprehensive file operations, multiple provider backends, and advanced tooling.

### Key New Features

- **🔒 Cross-Platform Sandboxing**: Native sandbox providers for macOS (Seatbelt), Linux (Bubblewrap), and universal Docker support
- **🛠️ Intelligent Provider Selection**: Automatic platform detection with graceful fallbacks
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
    # Zero-configuration setup (recommended)
    agent = TinyCodeAgent(
        model="gpt-4o-mini",
        api_key="your-openai-api-key",
        local_execution=True,  # Auto-selects best provider for your platform
        
        # Enable all new tools
        enable_file_tools=True,      # read_file, write_file, update_file, glob, grep
        enable_shell_tool=True,      # Enhanced bash tool
        enable_todo_write=True,      # Task management
        
        # Auto git checkpoints
        auto_git_checkpoint=True,
        
        # Rich terminal UI
        ui="rich"
    )
    
    try:
        # Complex cross-platform task with file operations
        result = await agent.run("""
        I need to analyze and refactor a Python project:
        
        1. Use glob to find all Python files in the project
        2. Use grep to identify functions that need refactoring
        3. Read key files to understand the architecture  
        4. Create a refactoring plan with todos
        5. Implement improvements with file operations
        6. Run tests to verify changes
        
        Use the todo system to track progress throughout.
        This will work on macOS (seatbelt), Linux (bubblewrap), or Windows (docker)!
        """)
        
        print(result)
    finally:
        await agent.close()

asyncio.run(main())
```

### Platform-Specific Examples

#### macOS Development Setup
```python
# Optimized for macOS development with Seatbelt sandbox
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="seatbelt",
    provider_config={
        "additional_read_dirs": ["/Users/username/projects"],
        "additional_write_dirs": ["/Users/username/projects/output"],
        "environment_variables": {
            "GITHUB_TOKEN": "your-token",
            "PROJECT_ROOT": "/Users/username/projects"
        },
        "bypass_shell_safety": True  # Enable shell commands for development
    },
    local_execution=True,
    enable_file_tools=True,
    ui="rich"
)
```

#### Linux Server Setup
```python
# Optimized for Linux servers with Bubblewrap isolation
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="bubblewrap",
    provider_config={
        "additional_read_dirs": ["/home/user/projects"],
        "additional_write_dirs": ["/home/user/output"],
        "environment_variables": {
            "GITHUB_USERNAME": "username",
            "GITHUB_TOKEN": "token"
        },
        "bypass_shell_safety": False  # Security-first for servers
    },
    local_execution=True,
    enable_file_tools=True
)
```

#### Windows/Universal Setup
```python
# Universal setup using Docker (works on Windows, macOS, Linux)
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="docker",
    provider_config={
        "memory_limit": "1g",
        "cpu_limit": "2.0",
        "enable_network": True,  # Enable for git operations
        "environment_variables": {
            "GITHUB_TOKEN": "your-token",
            "PROJECT_ROOT": "/workspace"
        },
        "additional_read_dirs": ["/host/data"],
        "additional_write_dirs": ["/host/output"]
    },
    enable_file_tools=True,
    ui="rich"
)
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

### Cross-Platform Provider System

TinyCodeAgent uses an intelligent provider system that automatically selects the best execution backend for your platform:

```python
# Automatic provider selection (recommended)
agent = TinyCodeAgent(local_execution=True)  
# Auto-selects: macOS→Seatbelt, Linux→Bubblewrap, Windows→Docker

# Explicit provider selection
agent = TinyCodeAgent(provider="seatbelt")    # macOS native sandbox
agent = TinyCodeAgent(provider="bubblewrap")  # Linux native sandbox
agent = TinyCodeAgent(provider="docker")     # Universal container-based
agent = TinyCodeAgent(provider="modal")      # Cloud execution

# Provider with fallback
agent = TinyCodeAgent(
    provider="bubblewrap",      # Try Linux native first
    provider_fallback=True,     # Fall back to docker if unavailable
    local_execution=True
)

# Check available providers
from tinyagent import TinyCodeAgent
available = TinyCodeAgent.get_available_providers()
print(f"Available: {available}")  # ['seatbelt', 'docker', 'modal']

best_local = TinyCodeAgent.get_best_local_provider()
print(f"Best local: {best_local}")  # 'seatbelt' on macOS, 'bubblewrap' on Linux
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
# LLM is not good at this task, counting characters, avoid duplicates, but with the power of code, tiny model like gpt-5-mini can do it without any problem.
```


### Full Configuration Options

```python
from tinyagent import TinyCodeAgent
from tinyagent.code_agent.tools.file_tools import ProductionApprovalHook

# Complete cross-platform configuration example
agent = TinyCodeAgent(
    # Core configuration
    model="gpt-4o-mini",
    api_key="your-api-key",
    
    # Cross-platform provider selection
    provider="auto",              # Auto-select best provider
    provider_fallback=True,       # Enable fallback chain
    local_execution=True,         # Prefer local over cloud
    
    # Universal provider configuration
    provider_config={
        # Common options (work across all providers)
        "additional_read_dirs": ["/path/to/data", "/path/to/config"],
        "additional_write_dirs": ["/path/to/output"],
        "environment_variables": {
            "PROJECT_ROOT": "/workspace",
            "GITHUB_TOKEN": "your-token",
            "API_KEY": "your-api-key"
        },
        "bypass_shell_safety": True,  # Enable shell commands
        
        # Platform-specific options (automatically filtered)
        "python_env_path": "/usr/local/bin/python3",  # Seatbelt/Bubblewrap
        "memory_limit": "1g",                          # Docker/Modal
        "cpu_limit": "2.0",                           # Docker/Modal
        "timeout": 300,                               # All providers
        "pip_packages": ["requests", "pandas"],       # Modal/Docker
    },
    
    # Tool enablement (all True by default)
    enable_python_tool=True,         # Python code execution
    enable_shell_tool=True,          # Enhanced bash tool
    enable_file_tools=True,          # read_file, write_file, update_file, glob, grep
    enable_todo_write=True,          # Task management system
    
    # Python environment setup
    authorized_imports=["requests", "pandas", "numpy", "matplotlib", "seaborn"],
    pip_packages=["requests", "pandas", "matplotlib"],  # For cloud providers
    
    # File and shell operations
    default_workdir="/workspace",
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
        "summary_model": "gpt-4o-mini"
    }
)

# Add custom file operation controls
file_hook = ProductionApprovalHook()  # Requires approval for file modifications
agent.add_callback(file_hook)
```

### Provider-Specific Configuration

#### macOS - Seatbelt Provider Configuration
```python
seatbelt_config = {
    "python_env_path": "/usr/local/bin/python3",
    "additional_read_dirs": ["/Users/username/projects"],
    "additional_write_dirs": ["/Users/username/output"],
    "environment_variables": {
        "GITHUB_TOKEN": "your-token",
        "PROJECT_ROOT": "/Users/username/projects"
    },
    "bypass_shell_safety": True  # More permissive for local development
}

agent = TinyCodeAgent(
    provider="seatbelt", 
    provider_config=seatbelt_config,
    local_execution=True  # Required for seatbelt
)
```

#### Linux - Bubblewrap Provider Configuration
```python
bubblewrap_config = {
    "additional_read_dirs": ["/home/user/projects"],
    "additional_write_dirs": ["/home/user/output"],
    "environment_variables": {
        "GITHUB_USERNAME": "username",
        "GITHUB_TOKEN": "your-token",
        "PROJECT_ROOT": "/home/user/projects"
    },
    "bypass_shell_safety": False  # More restrictive for servers
}

agent = TinyCodeAgent(
    provider="bubblewrap",
    provider_config=bubblewrap_config,
    local_execution=True  # Required for bubblewrap
)
```

#### Universal - Docker Provider Configuration
```python
docker_config = {
    "docker_image": "tinyagent-runtime:latest",  # Auto-built if missing
    "memory_limit": "1g",                      # Resource limits
    "cpu_limit": "2.0",
    "timeout": 300,                            # 5 minute timeout
    "enable_network": True,                    # Enable for git operations
    "environment_variables": {
        "GITHUB_TOKEN": "your-token",
        "PROJECT_ROOT": "/workspace"
    },
    "additional_read_dirs": ["/host/data"],
    "additional_write_dirs": ["/host/output"]
}

agent = TinyCodeAgent(
    provider="docker",
    provider_config=docker_config
    # Works on Windows, macOS, and Linux
)
```

#### Cloud - Modal Provider Configuration
```python
modal_config = {
    "pip_packages": ["requests", "pandas", "matplotlib"],
    "timeout": 300,
    "cpu_count": 2,
    "memory_mb": 2048,
    "bypass_shell_safety": False,  # More restrictive for cloud
    "additional_safe_shell_commands": ["custom_cmd"]
}

agent = TinyCodeAgent(
    provider="modal", 
    provider_config=modal_config,
    local_execution=False  # Use Modal cloud
)
```

### Automatic Git Checkpoints

TinyCodeAgent can automatically create Git checkpoints after each successful shell command execution. This helps track changes made by the agent and provides a safety net for reverting changes if needed.

```python
# Enable automatic Git checkpoints during initialization
agent = TinyCodeAgent(
    model="gpt-5-mini",
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

## 🛡️ Security Model Comparison

| Security Feature | Seatbelt (macOS) | Bubblewrap (Linux) | Docker (Universal) | Modal (Cloud) |
|------------------|------------------|--------------------|--------------------|---------------|
| **Process Isolation** | ✅ Seatbelt profiles | ✅ PID namespaces | ✅ Container isolation | ✅ Cloud isolation |
| **Filesystem Control** | ✅ Read-only binds | ✅ Bind mounts | ✅ Volume mounts | ✅ Serverless isolation |
| **Network Isolation** | ✅ Configurable | ✅ Network namespaces | ✅ Network modes | ✅ Cloud network |
| **Privilege Dropping** | ✅ Sandbox profiles | ✅ User namespaces | ✅ Non-root user | ✅ Serverless |
| **Resource Limits** | ⚠️ Basic | ✅ cgroups | ✅ Docker limits | ✅ Cloud limits |
| **Git Operations** | ✅ Full support | ✅ Full support | ✅ Full support | ✅ Full support |
| **State Persistence** | ✅ CloudPickle | ✅ CloudPickle | ✅ Volume mounts | ✅ Modal storage |
| **Setup Complexity** | 🟢 Zero setup | 🟡 Package install | 🟡 Docker required | 🟢 API key only |

## 🎯 Provider Selection Guide

**Choose Seatbelt if:**
- ✅ Developing on macOS
- ✅ Need fastest execution (native)
- ✅ Want zero additional setup
- ✅ Prefer Apple's security model

**Choose Bubblewrap if:**
- ✅ Running on Linux servers
- ✅ Need strong isolation without containers
- ✅ Want lightweight sandboxing
- ✅ CI/CD pipelines on Linux

**Choose Docker if:**
- ✅ Need universal compatibility (Windows/macOS/Linux)
- ✅ Want consistent environment across platforms
- ✅ Already using Docker in your workflow
- ✅ Need reproducible execution environment

**Choose Modal if:**
- ✅ Need cloud-scale execution
- ✅ Want serverless code execution
- ✅ Have variable computational needs
- ✅ Prefer managed infrastructure

**Use Auto-Selection if:**
- ✅ Building cross-platform applications
- ✅ Want optimal performance per platform
- ✅ Need graceful fallbacks
- ✅ Prefer zero-configuration setup

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
        model="gpt-5-mini",
        api_key="your-api-key"
    )
    
    # Add a general-purpose subagent
    helper = create_general_subagent(
        name="helper",
        model="gpt-5-mini",
        max_turns=15,
        enable_python=True,
        enable_shell=True
    )
    main_agent.add_tool(helper)
    
    # Add a specialized coding subagent  
    coder = create_coding_subagent(
        name="coder",
        model="gpt-5-mini",
        max_turns=25
    )
    main_agent.add_tool(coder)
    
    # Check available tools (subagents appear as tools)
    available_tools = list(main_agent.custom_tool_handlers.keys())
    print(f"Available tools: {available_tools}")  # ['TodoWrite', 'helper', 'coder']
    
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
    model="gpt-5",
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
    model="gpt-5-mini",
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
    model="gpt-5",
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
    model="gpt-5-mini",
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
    model="gpt-5-mini",
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
            # ✅  Modify event_kwargs["messages"] (what goes to LLM)
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
    agent = TinyAgent(model="gpt-5-mini", api_key="YOUR_API_KEY")
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
- Use `"gpt-5-mini"` as the default model in examples.
- Include proper error handling and compatibility for both new and legacy interfaces.
- Test your hook with the compatibility test framework in `test_all_hooks_compatibility.py`.

---

## License

MIT License. See [LICENSE](LICENSE).


# Added Name
Tiny Agent
