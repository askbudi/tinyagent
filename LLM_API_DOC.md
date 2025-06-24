# TinyAgent & TinyCodeAgent: A Developer's Guide for LLMs

This document provides all the necessary information to build applications using `TinyAgent` and `TinyCodeAgent`. It is designed to be read and understood by a Large Language Model.

## 1. Introduction: The TinyAgent Ecosystem

The TinyAgent ecosystem consists of two main classes:
-   **`TinyAgent`**: A general-purpose AI agent that can use tools to accomplish tasks. It is lightweight, extensible, and connects to tool servers using the Model Context Protocol (MCP).
-   **`TinyCodeAgent`**: A specialized version of `TinyAgent` designed for securely executing Python code. It uses a provider system (e.g., Modal.com) to run code in a sandboxed environment.

The core design philosophy is **extensibility through hooks**. You can add custom functionality like logging, UIs, or memory systems by creating and attaching callbacks to the agent.

## 2. The Core: `TinyAgent`

`TinyAgent` is the foundation. It manages the conversation with an LLM, handles tool calls, and orchestrates the overall workflow.

### 2.1. Initialization

You create an agent using the `TinyAgent.create()` async factory method.

```python
import os
import logging
from tinyagent import TinyAgent
from tinyagent.storage import Storage # Abstract base class
from tinyagent.storage.sqlite_storage import SqliteStorage # Concrete implementation

# It's best practice to set up logging
logger = logging.getLogger(__name__)

# To persist agent state, create a storage instance
storage = SqliteStorage(db_path="./agent_sessions.db")

# Async factory to create and potentially load a session
agent = await TinyAgent.create(
    model="gpt-4.1-mini",
    api_key=os.environ.get("OPENAI_API_KEY"),
    system_prompt="You are a helpful assistant.",
    temperature=0.0,
    logger=logger,
    # For persistence:
    storage=storage,
    session_id="unique-session-id-123", # Required for loading/saving
    user_id="optional-user-id",
    persist_tool_configs=False
)
```

**Key `create` / `__init__` Parameters:**
*   `model`: The LiteLLM model string (e.g., `"gpt-4.1-mini"`, `"o1-preview"`).
*   `api_key`: Your API key for the model provider.
*   `system_prompt`: The initial system message for the LLM.
*   `logger`: A standard Python logger instance.
*   `storage`: A storage instance (like `SqliteStorage`) for session persistence.
*   `session_id`: A unique ID for the agent's session. If a `storage` backend is provided, the agent will try to load a session with this ID.

### 2.2. Running the Agent

The main entry point is the `agent.run()` method.

```python
user_input = "What is the capital of Canada?"
final_answer = await agent.run(user_input, max_turns=10)
print(final_answer)
```
*   `user_input`: The user's prompt.
*   `max_turns`: The maximum number of LLM-tool-LLM cycles before stopping. This prevents infinite loops.

### 2.3. Working with Tools

TinyAgent can use two types of tools:
1.  **MCP Tools**: Tools exposed by external servers.
2.  **Custom Python Tools**: Python functions or classes defined in your code.

#### 2.3.1. Connecting to MCP Servers

Use `agent.connect_to_server()` to add tools from a Model Context Protocol (MCP) server.

```python
# Connect to a server and add all its tools
await agent.connect_to_server(
    command="npx",
    args=["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"]
)
```

#### 2.3.2. Creating Custom Tools

Use the `@tool` decorator to turn any Python function or class into a tool the agent can use.

```python
from tinyagent import tool
from typing import Optional

@tool(name="get_weather", description="Fetches the weather for a specific city.")
def get_weather(city: str, unit: Optional[str] = "celsius") -> str:
    """
    A simple weather tool.
    The docstring is used as the description if one isn't provided in the decorator.
    """
    if city == "Toronto":
        return f"The weather in Toronto is 20 degrees {unit}."
    else:
        return f"Sorry, I don't have weather information for {city}."

# Add the tool to the agent
agent.add_tool(get_weather)
```

### 2.4. Control Flow Tools

The agent has built-in tools for controlling the conversation flow:

*   `final_answer(content: str)`: The LLM calls this when it has completed the task. The `content` is the final response to the user.
*   `ask_question(question: str)`: The LLM calls this to ask a clarifying question to the user.

You do not add these tools manually; they are always available to the LLM.

### 2.5. The Hook System (Callbacks)

Hooks allow you to extend the agent's behavior by listening to events. Add a hook with `agent.add_callback()`. A hook is an `async` or regular callable that accepts `(event_name, agent, **kwargs)`.

