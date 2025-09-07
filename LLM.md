# TinyAgent Library API Documentation

TinyAgent is a minimal but powerful agent framework with MCP Client, Code Agent capabilities, and extensible hooks.

## Installation

```bash
pip install tinyagent-py
```

## Core Components

### Main Imports
```python
from tinyagent import TinyAgent, MCPClient, TinyCodeAgent, tool
```

---

# Core TinyAgent API

## Import Path
```python
from tinyagent import TinyAgent, tool
```

## TinyAgent Class

Main agent class with session persistence and robust error handling.

### Constructor
```python
TinyAgent(
    model: str = "gpt-4.1-mini",
    api_key: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.0,
    logger: Optional[logging.Logger] = None,
    model_kwargs: Optional[Dict[str, Any]] = {},
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    storage: Optional[Storage] = None,
    load_session_on_init: bool = False,
    memory_manager: Optional[MemoryManager] = None
)
```

### Core Methods

#### `async run(user_input: str, max_turns: int = 10) -> str`
Run the agent with user input.
```python
result = await agent.run("What is the capital of France?")
```

#### `async resume(max_turns: int = 10) -> str`
Resume conversation without new user message.
```python
result = await agent.resume()
```

#### `add_tool(tool_func_or_class: Any) -> None`
Add a custom tool decorated with @tool.
```python
@tool("weather", "Get weather for a city")
def get_weather(city: str) -> str:
    return f"Weather in {city}: Sunny"

agent.add_tool(get_weather)
```

#### `add_tools(tools: List[Any]) -> None`
Add multiple tools at once.
```python
agent.add_tools([get_weather, get_traffic])
```

#### `async connect_to_server(command: str, args: List[str]) -> None`
Connect to MCP server.
```python
await agent.connect_to_server("python", ["-m", "mcp_server"])
```

#### `add_callback(callback: callable) -> None`
Add event callback.
```python
agent.add_callback(rich_ui_callback)
```

#### `async close()`
Clean up resources.
```python
await agent.close()
```

#### `clear_conversation()`
Clear conversation history.
```python
agent.clear_conversation()
```

#### `async summarize() -> str`
Generate conversation summary.

#### `async compact() -> bool`
Replace conversation with summary.

#### `as_tool(name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]`
Convert agent to tool for use by other agents.

### Class Methods

#### `async create(...) -> TinyAgent`
Async factory method.
```python
agent = await TinyAgent.create(
    model="gpt-4",
    api_key="your-key",
    storage=JsonFileStorage("./sessions")
)
```

### Tool Decorator

#### `@tool(name: Optional[str] = None, description: Optional[str] = None, schema: Optional[Dict[str, Any]] = None)`
Decorator to create tools from functions or classes.

```python
@tool("calculator", "Perform basic math operations")
def calculate(operation: str, a: float, b: float) -> float:
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    return 0

@tool("weather_service", "Weather service class")
class WeatherService:
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def __call__(self) -> str:
        return "Weather data"
```

---


# Memory Manager API

## Import Path
```python
from tinyagent.memory_manager import MemoryManager, MessageImportance, MessageType, MemoryStrategy
from tinyagent.memory_manager import ConservativeStrategy, AggressiveStrategy, BalancedStrategy
```

## MemoryManager Class

Advanced memory management system for TinyAgent with intelligent message removal and summarization.

### Constructor
```python
MemoryManager(
    max_tokens: int = 8000,
    target_tokens: int = 6000,
    strategy: MemoryStrategy = None,
    enable_summarization: bool = True,
    logger: Optional[logging.Logger] = None
)
```

### Core Methods

#### `optimize_messages(messages: List[Dict[str, Any]], token_counter: callable) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]`
Main optimization method that removes/summarizes less important messages.

```python
memory_manager = MemoryManager(max_tokens=8000, target_tokens=6000)
optimized_messages, info = memory_manager.optimize_messages(messages, token_counter)
print(f"Saved {info['tokens_saved']} tokens")
```

#### `get_memory_stats() -> Dict[str, Any]`
Get comprehensive memory management statistics.

#### `should_optimize_memory(total_tokens: int) -> bool`
Determine if memory optimization is needed.

---

# Code Agent API

## Import Paths
```python
from tinyagent.code_agent import TinyCodeAgent
from tinyagent.code_agent.providers import CodeExecutionProvider, ModalProvider

# Conditional import for macOS only
import platform
if platform.system() == "Darwin":
    from tinyagent.code_agent.providers import SeatbeltProvider
```

## TinyCodeAgent Class

Specialized TinyAgent for code execution tasks with pluggable execution providers.

