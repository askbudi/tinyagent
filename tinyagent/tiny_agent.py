# Import LiteLLM for model interaction
import litellm
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from .mcp_client import MCPClient
import asyncio
import tiktoken  # Add tiktoken import for token counting

# Module-level logger; configuration is handled externally.
logger = logging.getLogger(__name__)
#litellm.callbacks = ["arize_phoenix"]



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
    
    async def connect_to_server(self, command: str, args: List[str]) -> None:
        """
        Connect to an MCP server and fetch available tools.
        
        Args:
            command: The command to run the server
            args: List of arguments for the server
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
        for tool in resp.tools:
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
        
        self.logger.info(f"Connected to {command} {args!r}, added {len(resp.tools)} tools")
        self.logger.debug(f"{command} {args!r} Available tools: {self.available_tools}")
    
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
                                # **New**: dispatch to the proper MCPClient
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