**Key Events:**
*   `agent_start`: The `agent.run()` method is called.
*   `message_add`: A message (user, assistant, tool) is added to the history.
*   `llm_start`: An LLM call is about to be made.
*   `llm_end`: An LLM call has just finished.
*   `agent_end`: The agent has finished its run (returned a `final_answer` or `ask_question`).

```python
async def my_simple_hook(event_name, agent, **kwargs):
    print(f"EVENT: {event_name}")
    if event_name == "llm_end":
        usage = kwargs.get("response", {}).usage
        print(f"LLM Usage: {usage}")

agent.add_callback(my_simple_hook)
```

### 2.6. Resource Management

**Crucially, you must always call `agent.close()` to clean up resources**, like server connections and storage handles. Use a `try...finally` block.

```python
agent = await TinyAgent.create(...)
try:
    await agent.run("Do a task.")
finally:
    await agent.close()
```

## 3. The Specialist: `TinyCodeAgent`

`TinyCodeAgent` is a powerful subclass of `TinyAgent` built specifically for **executing Python code**. It provides a secure, sandboxed environment for the LLM to write and run code to solve complex problems.

### 3.1. Initialization

`TinyCodeAgent` has a similar constructor to `TinyAgent`, but with additional parameters for configuring the code execution environment.

```python
from tinyagent import TinyCodeAgent

code_agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    api_key=os.environ.get("OPENAI_API_KEY"),
    # LLM-level tools (work like regular TinyAgent tools)
    tools=[], 
    # Tools available *inside* the Python code execution environment
    code_tools=[data_processor], 
    # Python packages to install in the sandbox
    pip_packages=["pandas", "matplotlib"],
    # Modules the generated code is allowed to import
    authorized_imports=["pandas", "matplotlib.pyplot", "io", "base64"],
    # Variables to pre-load into the Python environment
    user_variables={"my_data": [1, 2, 3, 4, 5]},
    # Set to True for local development/testing
    local_execution=False 
)
```

**Key `TinyCodeAgent` Parameters:**
*   `provider`: The execution backend. Defaults to `"modal"`, which uses Modal.com for secure, remote execution.
*   `local_execution`: If `True`, uses Modal's local runner instead of the cloud. Useful for debugging.
*   `tools`: A list of standard LLM tools, just like in `TinyAgent`.
*   `code_tools`: A list of Python functions (decorated with `@tool`) that are made available *inside* the code execution environment. The LLM can't call these directly, but the code it writes *can*.
*   `pip_packages`: A list of packages to `pip install` in the sandbox.
*   `authorized_imports`: A security feature. The generated code can only import modules from this list.
*   `user_variables`: A dictionary of Python objects that are pre-loaded into the global scope of the execution environment.

### 3.2. How it Works: The `run_python` Tool

`TinyCodeAgent` automatically adds a powerful `run_python(code_lines: list[str])` tool to the LLM. The LLM's primary job is to call this tool with Python code to solve the user's request.

The system prompt for `TinyCodeAgent` is specifically designed to guide the LLM on how to use `run_python` effectively.

### 3.3. `code_tools` vs. `tools`

This is a critical distinction:
-   **`tools`**: LLM-level tools. The LLM sees these and can call them directly. Example: `search_web(query)`.
-   **`code_tools`**: Python-level tools. The LLM cannot call these directly. Instead, the Python code *it writes* and passes to `run_python` can call them. Example: a `data_processor(data)` function.

## 4. The UI: `GradioCallback`

The `GradioCallback` is a hook that creates a rich, interactive web UI for your agent. It's the best way to build a user-facing application.

### 4.1. Setup and Launch

```python
from tinyagent.hooks.gradio_callback import GradioCallback
import tempfile

# 1. Initialize your agent (can be TinyAgent or TinyCodeAgent)
agent = TinyCodeAgent(...) 

# 2. Create a temporary folder for file uploads
upload_folder = tempfile.mkdtemp()

# 3. Instantiate the Gradio UI callback
gradio_ui = GradioCallback(
    file_upload_folder=upload_folder,
    show_thinking=True,
    show_tool_calls=True,
    logger=logger # Recommended
)

# 4. Register the callback with the agent
agent.add_callback(gradio_ui)

# 5. Launch the web interface (this is a blocking call)
# The launch method handles creating the app and running it.
gradio_ui.launch(
    agent,
    title="My Awesome Code Agent",
    description="Ask me to analyze data or create plots!",
    share=False, # Set to True for a public link
)

# Remember to clean up the upload folder when done
```

### 4.2. Key Features of the Gradio UI

-   **Interactive Chat**: Real-time, streaming conversation.
-   **File Uploads**: Users can upload files. The file paths are made available to the agent.
-   **Live Updates**: Shows "thinking" indicators, tool calls as they happen, and final results.
-   **Detailed Views**: Expandable sections show tool inputs/outputs and token usage.
-   **Full Control**: The UI is built on Gradio, so it's customizable.