### Constructor
```python
TinyCodeAgent(
    model: str = "gpt-4.1-mini",
    api_key: Optional[str] = None,
    provider: str = "modal",
    tools: Optional[List[Any]] = None,
    code_tools: Optional[List[Any]] = None,
    local_execution: bool = False,
    check_string_obfuscation: bool = True,
    **agent_kwargs
)
```

### Core Methods

#### `async run(user_input: str, max_turns: int = 10) -> str`
Run the code agent with user input.
```python
result = await agent.run("Calculate factorial of 10 using Python")
```

#### `set_user_variables(variables: Dict[str, Any])`
Set variables available in Python environment.
```python
agent.set_user_variables({"api_key": "secret", "data": [1, 2, 3]})
```

#### `add_ui_callback(ui_type: str, optimized: bool = True)`
Add UI callback for interactive interfaces.
```python
agent.add_ui_callback("rich")  # or "jupyter"
```

## Providers

### ModalProvider
Modal.com-based code execution provider for scalable, secure remote execution.

```python
modal_config = {
    "pip_packages": ["pandas", "matplotlib"],
    "authorized_imports": ["requests", "numpy.*"],
    "modal_secrets": {"API_KEY": "secret"}
}

agent = TinyCodeAgent(
    provider="modal",
    provider_config=modal_config,
    local_execution=False
)
```

### SeatbeltProvider (macOS only)
macOS sandbox-exec based provider for local sandboxed execution.

```python
seatbelt_config = {
    "additional_read_dirs": ["/path/to/data"],
    "additional_write_dirs": ["/path/to/output"]
}

agent = TinyCodeAgent(
    provider="seatbelt",
    provider_config=seatbelt_config,
    local_execution=True
)
```

---

# Hooks API

## Import Paths
```python
from tinyagent.hooks import RichUICallback, RichCodeUICallback, LoggingManager, TokenTracker
from tinyagent.hooks.gradio_callback import GradioCallback
from tinyagent.hooks.jupyter_notebook_callback import JupyterNotebookCallback
```

## UI Callbacks

### RichUICallback
Rich terminal UI callback for TinyAgent with live display capabilities.

```python
rich_ui = RichUICallback(markdown=True, show_thinking=True)
agent.add_callback(rich_ui)
```

### GradioCallback
Web-based UI callback using Gradio for interactive chat interface.

```python
gradio_ui = GradioCallback(
    file_upload_folder="./uploads",
    allowed_file_types=[".pdf", ".txt", ".docx"],
    show_thinking=True
)
agent.add_callback(gradio_ui)
gradio_ui.launch(agent, share=True, server_port=7860)
```

### JupyterNotebookCallback
Interactive Jupyter notebook UI with ipywidgets.

```python
jupyter_ui = JupyterNotebookCallback(auto_display=True, max_turns=50)
agent.add_callback(jupyter_ui)
```

## Utilities

### LoggingManager
Granular logging control for TinyAgent modules.

```python
log_manager = LoggingManager(default_level=logging.INFO)
log_manager.set_levels({
    'tinyagent.tiny_agent': logging.DEBUG,
    'tinyagent.mcp_client': logging.INFO,
})

agent_logger = log_manager.get_logger('tinyagent.tiny_agent')
agent = TinyAgent(model="gpt-4", logger=agent_logger)
```

### TokenTracker
Comprehensive token and cost tracking.

```python
from tinyagent.hooks import create_token_tracker

tracker = create_token_tracker(name="main_agent")
agent.add_callback(tracker)

# Get usage statistics
total_usage = tracker.get_total_usage()
print(f"Total cost: ${total_usage.cost:.4f}")
print(f"Total tokens: {total_usage.total_tokens}")
```

---

# Storage API

## Import Paths
```python
from tinyagent.storage import Storage, JsonFileStorage, SqliteStorage, PostgresStorage, RedisStorage
```

## Base Storage Interface

### Storage (Abstract Base Class)
```python
class Storage(ABC):
    @abstractmethod
    async def save_session(self, session_id: str, data: Dict[str, Any], user_id: Optional[str] = None) -> None:
        """Persist the given agent state under session_id."""
        
    @abstractmethod
    async def load_session(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve the agent state for session_id, or return {} if not found."""
        
    @abstractmethod
    async def close(self) -> None:
        """Clean up any resources."""
        
    def attach(self, agent: "TinyAgent") -> None:
        """Hook this storage to a TinyAgent for auto-persistence."""
```

## Storage Implementations

### JsonFileStorage
Persist TinyAgent sessions as individual JSON files.

```python
storage = JsonFileStorage(base_dir="./sessions")
agent = TinyAgent(storage=storage)
```

### SqliteStorage
Persist TinyAgent sessions in a SQLite database.

