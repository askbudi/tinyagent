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
        prop_schema = {"description": ""}
        
        # Map Python types to JSON schema types
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

class TinyAgent:
    """
    A minimal implementation of an agent powered by MCP and LiteLLM.
    This agent is literally just a while loop on top of MCPClient.
    """
    
    def __init__(self, model: str = "gpt-4.1-mini", api_key: Optional[str] = None, 
                system_prompt: Optional[str] = None, temperature: float = 0.0, logger: Optional[logging.Logger] = None,model_kwargs: Optional[Dict[str, Any]] = {}):
        """
        Initialize the Tiny Agent.
        
        Args:
            model: The model to use with LiteLLM
            api_key: The API key for the model provider
            system_prompt: Custom system prompt for the agent
            logger: Optional logger to use
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
        if api_key:
            litellm.api_key = api_key
        
        self.model_kwargs = model_kwargs
            
        # Conversation state
        self.messages = [{
            "role": "system",
            "content": system_prompt or (
                "You are a helpful AI assistant with access to a variety of tools. "
                "Use the tools when appropriate to accomplish tasks. "
                "If a tool you need isn't available, just say so."
            )
        }]
        
        # This list now accumulates tools from *all* connected MCP servers:
        self.available_tools: List[Dict[str, Any]] = []
        
        # Control flow tools
        self.exit_loop_tools = [
            {
                "type": "function",
                "function": {
                    "name": "task_complete",
                    "description": "Call this tool when the task given by the user is complete",
                    "parameters": {"type": "object", "properties": {}}
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
        
        self.logger.debug("TinyAgent initialized")
    
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
            return f"Error executing tool {tool_name}: {str(e)}"
    
    async def run(self, user_input: str, max_turns: int = 10) -> str:
        """
        Run the agent with user input.
        
        Args:
            user_input: The user's request
            max_turns: Maximum number of turns before giving up
            
        Returns:
            The final agent response
        """
        # Notify start
        await self._run_callbacks("agent_start", user_input=user_input)
        
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_input})
        await self._run_callbacks("message_add", message=self.messages[-1])
        
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

                # If there's textual content, emit it as its own assistant message
                if content:
                    content_msg = {
                        "role": "assistant",
                        "content": content
                    }
                    self.messages.append(content_msg)
                    await self._run_callbacks("message_add", message=content_msg)

                # Now emit the "assistant" message that carries the function call (or, if no calls, the content)
                if has_tool_calls:
                    assistant_msg = {
                        "role": "assistant",
                        "content": "",            # split off above
                        "tool_calls": tool_calls
                    }
                else:
                    assistant_msg = {
                        "role": "assistant",
                        "content": content
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
                            "content": ""  # Default empty content
                        }
                        
                        try:
                            # Parse tool arguments
                            try:
                                tool_args = json.loads(function_info.arguments)
                            except json.JSONDecodeError:
                                self.logger.error(f"Could not parse tool arguments: {function_info.arguments}")
                                tool_args = {}
                            
                            # Handle control flow tools
                            if tool_name == "task_complete":
                                # Add a response for this tool call before returning
                                tool_message["content"] = "Task has been completed successfully."
                                self.messages.append(tool_message)
                                await self._run_callbacks("agent_end", result="Task completed.")
                                return "Task completed."
                            elif tool_name == "ask_question":
                                question = tool_args.get("question", "Could you provide more details?")
                                # Add a response for this tool call before returning
                                tool_message["content"] = f"Question asked: {question}"
                                self.messages.append(tool_message)
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
                    if next_turn_should_call_tools and num_turns > 0:
                        # If we expected tool calls but didn't get any, we're done
                        await self._run_callbacks("agent_end", result=assistant_msg["content"] or "")
                        return assistant_msg["content"] or ""
                    
                    next_turn_should_call_tools = True
                
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
        """Clean up *all* MCP clients."""
        for client in self.mcp_clients:
            try:
                await client.close()
            except RuntimeError as e:
                self.logger.error(f"Error closing MCP client: {str(e)}")
                # Continue closing other clients even if one fails

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
    agent = TinyAgent(model="gpt-4.1-mini", api_key=api_key, logger=agent_logger)
    
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
    
    agent_logger.info(f"Final result: {result}")
    
    # Clean up
    await agent.close()
    agent_logger.debug("Example completed")
