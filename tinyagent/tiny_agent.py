# Import LiteLLM for model interaction
import litellm
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Callable, Union, Type, get_type_hints
from .mcp_client import MCPClient
import asyncio
import tiktoken  # Add tiktoken import for token counting
import inspect
import functools
import uuid
from .storage import Storage    # ← your abstract base
import traceback
import time  # Add time import for Unix timestamps
# Module-level logger; configuration is handled externally.
logger = logging.getLogger(__name__)
#litellm.callbacks = ["arize_phoenix"]

def tool(name: Optional[str] = None, description: Optional[str] = None, 
         schema: Optional[Dict[str, Any]] = None):
    """
    Decorator to convert a Python function or class into a tool for TinyAgent.
    
    Args:
        name: Optional custom name for the tool (defaults to function/class name)
        description: Optional description (defaults to function/class docstring)
        schema: Optional JSON schema for the tool parameters (auto-generated if not provided)
        
    Returns:
        Decorated function or class with tool metadata
    """
    def decorator(func_or_class):
        # Determine if we're decorating a function or class
        is_class = inspect.isclass(func_or_class)
        
        # Get the name (use provided name or function/class name)
        tool_name = name or func_or_class.__name__
        
        # Get the description (use provided description or docstring)
        tool_description = description or inspect.getdoc(func_or_class) or f"Tool based on {tool_name}"
        
        # Temporarily attach the description to the function/class
        # This allows _generate_schema_from_function to access it for param extraction
        if description:
            func_or_class._temp_tool_description = description
        
        # Generate schema if not provided
        tool_schema = schema or {}
        if not tool_schema:
            if is_class:
                # For classes, look at the __init__ method
                init_method = func_or_class.__init__
                tool_schema = _generate_schema_from_function(init_method)
            else:
                # For functions, use the function itself
                tool_schema = _generate_schema_from_function(func_or_class)
        
        # Clean up temporary attribute
        if hasattr(func_or_class, '_temp_tool_description'):
            delattr(func_or_class, '_temp_tool_description')
        
        # Attach metadata to the function or class
        func_or_class._tool_metadata = {
            "name": tool_name,
            "description": tool_description,
            "schema": tool_schema,
            "is_class": is_class
        }
        
        return func_or_class
    
    return decorator