```python
storage = SqliteStorage(db_path="./sessions.db")
agent = TinyAgent(storage=storage)
```

### PostgresStorage
Persist TinyAgent sessions in a Postgres table with JSONB state.

```python
storage = PostgresStorage(
    host="localhost",
    port=5432,
    database="tinyagent",
    user="user",
    password="password"
)
agent = TinyAgent(storage=storage)
```

### RedisStorage
Persist TinyAgent sessions in Redis with optional TTL.

```python
storage = RedisStorage(
    host="localhost",
    port=6379,
    db=0,
    ttl=3600  # 1 hour expiration
)
agent = TinyAgent(storage=storage)
```

---

# MCP Client API

## Import Path
```python
from tinyagent.mcp_client import MCPClient
```

## MCPClient Class

Model Context Protocol client for connecting to MCP servers.

### Constructor
```python
MCPClient(logger: Optional[logging.Logger] = None)
```

### Core Methods

#### `async connect(command: str, args: List[str])`
Launches the MCP server subprocess and initializes the client session.
```python
client = MCPClient()
await client.connect("python", ["-m", "mcp_server"])
```

#### `async list_tools()`
List available tools from the MCP server.
```python
tools = await client.list_tools()
```

#### `async call_tool(name: str, arguments: dict)`
Invoke a named tool and return its raw content.
```python
result = await client.call_tool("file_read", {"path": "/path/to/file"})
```

#### `add_callback(callback: callable) -> None`
Add a callback function to the client.
```python
client.add_callback(my_callback)
```

#### `async close()`
Clean up subprocess and streams.
```python
await client.close()
```

---

# Usage Examples

## Basic Agent Usage
```python
import asyncio
from tinyagent import TinyAgent
from tinyagent.hooks import RichUICallback

async def main():
    agent = TinyAgent(
        model="gpt-4.1-mini",
        api_key="your-openai-api-key"
    )
    
    # Add rich UI for better visualization
    rich_ui = RichUICallback(markdown=True, show_thinking=True)
    agent.add_callback(rich_ui)
    
    try:
        result = await agent.run("What is the capital of France?")
        print(result)
    finally:
        await agent.close()

asyncio.run(main())
```

## Code Agent Usage
```python
import asyncio
from tinyagent.code_agent import TinyCodeAgent

async def main():
    agent = TinyCodeAgent(
        model="gpt-4.1-mini",
        api_key="your-api-key",
        provider="modal",
        local_execution=False
    )
    
    try:
        result = await agent.run("Create a simple data visualization with matplotlib")
        print(result)
    finally:
        await agent.close()

asyncio.run(main())
```

## Agent with Persistent Storage
```python
import asyncio
from tinyagent import TinyAgent
from tinyagent.storage import JsonFileStorage

async def main():
    storage = JsonFileStorage("./sessions")
    
    agent = TinyAgent(
        model="gpt-4.1-mini",
        api_key="your-api-key",
        storage=storage,
        session_id="user_123_session",
        load_session_on_init=True
    )
    
    try:
        result = await agent.run("Continue our previous conversation")
        print(result)
    finally:
        await agent.close()
        await storage.close()

asyncio.run(main())
```

## Custom Tools
```python
import asyncio
from tinyagent import TinyAgent, tool

@tool("weather", "Get weather information for a city")
def get_weather(city: str) -> str:
    # Your weather API logic here
    return f"The weather in {city} is sunny and 25°C"

@tool("calculator", "Perform mathematical calculations")
def calculate(expression: str) -> str:
    try:
        result = eval(expression)  # Note: Use safely in production
        return str(result)
    except Exception as e:
        return f"Error: {e}"

async def main():
    agent = TinyAgent(
        model="gpt-4.1-mini",
        api_key="your-api-key"
    )
    
    agent.add_tools([get_weather, calculate])
    
    try:
        result = await agent.run("What's the weather in Tokyo and what's 15 * 23?")
        print(result)
    finally:
        await agent.close()

asyncio.run(main())
```

---

# Key Features

- **Minimal but Powerful**: Simple API with advanced capabilities
- **MCP Integration**: Connect to Model Context Protocol servers
- **Code Execution**: Secure sandboxed Python code execution
- **Session Persistence**: Multiple storage backends (JSON, SQLite, PostgreSQL, Redis)
- **Memory Management**: Intelligent conversation history optimization
- **Extensible Hooks**: Rich UI callbacks, logging, token tracking
- **Custom Tools**: Easy tool creation with decorators
- **Async/Await**: Full async support for scalable applications
- **Error Handling**: Robust error handling and recovery
- **Multi-Provider**: Support for different LLM providers via LiteLLM