## 5. Putting It All Together: Complete Example

This example demonstrates how to combine `TinyCodeAgent`, `GradioCallback`, and custom `code_tools` to build a complete data analysis web application.

```python
import asyncio
import os
import logging
import sys
import tempfile
import shutil
from typing import List, Dict, Any

from tinyagent import TinyCodeAgent, tool
from tinyagent.hooks.gradio_callback import GradioCallback
from tinyagent.hooks.logging_manager import LoggingManager

# --- 1. Set up Logging (Best Practice) ---
log_manager = LoggingManager(default_level=logging.INFO)
log_manager.set_levels({
    'tinyagent.code_agent': logging.DEBUG,
    'tinyagent.hooks.gradio_callback': logging.DEBUG,
})
console_handler = logging.StreamHandler(sys.stdout)
log_manager.configure_handler(
    console_handler,
    format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = log_manager.get_logger('main_app')

# --- 2. Define a Custom Code Tool ---
# This tool will be available *inside* the Python execution environment.
@tool(name="data_processor", description="Process data arrays and return stats.")
def data_processor(data: List[float]) -> Dict[str, Any]:
    """Processes a list of numbers and returns statistics."""
    if not data:
        return {}
    return {
        "mean": sum(data) / len(data),
        "max": max(data),
        "min": min(data),
        "count": len(data)
    }

# --- 3. Main Application Logic ---
async def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("Please set the OPENAI_API_KEY environment variable.")
        return

    # Create a temporary folder for Gradio file uploads
    upload_folder = tempfile.mkdtemp(prefix="gradio_uploads_")
    logger.info(f"Upload folder: {upload_folder}")

    agent = None
    try:
        # --- 4. Initialize TinyCodeAgent ---
        agent = TinyCodeAgent(
            model="gpt-4.1-mini",
            api_key=api_key,
            log_manager=log_manager,
            # Provide the custom tool to the code execution sandbox
            code_tools=[data_processor],
            # Pre-load some data for the agent to use
            user_variables={"sample_data": [10, 25, 5, 42, 18, 22]},
            # Allow these packages to be used in the generated code
            pip_packages=["pandas", "numpy", "matplotlib"],
            authorized_imports=["pandas", "numpy", "matplotlib.pyplot", "io", "base64"],
            local_execution=False, # Use remote Modal for security
        )

        # --- 5. Initialize and Add GradioCallback ---
        gradio_ui = GradioCallback(
            file_upload_folder=upload_folder,
            show_thinking=True,
            show_tool_calls=True,
            logger=log_manager.get_logger('gradio_ui')
        )
        # This connects the UI to the agent's event stream
        agent.add_callback(gradio_ui)

        # --- 6. Launch the Gradio UI ---
        # This is a blocking call that starts the web server.
        logger.info("Launching Gradio UI... Press Ctrl+C to exit.")
        gradio_ui.launch(
            agent,
            title="Interactive Data Analysis Agent",
            description="""
            Ask me to analyze the pre-loaded `sample_data` or upload a file.
            Try these prompts:
            - "Analyze the sample_data using the data_processor tool and tell me the result."
            - "Create a bar chart of the sample_data, save it as a base64 encoded image string and show me the result."
            """,
            share=False
        )
    except KeyboardInterrupt:
        logger.info("UI shutting down.")
    finally:
        # --- 7. Clean up resources ---
        if agent:
            await agent.close()
        shutil.rmtree(upload_folder)
        logger.info("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(main())
```

## 6. Summary for LLMs: How to Build with TinyAgent

1.  **Choose Your Agent**:
    *   Use `TinyAgent` for general tasks with tools (web search, APIs).
    *   Use `TinyCodeAgent` for tasks requiring data manipulation, computation, visualization, or file processing via Python code.

2.  **Structure Your Code**:
    *   Use an `async def main():` structure.
    *   Wrap your agent logic in a `try...finally` block.
    *   **ALWAYS** call `await agent.close()` in the `finally` block.

3.  **Define Your Tools**:
    *   For `TinyCodeAgent`, decide if a tool should be an LLM-level `tool` (for the agent to call) or a `code_tool` (for the generated Python code to call).
    *   Decorate all tools with `@tool`. Provide clear names and descriptions.

4.  **Build the UI**:
    *   For any interactive application, use `GradioCallback`.
    *   Instantiate it, add it to the agent with `add_callback`, and call `gradio_ui.launch(agent)`.

5.  **Run the Agent**:
    *   Call `await agent.run(user_prompt)` to start the process.
    *   If using Gradio, the UI handles calling `run` for you.

By following these patterns, you can reliably construct robust and interactive AI applications. 