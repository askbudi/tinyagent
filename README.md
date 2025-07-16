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

**Two Main Components:**
- **TinyAgent**: Core agent with MCP tool integration and extensible hooks
- **TinyCodeAgent**: Specialized agent for secure Python code execution with pluggable providers

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

## TinyCodeAgent - Code Execution Made Easy

TinyCodeAgent is a specialized agent for executing Python code with enterprise-grade reliability and extensible execution providers.

### Quick Start with TinyCodeAgent

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
        # Ask the agent to solve a coding problem
        result = await agent.run("Calculate the factorial of 10 and explain the algorithm")
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


### Configuration Options

```python
from tinyagent import TinyCodeAgent
from tinyagent.code_agent.tools import get_weather, get_traffic

# Full configuration example
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    api_key="your-api-key", 
    provider="modal",
    tools=[get_weather, get_traffic],
    authorized_imports=["requests", "pandas", "numpy"],
    provider_config={
        "pip_packages": ["requests", "pandas"],
        "sandbox_name": "my-code-sandbox"
    }
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

---

## List of Available Hooks

You can import and use these hooks from `tinyagent.hooks`:

| Hook Name                | Description                                      | Example Import                                  |
|--------------------------|--------------------------------------------------|-------------------------------------------------|
| `LoggingManager`         | Granular logging control for all modules         | `from tinyagent.hooks.logging_manager import LoggingManager` |
| `RichUICallback`         | Rich terminal UI (with [rich](https://github.com/Textualize/rich)) | `from tinyagent.hooks.rich_ui_callback import RichUICallback` |
| `GradioCallback` | Interactive browser-based chat UI: file uploads, live thinking, tool calls, token stats | `from tinyagent.hooks.gradio_callback import GradioCallback`         |

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
- Add an example usage as `async def run_example()` in the same file.
- Use `"gpt-4.1-mini"` as the default model in examples.

---

## License

MIT License. See [LICENSE](LICENSE).
