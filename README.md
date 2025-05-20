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

## Overview
This is a tiny agent that uses MCP and LiteLLM to interact with a model. You have full control over the agent, you can add any tools you like from MCP and extend the agent using its event system.

## Installation

### Using pip
```bash
# Basic installation
pip install tinyagent-py

# Install with all optional dependencies
pip install tinyagent-py[all]

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

# Install with PostgreSQL support
uv pip install tinyagent-py[postgres]

# Install with SQLite support
uv pip install tinyagent-py[sqlite]

# Install with Gradio UI support
uv pip install tinyagent-py[gradio]

# Install with all optional dependencies
uv pip install tinyagent-py[all]

# Install with development tools
uv pip install tinyagent-py[dev]
```

## Usage
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
