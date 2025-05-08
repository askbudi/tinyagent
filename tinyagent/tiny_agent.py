# Import LiteLLM for model interaction
import litellm
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from .mcp_client import MCPClient

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
#litellm.callbacks = ["arize_phoenix"]



class TinyAgent:
    """
    A minimal implementation of an agent powered by MCP and LiteLLM.
    This agent is literally just a while loop on top of MCPClient.
    """
    
    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None, system_prompt: Optional[str] = None):
        """
        Initialize the Tiny Agent.
        
        Args:
            model: The model to use with LiteLLM
            api_key: The API key for the model provider
            system_prompt: Custom system prompt for the agent
        """
        # Instead of a single MCPClient, keep multiple:
        self.mcp_clients: List[MCPClient] = []
        # Map from tool_name -> MCPClient instance
        self.tool_to_client: Dict[str, MCPClient] = {}
        
        # LiteLLM configuration
        self.model = model
        self.api_key = api_key
        if api_key:
            litellm.api_key = api_key
            
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
    
    async def connect_to_server(self, command: str, args: List[str]) -> None:
        """
        Connect to an MCP server and fetch available tools.
        
        Args:
            command: The command to run the server
            args: List of arguments for the server
        """
        # 1) Create and connect a brand-new client
        client = MCPClient()
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
        
        logger.info(f"Connected to {command} {args!r}, added {len(resp.tools)} tools")
    
    async def run(self, user_input: str, max_turns: int = 10) -> str:
        """
        Run the agent with user input.
        
        Args:
            user_input: The user's request
            max_turns: Maximum number of turns before giving up
            
        Returns:
            The final agent response
        """
        # Add user message to conversation
        self.messages.append({"role": "user", "content": user_input})
        
        # Initialize loop control variables
        num_turns = 0
        next_turn_should_call_tools = True
        
        # The main agent loop
        while True:
            # Get all available tools including exit loop tools
            all_tools = self.available_tools + self.exit_loop_tools
            
            # Call LLM with messages and tools
            try:
                logger.info(f"Calling LLM with {len(self.messages)} messages and {len(all_tools)} tools")
                response = await litellm.acompletion(
                    model=self.model,
                    messages=self.messages,
                    tools=all_tools,
                    tool_choice="auto"
                )
                
                # Process the response - properly handle the object
                response_message = response.choices[0].message
                logger.debug(f"🔥🔥🔥🔥🔥🔥 Response : {response_message}")
                
                # Create a proper message dictionary from the response object's attributes
                assistant_message = {
                    "role": "assistant",
                    "content": response_message.content if hasattr(response_message, "content") else ""
                }
                
                # Check if the message has tool_calls attribute and it's not empty
                has_tool_calls = hasattr(response_message, "tool_calls") and response_message.tool_calls
                
                if has_tool_calls:
                    # Add tool_calls to the message if present
                    assistant_message["tool_calls"] = response_message.tool_calls
                
                # Add the properly formatted assistant message to conversation
                self.messages.append(assistant_message)
                
                # Process tool calls if they exist
                if has_tool_calls:
                    tool_calls = response_message.tool_calls
                    logger.info(f"Tool calls detected: {len(tool_calls)}")
                    
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
                                logger.error(f"Could not parse tool arguments: {function_info.arguments}")
                                tool_args = {}
                            
                            # Handle control flow tools
                            if tool_name == "task_complete":
                                # Add a response for this tool call before returning
                                tool_message["content"] = "Task has been completed successfully."
                                self.messages.append(tool_message)
                                return "Task completed."
                            elif tool_name == "ask_question":
                                question = tool_args.get("question", "Could you provide more details?")
                                # Add a response for this tool call before returning
                                tool_message["content"] = f"Question asked: {question}"
                                self.messages.append(tool_message)
                                return f"I need more information: {question}"
                            else:
                                # **New**: dispatch to the proper MCPClient
                                client = self.tool_to_client.get(tool_name)
                                if not client:
                                    tool_message["content"] = f"No MCP server registered for tool '{tool_name}'"
                                else:
                                    try:
                                        content_list = await client.call_tool(tool_name, tool_args)
                                        
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
                                        logger.error(f"Error calling tool {tool_name}: {str(e)}")
                                        tool_message["content"] = f"Error executing tool {tool_name}: {str(e)}"
                        except Exception as e:
                            # If any error occurs during tool call processing, make sure we still have a tool response
                            logger.error(f"Unexpected error processing tool call {tool_call_id}: {str(e)}")
                            tool_message["content"] = f"Error processing tool call: {str(e)}"
                        
                        # Always add the tool message to ensure each tool call has a response
                        self.messages.append(tool_message)
                    
                    next_turn_should_call_tools = False
                else:
                    # No tool calls in this message
                    if next_turn_should_call_tools and num_turns > 0:
                        # If we expected tool calls but didn't get any, we're done
                        return assistant_message["content"] or ""
                    
                    next_turn_should_call_tools = True
                
                num_turns += 1
                if num_turns >= max_turns:
                    return "Max turns reached. Task incomplete."
                
            except Exception as e:
                logger.error(f"Error in agent loop: {str(e)}")
                return f"Error: {str(e)}"

    
    async def close(self):
        """Clean up *all* MCP clients."""
        for client in self.mcp_clients:
            try:
                await client.close()
            except RuntimeError as e:
                logger.error(f"Error closing MCP client: {str(e)}")
                # Continue closing other clients even if one fails