def _generate_schema_from_function(func: Callable) -> Dict[str, Any]:
    """
    Generate a JSON schema for a function based on its signature and type hints.
    
    Args:
        func: The function to analyze
        
    Returns:
        A JSON schema object for the function parameters
    """
    # Get function signature and type hints
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    
    # Extract parameter descriptions from docstring
    param_descriptions = {}
    
    # First check if we have a tool decorator description (has higher priority)
    decorator_description = None
    if hasattr(func, '_temp_tool_description'):
        decorator_description = func._temp_tool_description
    
    # Get function docstring
    docstring = inspect.getdoc(func) or ""
    
    # Combine sources to check for parameter descriptions
    sources_to_check = []
    if decorator_description:
        sources_to_check.append(decorator_description)
    if docstring:
        sources_to_check.append(docstring)
    
    # Parse parameter descriptions from all sources
    for source in sources_to_check:
        lines = source.split('\n')
        in_args_section = False
        current_param = None
        
        for line in lines:
            line = line.strip()
            
            # Check for Args/Parameters section markers
            if line.lower() in ('args:', 'arguments:', 'parameters:'):
                in_args_section = True
                continue
                
            # Check for other section markers that would end the args section
            if line.lower() in ('returns:', 'raises:', 'yields:', 'examples:') and in_args_section:
                in_args_section = False
                
            # Look for :param or :arg style parameter descriptions
            if line.startswith((":param", ":arg")):
                try:
                    # e.g., ":param user_id: The ID of the user."
                    parts = line.split(" ", 2)
                    if len(parts) >= 3:
                        param_name = parts[1].strip().split(" ")[0]
                        param_descriptions[param_name] = parts[2].strip()
                except (ValueError, IndexError):
                    continue
                    
            # Look for indented parameter descriptions in Args section
            elif in_args_section and line.strip():
                # Check for param: description pattern
                param_match = line.lstrip().split(":", 1)
                if len(param_match) == 2:
                    param_name = param_match[0].strip()
                    description = param_match[1].strip()
                    param_descriptions[param_name] = description
                    current_param = param_name
                # Check for continued description from previous param
                elif current_param and line.startswith((' ', '\t')):
                    param_descriptions[current_param] += " " + line.strip()
    # Skip 'self' parameter for methods
    params = {
        name: param for name, param in sig.parameters.items() 
        if name != 'self' and name != 'cls'
    }
    
    # Build properties dictionary
    properties = {}
    required = []
    
    for name, param in params.items():
        # Get parameter type
        param_type = type_hints.get(name, Any)
        
        # Create property schema
        prop_schema = {}
        description = param_descriptions.get(name)
        if description:
            prop_schema["description"] = description
        
        # Handle different types of type annotations
        if param_type == str:
            prop_schema["type"] = "string"
        elif param_type == int:
            prop_schema["type"] = "integer"
        elif param_type == float:
            prop_schema["type"] = "number"
        elif param_type == bool:
            prop_schema["type"] = "boolean"
        elif param_type == list or param_type == List:
            prop_schema["type"] = "array"
        elif param_type == dict or param_type == Dict:
            prop_schema["type"] = "object"
        else:
            # Handle generic types
            origin = getattr(param_type, "__origin__", None)
            args = getattr(param_type, "__args__", None)
            
            if origin is not None and args is not None:
                # Handle List[X], Sequence[X], etc.
                if origin in (list, List) or (hasattr(origin, "__name__") and "List" in origin.__name__):
                    prop_schema["type"] = "array"
                    # Add items type if we can determine it
                    if args and len(args) == 1:
                        item_type = args[0]
                        if item_type == str:
                            prop_schema["items"] = {"type": "string"}
                        elif item_type == int:
                            prop_schema["items"] = {"type": "integer"}
                        elif item_type == float:
                            prop_schema["items"] = {"type": "number"}
                        elif item_type == bool:
                            prop_schema["items"] = {"type": "boolean"}
                        else:
                            prop_schema["items"] = {"type": "string"}
                
                # Handle Dict[K, V], Mapping[K, V], etc.
                elif origin in (dict, Dict) or (hasattr(origin, "__name__") and "Dict" in origin.__name__):
                    prop_schema["type"] = "object"
                    # We could add additionalProperties for value type, but it's not always needed
                    if args and len(args) == 2:
                        value_type = args[1]
                        if value_type == str:
                            prop_schema["additionalProperties"] = {"type": "string"}
                        elif value_type == int:
                            prop_schema["additionalProperties"] = {"type": "integer"}
                        elif value_type == float:
                            prop_schema["additionalProperties"] = {"type": "number"}
                        elif value_type == bool:
                            prop_schema["additionalProperties"] = {"type": "boolean"}
                        else:
                            prop_schema["additionalProperties"] = {"type": "string"}
                
                # Handle Union types (Optional is Union[T, None])
                elif origin is Union:
                    # Check if this is Optional[X] (Union[X, None])
                    if type(None) in args:
                        # Get the non-None type
                        non_none_types = [arg for arg in args if arg is not type(None)]
                        if non_none_types:
                            # Use the first non-None type
                            main_type = non_none_types[0]
                            # Recursively process this type
                            if main_type == str:
                                prop_schema["type"] = "string"
                            elif main_type == int:
                                prop_schema["type"] = "integer"
                            elif main_type == float:
                                prop_schema["type"] = "number"
                            elif main_type == bool:
                                prop_schema["type"] = "boolean"
                            elif main_type == list or main_type == List:
                                prop_schema["type"] = "array"
                            elif main_type == dict or main_type == Dict:
                                prop_schema["type"] = "object"
                            else:
                                # Try to handle generic types like List[str]
                                inner_origin = getattr(main_type, "__origin__", None)
                                inner_args = getattr(main_type, "__args__", None)
                                
                                if inner_origin is not None and inner_args is not None:
                                    if inner_origin in (list, List) or (hasattr(inner_origin, "__name__") and "List" in inner_origin.__name__):
                                        prop_schema["type"] = "array"
                                        if inner_args and len(inner_args) == 1:
                                            inner_item_type = inner_args[0]
                                            if inner_item_type == str:
                                                prop_schema["items"] = {"type": "string"}
                                            elif inner_item_type == int:
                                                prop_schema["items"] = {"type": "integer"}
                                            elif inner_item_type == float:
                                                prop_schema["items"] = {"type": "number"}
                                            elif inner_item_type == bool:
                                                prop_schema["items"] = {"type": "boolean"}
                                            else:
                                                prop_schema["items"] = {"type": "string"}
                                    elif inner_origin in (dict, Dict) or (hasattr(inner_origin, "__name__") and "Dict" in inner_origin.__name__):
                                        prop_schema["type"] = "object"
                                        # Add additionalProperties for value type
                                        if inner_args and len(inner_args) == 2:
                                            value_type = inner_args[1]
                                            if value_type == str:
                                                prop_schema["additionalProperties"] = {"type": "string"}
                                            elif value_type == int:
                                                prop_schema["additionalProperties"] = {"type": "integer"}
                                            elif value_type == float:
                                                prop_schema["additionalProperties"] = {"type": "number"}
                                            elif value_type == bool:
                                                prop_schema["additionalProperties"] = {"type": "boolean"}
                                            else:
                                                prop_schema["additionalProperties"] = {"type": "string"}
                                    else:
                                        prop_schema["type"] = "string"  # Default for complex types
                                else:
                                    prop_schema["type"] = "string"  # Default for complex types
                    else:
                        # For non-Optional Union types, default to string
                        prop_schema["type"] = "string"
                else:
                    prop_schema["type"] = "string"  # Default for other complex types
            else:
                prop_schema["type"] = "string"  # Default to string for complex types
        
        properties[name] = prop_schema
        
        # Check if parameter is required
        if param.default == inspect.Parameter.empty:
            required.append(name)
    
    # Build the final schema
    schema = {
        "type": "object",
        "properties": properties
    }
    
    if required:
        schema["required"] = required
    
    return schema

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant with access to a variety of tools. "
    "Use the tools when appropriate to accomplish tasks. "
    "If a tool you need isn't available, just say so."
)

DEFAULT_SUMMARY_SYSTEM_PROMPT = (
    "You are an expert assistant. Your goal is to generate a concise, structured summary "
    "of the conversation below that captures all essential information needed to continue "
    "development after context replacement. Include tasks performed, code areas modified or "
    "reviewed, key decisions or assumptions, test results or errors, and outstanding tasks or next steps."
)

class TinyAgent:
    """
    A minimal implementation of an agent powered by MCP and LiteLLM,
    now with session/state persistence.
    """
    session_state: Dict[str, Any] = {}
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        logger: Optional[logging.Logger] = None,
        model_kwargs: Optional[Dict[str, Any]] = {},
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        storage: Optional[Storage] = None,
        persist_tool_configs: bool = False,
        summary_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the Tiny Agent.
        
        Args:
            model: The model to use with LiteLLM
            api_key: The API key for the model provider
            system_prompt: Custom system prompt for the agent
            logger: Optional logger to use
            session_id: Optional session ID (if provided with storage, will attempt to load existing session)
            metadata: Optional metadata for the session
            storage: Optional storage backend for persistence
            persist_tool_configs: Whether to persist tool configurations
            summary_model: Optional model to use for generating conversation summaries
            summary_system_prompt: Optional system prompt for the summary model
        """
        # Set up logger
        self.logger = logger or logging.getLogger(__name__)
        
        # Instead of a single MCPClient, keep multiple:
        self.mcp_clients: List[MCPClient] = []
        # Map from tool_name -> MCPClient instance
        self.tool_to_client: Dict[str, MCPClient] = {}
        
        # Simplified hook system - single list of callbacks
        self.callbacks: List[callable] = []
        
        # LiteLLM configuration
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        if model in ["o1", "o1-preview","o3","o4-mini"]:
            self.temperature = 1

        
        self.model_kwargs = model_kwargs
        self.encoder = tiktoken.get_encoding("o200k_base")
            
        # Conversation state
        self.messages = [{
            "role": "system",
            "content": system_prompt or DEFAULT_SYSTEM_PROMPT
        }]
        
        self.summary_config = summary_config or {}
        
        # This list now accumulates tools from *all* connected MCP servers:
        self.available_tools: List[Dict[str, Any]] = []
        
        # Control flow tools
        self.exit_loop_tools = [
            {
                "type": "function",
                "function": {
                    "name": "final_answer",
                    "description": "Call this tool when the task given by the user is complete",
                    "parameters": {"type": "object", "properties": {"content": {
                                "type": "string",
                                "description": "Your final answer to the user's problem, user only sees the content of this field. "
                            }}}
                            ,
                        "required": ["content"]
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "ask_question",
                    "description": "Ask a question to the user to get more info required to solve or clarify their problem.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The question to ask the user"
                            }
                        },
                        "required": ["question"]
                    }
                }
            }
        ]
        
        # Add a list to store custom tools (functions and classes)
        self.custom_tools: List[Dict[str, Any]] = []
        self.custom_tool_handlers: Dict[str, Any] = {}
        # 1) User and session management
        self.user_id = user_id or self._generate_session_id()
        self.session_id = session_id or self._generate_session_id()
        # build default metadata
        default_md = {
            "model": model,
            "temperature": temperature,
            **(model_kwargs or {}),
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        }
        self.metadata = metadata or default_md
        self.metadata.setdefault("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

        # 2) Storage is attached immediately for auto‐saving, but loading is deferred:
        self.storage = storage
        self.persist_tool_configs = persist_tool_configs
        # only a flag — no blocking or hidden runs in __init__
        self._needs_session_load = bool(self.storage and session_id)

        if self.storage:
            # register auto‐save on llm_end
            self.storage.attach(self)

        self.logger.debug(f"TinyAgent initialized (session={self.session_id})")
        
        # register our usage‐merging hook
        self.add_callback(self._on_llm_end)
    
    def _generate_session_id(self) -> str:
        """Produce a unique session identifier."""
        return str(uuid.uuid4())

    def count_tokens(self, text: str) -> int:
            """Count tokens in a string using tiktoken."""
            if not self.encoder or not text:
                return 0
            try:
                return len(self.encoder.encode(text))
            except Exception as e:
                self.logger.error(f"Error counting tokens: {e}")
                return 0
            
    async def save_agent(self) -> None:
        """Persist our full serialized state via the configured Storage."""
        if not self.storage:
            self.logger.warning("No storage configured; skipping save.")
            return
        data = self.to_dict()
        await self.storage.save_session(self.session_id, data, self.user_id)
        self.logger.info(f"Agent state saved for session={self.session_id}")

    async def _on_llm_end(self, event_name: str, agent: "TinyAgent", **kwargs) -> None:
        """
        Callback hook: after each LLM call, accumulate *all* fields from
        litellm's response.usage into our metadata and persist.
        """
        if event_name != "llm_end":
            return

        response = kwargs.get("response")
        if response and hasattr(response, "usage") and isinstance(response.usage, dict):
            usage = response.usage
            bucket = self.metadata.setdefault(
                "usage", {}
            )
            # Merge every key from the LLM usage (prompt_tokens, completion_tokens,
            # total_tokens, maybe cost, etc.)
            for field, value in usage.items():
                try:
                    # only aggregate numeric fields
                    bucket[field] = bucket.get(field, 0) + int(value)
                except (ValueError, TypeError):
                    # fallback: overwrite or store as-is
                    bucket[field] = value

        # persist after each LLM call
        await self.save_agent()

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize session_id, metadata, and a user‐extensible session_state.
        """
        # start from user's own session_state
        session_data = dict(self.session_state)
        # always include the conversation
        session_data["messages"] = self.messages

        # optionally include tools
        if self.persist_tool_configs:
            serialized = []
            for cfg in getattr(self, "_tool_configs_for_serialization", []):
                if cfg["type"] == "tiny_agent":
                    serialized.append({
                        "type": "tiny_agent",
                        "state": cfg["state_func"]()
                    })
                else:
                    serialized.append(cfg)
            session_data["tool_configs"] = serialized

        return {
            "session_id": self.session_id,
            "metadata": self.metadata,
            "session_state": session_data
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        logger: Optional[logging.Logger] = None,
        tool_registry: Optional[Dict[str, Any]] = None,
        storage: Optional[Storage] = None
    ) -> "TinyAgent":
        """
        Rehydrate a TinyAgent from JSON state.
        """
        session_id = data["session_id"]
        metadata   = data.get("metadata", {})
        state_blob = data.get("session_state", {})

        # core config
        model       = metadata.get("model", "gpt-4.1-mini")
        temperature = metadata.get("temperature", 0.0)
        # everything else except model/temperature/usage → model_kwargs
        model_kwargs = {k:v for k,v in metadata.items() if k not in ("model","temperature","usage")}

        # instantiate (tools* not yet reconstructed)
        agent = cls(
            model=model,
            api_key=None,
            system_prompt=None,
            temperature=temperature,
            logger=logger,
            model_kwargs=model_kwargs,
            session_id=session_id,
            metadata=metadata,
            storage=storage,
            persist_tool_configs=False   # default off
        )

        # Apply the session data directly instead of loading from storage
        agent._needs_session_load = False
        agent._apply_session_data(data)

        # rebuild tools if we persisted them
        agent.tool_registry = tool_registry or {}
        for tcfg in state_blob.get("tool_configs", []):
            agent._reconstruct_tool(tcfg)

        return agent
    
    def add_callback(self, callback: callable) -> None:
        """
        Add a callback function to the agent.
        
        Args:
            callback: A function that accepts (event_name, agent, **kwargs)
        """
        self.callbacks.append(callback)
    
    async def _run_callbacks(self, event_name: str, **kwargs) -> None:
        """
        Run all registered callbacks for an event.
        
        Args:
            event_name: The name of the event
            **kwargs: Additional data for the event
        """
        for callback in self.callbacks:
            try:
                self.logger.debug(f"Running callback: {callback}")
                if asyncio.iscoroutinefunction(callback):
                    self.logger.debug(f"Callback is a coroutine function")
                    await callback(event_name, self, **kwargs)
                else:
                    # Check if the callback is a class with an async __call__ method
                    if hasattr(callback, '__call__') and asyncio.iscoroutinefunction(callback.__call__):
                        self.logger.debug(f"Callback is a class with an async __call__ method")  
                        await callback(event_name, self, **kwargs)
                    else:
                        self.logger.debug(f"Callback is a regular function")
                        callback(event_name, self, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in callback for {event_name}: {str(e)}")
    
    async def connect_to_server(self, command: str, args: List[str], 
                               include_tools: Optional[List[str]] = None, 
                               exclude_tools: Optional[List[str]] = None) -> None:
        """
        Connect to an MCP server and fetch available tools.
        
        Args:
            command: The command to run the server
            args: List of arguments for the server
            include_tools: Optional list of tool name patterns to include (if provided, only matching tools will be added)
            exclude_tools: Optional list of tool name patterns to exclude (matching tools will be skipped)
        """
        # 1) Create and connect a brand-new client
        client = MCPClient()
        
        # Pass our callbacks to the client
        for callback in self.callbacks:
            client.add_callback(callback)
        
        await client.connect(command, args)
        self.mcp_clients.append(client)
        
        # 2) List tools on *this* server
        resp = await client.session.list_tools()
        
        # 3) For each tool, record its schema + map name->client
        added_tools = 0
        for tool in resp.tools:
            # Apply filtering logic
            tool_name = tool.name
            
            # Skip if not in include list (when include list is provided)
            if include_tools and not any(pattern in tool_name for pattern in include_tools):
                self.logger.debug(f"Skipping tool {tool_name} - not in include list")
                continue
                
            # Skip if in exclude list
            if exclude_tools and any(pattern in tool_name for pattern in exclude_tools):
                self.logger.debug(f"Skipping tool {tool_name} - matched exclude pattern")
                continue
            
            fn_meta = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            self.available_tools.append(fn_meta)
            self.tool_to_client[tool.name] = client
            added_tools += 1
        
        self.logger.info(f"Connected to {command} {args!r}, added {added_tools} tools (filtered from {len(resp.tools)} available)")
        self.logger.debug(f"{command} {args!r} Available tools: {self.available_tools}")
    
    def add_tool(self, tool_func_or_class: Any) -> None:
        """
        Add a custom tool (function or class) to the agent.
        
        Args:
            tool_func_or_class: A function or class decorated with @tool
        """
        # Check if the tool has the required metadata
        if not hasattr(tool_func_or_class, '_tool_metadata'):
            raise ValueError("Tool must be decorated with @tool decorator")
        
        metadata = tool_func_or_class._tool_metadata
        
        # Create tool schema
        tool_schema = {
            "type": "function",
            "function": {
                "name": metadata["name"],
                "description": metadata["description"],
                "parameters": metadata["schema"]
            }
        }
        
        # Add to available tools
        self.custom_tools.append(tool_schema)
        self.available_tools.append(tool_schema)
        
        # Store the handler (function or class)
        self.custom_tool_handlers[metadata["name"]] = tool_func_or_class
        
        self.logger.info(f"Added custom tool: {metadata['name']}")
    
    def add_tools(self, tools: List[Any]) -> None:
        """
        Add multiple custom tools to the agent.
        
        Args:
            tools: List of functions or classes decorated with @tool
        """
        for tool_func_or_class in tools:
            self.add_tool(tool_func_or_class)
    
    async def _execute_custom_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        """
        Execute a custom tool and return its result.
        
        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
            
        Returns:
            String result from the tool
        """
        handler = self.custom_tool_handlers.get(tool_name)
        if not handler:
            return f"Error: Tool '{tool_name}' not found"
        
        try:
            # Check if it's a class or function
            metadata = handler._tool_metadata
            
            if metadata["is_class"]:
                # Instantiate the class and call it
                instance = handler(**tool_args)
                if hasattr(instance, "__call__"):
                    result = instance()
                else:
                    result = instance
            else:
                # Call the function directly
                result = handler(**tool_args)
            
            # Handle async functions
            if asyncio.iscoroutine(result):
                result = await result
                
            return str(result)
        except Exception as e:
            self.logger.error(f"Error executing custom tool {tool_name}: {str(e)}")
            self.logger.error(f"Error: {traceback.format_exc()}")
            return f"Error executing tool {tool_name}: {str(e)}"
    
    async def run(self, user_input: str, max_turns: int = 10) -> str:
        # ----------------------------------------------------------------
        # Ensure any deferred session‐load happens exactly once
        # ----------------------------------------------------------------
        if self._needs_session_load:
            self.logger.debug(f"Deferred session load detected for {self.session_id}; loading now")
        await self.init_async()

        # ----------------------------------------------------------------
        # Now proceed with the normal agent loop
        # ----------------------------------------------------------------

        # Notify start
        await self._run_callbacks("agent_start", user_input=user_input)
        
        # Add user message to conversation with timestamp
        user_message = {
            "role": "user", 
            "content": user_input,
            "created_at": int(time.time())
        }
        self.messages.append(user_message)
        await self._run_callbacks("message_add", message=self.messages[-1])
        
        return await self._run_agent_loop(max_turns)
    
    async def resume(self, max_turns: int = 10) -> str:
        """
        Resume the conversation without adding a new user message.
        
        This method continues the conversation from the current state,
        allowing the agent to process the existing conversation history
        and potentially take additional actions.
        
        Args:
            max_turns: Maximum number of conversation turns
            
        Returns:
            The agent's response
        """
        # Ensure any deferred session-load happens exactly once
        if self._needs_session_load:
            self.logger.debug(f"Deferred session load detected for {self.session_id}; loading now")
        await self.init_async()
        
        # Notify start with resume flag
        await self._run_callbacks("agent_start", resume=True)
        
        return await self._run_agent_loop(max_turns)
    
    async def _run_agent_loop(self, max_turns: int = 10) -> str:
        """
        Internal method that runs the agent's main loop.
        
        Args:
            max_turns: Maximum number of conversation turns
            
        Returns:
            The agent's response
        """
        # Initialize loop control variables
        num_turns = 0
        next_turn_should_call_tools = True
        
        # The main agent loop
        while True:
            # Get all available tools including exit loop tools
            all_tools = self.available_tools + self.exit_loop_tools
            
            # Call LLM with messages and tools
            try:
                self.logger.info(f"Calling LLM with {len(self.messages)} messages and {len(all_tools)} tools")
                
                # Notify LLM start
                await self._run_callbacks("llm_start", messages=self.messages, tools=all_tools)
                
                response = await litellm.acompletion(
                    model=self.model,
                    api_key=self.api_key,
                    messages=self.messages,
                    tools=all_tools,
                    tool_choice="auto",
                    temperature=self.temperature,
                    **self.model_kwargs
                )
                
                # Notify LLM end
                await self._run_callbacks("llm_end", response=response)
                
                # Process the response - properly handle the object
                response_message = response.choices[0].message
                self.logger.debug(f"🔥🔥🔥🔥🔥🔥 Response : {response_message}")
                
                # Extract both content and any tool_calls
                content = getattr(response_message, "content", "") or ""
                tool_calls = getattr(response_message, "tool_calls", []) or []
                has_tool_calls = bool(tool_calls)

                # Now emit the "assistant" message that carries the function call (or, if no calls, the content)
                if has_tool_calls:
                    assistant_msg = {
                        "role": "assistant",
                        "content": content,            # split off above
                        "tool_calls": tool_calls,
                        "created_at": int(time.time())
                    }
                else:
                    assistant_msg = {
                        "role": "assistant",
                        "content": content,
                        "created_at": int(time.time())
                    }
                self.messages.append(assistant_msg)
                await self._run_callbacks("message_add", message=assistant_msg)
                
                # Process tool calls if they exist
                if has_tool_calls:
                    self.logger.info(f"Tool calls detected: {len(tool_calls)}")
                    
                    # Process each tool call one by one
                    for tool_call in tool_calls:
                        tool_call_id = tool_call.id
                        function_info = tool_call.function
                        tool_name = function_info.name
                        
                        # Create a tool message
                        tool_message = {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "name": tool_name,
                            "content": "",  # Default empty content
                            "created_at": int(time.time())
                        }
                        
                        try:
                            # Parse tool arguments
                            try:
                                tool_args = json.loads(function_info.arguments)
                            except json.JSONDecodeError:
                                self.logger.error(f"Could not parse tool arguments: {function_info.arguments}")
                                tool_args = {}
                            
                            # Handle control flow tools
                            if tool_name == "final_answer":
                                # Add a response for this tool call before returning
                                tool_message["content"] = tool_args.get("content", "Task completed without final answer.!!!")
                                self.messages.append(tool_message)
                                await self._run_callbacks("message_add", message=tool_message)
                                await self._run_callbacks("agent_end", result="Task completed.")
                                return tool_message["content"] 
                            elif tool_name == "ask_question":
                                question = tool_args.get("question", "Could you provide more details?")
                                # Add a response for this tool call before returning
                                tool_message["content"] = f"Question asked: {question}"
                                self.messages.append(tool_message)
                                await self._run_callbacks("message_add", message=tool_message)
                                await self._run_callbacks("agent_end", result=f"I need more information: {question}")
                                return f"I need more information: {question}"
                            else:
                                # Check if it's a custom tool first
                                if tool_name in self.custom_tool_handlers:
                                    tool_message["content"] = await self._execute_custom_tool(tool_name, tool_args)
                                else:
                                    # Dispatch to the proper MCPClient
                                    client = self.tool_to_client.get(tool_name)
                                    if not client:
                                        tool_message["content"] = f"No MCP server registered for tool '{tool_name}'"
                                    else:
                                        try:
                                            self.logger.debug(f"Calling tool {tool_name} with args: {tool_args}")
                                            self.logger.debug(f"Client: {client}")
                                            content_list = await client.call_tool(tool_name, tool_args)
                                            self.logger.debug(f"Tool {tool_name} returned: {content_list}")
                                            # Safely extract text from the content
                                            if content_list:
                                                # Try different ways to extract the content
                                                if hasattr(content_list[0], 'text'):
                                                    tool_message["content"] = content_list[0].text
                                                elif isinstance(content_list[0], dict) and 'text' in content_list[0]:
                                                    tool_message["content"] = content_list[0]['text']
                                                else:
                                                    tool_message["content"] = str(content_list)
                                            else:
                                                tool_message["content"] = "Tool returned no content"
                                        except Exception as e:
                                            self.logger.error(f"Error calling tool {tool_name}: {str(e)}")
                                            tool_message["content"] = f"Error executing tool {tool_name}: {str(e)}"
                        except Exception as e:
                            # If any error occurs during tool call processing, make sure we still have a tool response
                            self.logger.error(f"Unexpected error processing tool call {tool_call_id}: {str(e)}")
                            tool_message["content"] = f"Error processing tool call: {str(e)}"
                        
                        # Always add the tool message to ensure each tool call has a response
                        self.messages.append(tool_message)
                        await self._run_callbacks("message_add", message=tool_message)
                    
                    next_turn_should_call_tools = False
                else:
                    # No tool calls in this message
                    # If the model provides a direct answer without tool calls, we should return it
                    # This handles the case where the LLM gives a direct answer without using tools
                    await self._run_callbacks("agent_end", result=assistant_msg["content"] or "")
                    return assistant_msg["content"] or ""
                
                num_turns += 1
                if num_turns >= max_turns:
                    result = "Max turns reached. Task incomplete."
                    await self._run_callbacks("agent_end", result=result)
                    return result
                
            except Exception as e:
                self.logger.error(f"Error in agent loop: {str(e)}")
                result = f"Error: {str(e)}"
                await self._run_callbacks("agent_end", result=result, error=str(e))
                return result

    
    async def close(self):
        """
        Clean up all resources used by the agent including MCP clients and storage.
        
        This method should be called when the agent is no longer needed to ensure
        proper resource cleanup, especially in web frameworks like FastAPI.
        """
        cleanup_errors = []
        
        # 1. First save any pending state if storage is configured
        if self.storage:
            try:
                self.logger.debug(f"Saving final state before closing (session={self.session_id})")
                await self.save_agent()
            except Exception as e:
                error_msg = f"Error saving final state: {str(e)}"
                self.logger.error(error_msg)
                cleanup_errors.append(error_msg)
        
        # 2. Close all MCP clients
        for client in self.mcp_clients:
            try:
                self.logger.debug(f"Closing MCP client: {client}")
                await client.close()
            except Exception as e:
                error_msg = f"Error closing MCP client: {str(e)}"
                self.logger.error(error_msg)
                cleanup_errors.append(error_msg)
        
        # 3. Close storage connection if available
        if self.storage:
            try:
                self.logger.debug("Closing storage connection")
                await self.storage.close()
            except Exception as e:
                error_msg = f"Error closing storage: {str(e)}"
                self.logger.error(error_msg)
                cleanup_errors.append(error_msg)
        
        # 4. Run any cleanup callbacks
        try:
            await self._run_callbacks("agent_cleanup")
        except Exception as e:
            error_msg = f"Error in cleanup callbacks: {str(e)}"
            self.logger.error(error_msg)
            cleanup_errors.append(error_msg)
        
        # Log summary of cleanup
        if cleanup_errors:
            self.logger.warning(f"TinyAgent cleanup completed with {len(cleanup_errors)} errors")
        else:
            self.logger.info(f"TinyAgent cleanup completed successfully (session={self.session_id})")

    def clear_conversation(self):
        """
        Clear the conversation history, preserving only the initial system prompt.
        """
        if self.messages:
            system_msg = self.messages[0]
        else:
            # Rebuild a default system prompt if somehow missing
            default_sys = {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant with access to a variety of tools. "
                    "Use the tools when appropriate to accomplish tasks. "
                    "If a tool you need isn't available, just say so."
                )
            }
            system_msg = default_sys
        self.messages = [system_msg]
        self.logger.info("TinyAgent conversation history cleared.")
        
    def as_tool(self, name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert this TinyAgent instance into a tool that can be used by another TinyAgent.
        
        Args:
            name: Optional custom name for the tool (defaults to "TinyAgentTool")
            description: Optional description (defaults to a generic description)
            
        Returns:
            A tool function that can be added to another TinyAgent
        """
        tool_name = name or f"TinyAgentTool_{id(self)}"
        tool_description = description or f"A tool that uses a TinyAgent with model {self.model} to solve tasks"
        
        @tool(name=tool_name, description=tool_description)
        async def agent_tool(query: str, max_turns: int = 5) -> str:
            """
            Run this TinyAgent with the given query.
            
            Args:
                query: The task or question to process
                max_turns: Maximum number of turns (default: 5)
                
            Returns:
                The agent's response
            """
            return await self.run(query, max_turns=max_turns)
        
        return agent_tool

    async def init_async(self) -> "TinyAgent":
        """
        Load session data from storage if flagged.  Safe to call only once.
        """
        if not self._needs_session_load:
            return self

        try:
            data = await self.storage.load_session(self.session_id, self.user_id)
            if data:
                self.logger.info(f"Resuming session {self.session_id}")
                self._apply_session_data(data)
            else:
                self.logger.info(f"No existing session for {self.session_id}")
        except Exception as e:
            self.logger.error(f"Failed to load session {self.session_id}: {traceback.format_exc()}")
        finally:
            self._needs_session_load = False

        return self

    @classmethod
    async def create(
        cls,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        logger: Optional[logging.Logger] = None,
        model_kwargs: Optional[Dict[str, Any]] = {},
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        storage: Optional[Storage] = None,
        persist_tool_configs: bool = False
    ) -> "TinyAgent":
        """
        Async factory: constructs the agent, then loads an existing session
        if (storage and session_id) were provided.
        """
        agent = cls(
            model=model,
            api_key=api_key,
            system_prompt=system_prompt,
            temperature=temperature,
            logger=logger,
            model_kwargs=model_kwargs,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            storage=storage,
            persist_tool_configs=persist_tool_configs
        )
        if agent._needs_session_load:
            await agent.init_async()
        return agent

    def _apply_session_data(self, data: Dict[str, Any]) -> None:
        """
        Apply loaded session data to this agent instance.
        
        Args:
            data: Session data dictionary from storage
        """
        # Update metadata (preserving model and temperature from constructor)
        if "metadata" in data:
            # Keep original model/temperature/api_key but merge everything else
            stored_metadata = data["metadata"]
            for key, value in stored_metadata.items():
                if key not in ("model", "temperature"):  # Don't override these
                    self.metadata[key] = value
        
        # Load session state
        if "session_state" in data:
            state_blob = data["session_state"]
            
            # Restore conversation history
            if "messages" in state_blob:
                self.messages = state_blob["messages"]
            
            # Restore other session state
            for key, value in state_blob.items():
                if key != "messages" and key != "tool_configs":
                    self.session_state[key] = value
            
            # Tool configs would be handled separately if needed

    async def summarize(self) -> str:
        """
        Generate a summary of the current conversation history.
        
        Args:
            custom_model: Optional model to use for summary generation (overrides self.summary_model)
            custom_system_prompt: Optional system prompt for summary generation (overrides self.summary_system_prompt)
            
        Returns:
            A string containing the conversation summary
        """
        # Skip if there are no messages or just the system message
        if len(self.messages) <= 1:
            return "No conversation to summarize."
        
        # Use provided parameters or defaults
        system_prompt = self.summary_config.get("system_prompt",DEFAULT_SUMMARY_SYSTEM_PROMPT)
        
        # Format the conversation into a single string
        conversation_text = self._format_conversation_for_summary()
        
        # Build the prompt for the summary model
        summary_messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f"Here is the conversation so far:\n{conversation_text}\n\nPlease summarize this conversation, covering:\n0. What is the task its requirments, goals and constraints\n1. Tasks performed and outcomes\n2. Code files, modules, or functions modified or examined\n3. Important decisions or assumptions made\n4. Errors encountered and test or build results\n5. Remaining tasks, open questions, or next steps\nProvide the summary in a clear, concise format."
            }
        ]
        
        try:
            # Log that we're generating a summary
            self.logger.info(f"Generating conversation summary using model {self.summary_config.get('model',self.model)}")
            
            # Call the LLM to generate the summary
            response = await litellm.acompletion(
                model=self.summary_config.get("model",self.model),
                api_key=self.summary_config.get("api_key",self.api_key),
                messages=summary_messages,
                temperature=self.summary_config.get("temperature",self.temperature),  # Use low temperature for consistent summaries
                max_tokens=self.summary_config.get("max_tokens",8000)   # Reasonable limit for summary length
            )
            
            # Extract the summary from the response
            summary = response.choices[0].message.content
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating conversation summary: {str(e)}")
            return f"Failed to generate summary: {str(e)}"
    
    async def compact(self) -> bool:
        """
        Compact the conversation history by replacing it with a summary.
        
        This method:
        1. Generates a summary of the current conversation
        2. If successful, replaces the conversation with just [system, user] messages
           where the user message contains the summary
        3. Returns True if compaction was successful, False otherwise
        
        Returns:
            Boolean indicating whether the compaction was successful
        """
        # Skip if there are no messages or just the system message
        if len(self.messages) <= 1:
            self.logger.info("No conversation to compact.")
            return False
        
        # Generate the summary
        summary = await self.summarize()
        
        # Check if the summary generation was successful
        if summary.startswith("Failed to generate summary:") or summary == "No conversation to summarize.":
            self.logger.error(f"Compaction failed: {summary}")
            return False
        
        # Save the system message
        system_message = self.messages[0]
        
        
        # Create a new user message with the summary
        summary_message = {
            "role": "user",
            "content": f"CONVERSATION SUMMARY:\n\n{summary}",
            "created_at": int(time.time())
        }
        
        # Replace the conversation with just [system, user] messages
        self.messages = [system_message, summary_message]
        
        # Notify about the compaction
        self.logger.info("🤐Conversation successfully compacted.")
        await self._run_callbacks("message_add", message=summary_message)
        
        return True
    
    def _format_conversation_for_summary(self) -> str:
        """
        Format the conversation history into a string for summarization.
        
        Returns:
            A string representing the conversation in the format:
            user: content
            assistant: content
            tool_call: tool name and args
            tool_response: response content
            ...
        """
        formatted_lines = []
        
        # Skip the system message (index 0)
        for message in self.messages[1:]:
            role = message.get("role", "unknown")
            
            if role == "user":
                formatted_lines.append(f"user: {message.get('content', '')}")
            
            elif role == "assistant":
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])
                
                # Add assistant message content if present
                if content:
                    formatted_lines.append(f"assistant: {content}")
                
                # Add tool calls if present
                for tool_call in tool_calls:
                    function_info = tool_call.get("function", {})
                    tool_name = function_info.get("name", "unknown_tool")
                    arguments = function_info.get("arguments", "{}")
                    
                    formatted_lines.append(f"tool_call: {tool_name} with args {arguments}")
            
            elif role == "tool":
                tool_name = message.get("name", "unknown_tool")
                content = message.get("content", "")
                formatted_lines.append(f"tool_response: {content}")
            
            else:
                # Handle any other message types
                formatted_lines.append(f"{role}: {message.get('content', '')}")
        
        return "\n".join(formatted_lines)

async def run_example():
    """Example usage of TinyAgent with proper logging."""
    import os
    import sys
    from tinyagent.hooks.logging_manager import LoggingManager
    from tinyagent.hooks.rich_ui_callback import RichUICallback
    
    # Create and configure logging manager
    log_manager = LoggingManager(default_level=logging.INFO)
    log_manager.set_levels({
        'tinyagent.tiny_agent': logging.DEBUG,  # Debug for this module
        'tinyagent.mcp_client': logging.INFO,
        'tinyagent.hooks.rich_ui_callback': logging.INFO,
    })
    
    # Configure a console handler
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    
    # Get module-specific loggers
    agent_logger = log_manager.get_logger('tinyagent.tiny_agent')
    ui_logger = log_manager.get_logger('tinyagent.hooks.rich_ui_callback')
    mcp_logger = log_manager.get_logger('tinyagent.mcp_client')
    
    agent_logger.debug("Starting TinyAgent example")
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        agent_logger.error("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Initialize the agent with our logger
    agent = await TinyAgent.create(
        model="gpt-4.1-mini",
        api_key=api_key,
        logger=agent_logger,
        session_id="my-session-123",
        storage=None
    )
    
    # Add the Rich UI callback with our logger
    rich_ui = RichUICallback(
        markdown=True,
        show_message=True,
        show_thinking=True,
        show_tool_calls=True,
        logger=ui_logger
    )
    agent.add_callback(rich_ui)
    
    # Run the agent with a user query
    user_input = "What is the capital of France?"
    agent_logger.info(f"Running agent with input: {user_input}")
    result = await agent.run(user_input)
    
    agent_logger.info(f"Initial result: {result}")
    
    # Now demonstrate the resume functionality
    agent_logger.info("Resuming the conversation without new user input")
    resume_result = await agent.resume(max_turns=3)
    
    agent_logger.info(f"Resume result: {resume_result}")
    
    # Clean up
    await agent.close()
    agent_logger.debug("Example completed")
