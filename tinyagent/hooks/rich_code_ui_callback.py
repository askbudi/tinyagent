import json
import logging
from typing import Any, Optional, Set

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.text import Text
from rich.json import JSON

from tinyagent.hooks.rich_ui_callback import RichUICallback, create_panel, escape_markdown_tags

__all__ = ["RichCodeUICallback"]


class RichCodeUICallback(RichUICallback):
    """
    A callback for TinyAgent that extends RichUICallback with special handling for code tools.
    Provides richer display for Python code execution in run_python tool calls.
    """
    
    def __init__(
        self, 
        console: Optional[Console] = None,
        markdown: bool = True,
        show_message: bool = True,
        show_thinking: bool = True,
        show_tool_calls: bool = True,
        tags_to_include_in_markdown: Set[str] = {"think", "thinking"},
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Rich Code UI callback.
        
        Args:
            console: Optional Rich console to use
            markdown: Whether to render responses as markdown
            show_message: Whether to show the user message
            show_thinking: Whether to show the thinking process
            show_tool_calls: Whether to show tool calls
            tags_to_include_in_markdown: Tags to include in markdown rendering
            logger: Optional logger to use
        """
        super().__init__(
            console=console,
            markdown=markdown,
            show_message=show_message,
            show_thinking=show_thinking,
            show_tool_calls=show_tool_calls,
            tags_to_include_in_markdown=tags_to_include_in_markdown,
            logger=logger or logging.getLogger(__name__)
        )
        self.logger.debug("RichCodeUICallback initialized")
    
    async def _handle_message_add(self, agent: Any, **kwargs: Any) -> None:
        """Handle the message_add event with special handling for run_python tool."""
        # Call the parent method first to ensure all standard processing occurs
        await super()._handle_message_add(agent, **kwargs)
        
        # Then perform our special handling for run_python tool calls
        message = kwargs.get("message", {})
        
        # Process tool calls in assistant messages
        if message.get("role") == "assistant" and "tool_calls" in message:
            for tool_call in message.get("tool_calls", []):
                function_info = tool_call.get("function", {})
                tool_name = function_info.get("name", "unknown")
                
                # Only process run_python tool calls
                if tool_name == "run_python":
                    args = function_info.get("arguments", "{}")
                    tool_id = tool_call.get("id", "unknown")
                    
                    try:
                        args_dict = json.loads(args)
                        
                        # Find the corresponding tool call in our detailed list
                        for tool_detail in self.tool_call_details:
                            if tool_detail.get("id") == tool_id and tool_detail.get("name") == "run_python":
                                # Check if code_lines is present
                                if "code_lines" in args_dict and isinstance(args_dict["code_lines"], list):
                                    # Store the original code_lines for display purposes
                                    tool_detail["code_lines"] = args_dict["code_lines"]
                                    self.logger.debug(f"Stored code_lines for run_python tool {tool_id}")
                                break
                    except Exception as e:
                        self.logger.error(f"Error processing run_python arguments: {e}")
    
    def _update_display(self) -> None:
        """Update the live display with current panels, with special handling for code output."""
        # Don't call super() yet - we'll build the panels ourselves to have more control
        
        # If we don't have live display, nothing to do
        if not self.live:
            return
            
        # Start with a fresh list of panels in the specified order
        ordered_panels = []
        
        # 1. Status (if exists)
        status_panel = next((p for p in self.panels if hasattr(p, "renderable") and isinstance(p.renderable, Group) and 
                            hasattr(p.renderable[0], "spinner")), None)
        if status_panel:
            ordered_panels.append(status_panel)
        
        # 2. User Message (if exists)
        user_message_panel = next((p for p in self.panels if hasattr(p, "title") and "User Message" in str(p.title)), None)
        if user_message_panel:
            ordered_panels.append(user_message_panel)
        
        # 3. Tool Calls summary (if we have tool calls)
        if self.show_tool_calls and self.tool_calls:
            # Create the tool calls summary panel
            self.logger.debug(f"Creating tool calls summary panel with {len(self.tool_calls)} calls")
            tool_calls_content = Text()
            for i, tool_call in enumerate(self.tool_calls):
                if "result:" not in tool_call:  # Only show the calls, not results
                    tool_calls_content.append(f"• {tool_call}\n")
            
            if tool_calls_content:
                tool_calls_panel = create_panel(
                    content=tool_calls_content,
                    title="Tool Calls Summary",
                    border_style="yellow",
                    logger=self.logger
                )
                ordered_panels.append(tool_calls_panel)
        
        # 4. Assistant Text Responses
        for i, response_data in enumerate(self.assistant_text_responses):
            content = response_data["content"]
            token_count = response_data.get("token_count", 0)
            
            if self.markdown:
                self.logger.debug("Converting assistant response to markdown")
                escaped_content = escape_markdown_tags(content, self.tags_to_include_in_markdown)
                content = Markdown(escaped_content)
            
            response_panel = create_panel(
                content=content,
                title=f"Assistant Response {i+1}",
                border_style="blue",
                logger=self.logger
            )
            ordered_panels.append(response_panel)
            
            # Add token count panel with purple border
            token_panel = create_panel(
                content=Text(f"Token count: {token_count}", style="bold"),
                title="Tokens",
                border_style="purple",
                logger=self.logger
            )
            ordered_panels.append(token_panel)
        
        # 5. Token Usage Panel
        if any(self.token_usage.values()):
            token_content = Text()
            token_content.append(f"Prompt Tokens: {self.token_usage['prompt_tokens']}\n", style="cyan")
            token_content.append(f"Completion Tokens: {self.token_usage['completion_tokens']}\n", style="green")
            token_content.append(f"Total Tokens: {self.token_usage['total_tokens']}", style="bold magenta")
            
            token_panel = create_panel(
                content=token_content,
                title="Token Usage",
                border_style="bright_blue",
                logger=self.logger
            )
            ordered_panels.append(token_panel)
        
        # 6. Detailed Tool Calls - with special handling for run_python
        if self.show_tool_calls:
            for tool_detail in self.tool_call_details:
                tool_name = tool_detail["name"]
                tool_id = tool_detail.get("id", "unknown")
                
                # Special handling for run_python tools
                if tool_name == "run_python" and "code_lines" in tool_detail:
                    # Create a markdown-formatted Python code block
                    code_lines = tool_detail["code_lines"]
                    combined_code = "\n".join(code_lines)
                    python_code_markdown = f"```python\n{combined_code}\n```"
                    
                    # Create a group with the code and result (if available)
                    content_group = []
                    
                    # Add the markdown-formatted code
                    if self.markdown:
                        try:
                            code_content = Markdown(python_code_markdown)
                            content_group.append(code_content)
                            
                            # Add the result if available
                            if tool_detail.get("result"):
                                result = tool_detail.get("result")
                                content_group.append(Text("\nOutput:", style="bold"))
                                
                                # Handle different result types properly
                                if isinstance(result, dict):
                                    # If result is already a dict, use JSON formatter
                                    content_group.append(JSON(result))
                                else:
                                    try:
                                        # Try to parse string result as JSON
                                        result_json = json.loads(result)
                                        content_group.append(JSON(result_json))
                                    except:
                                        # Handle plain text with proper formatting
                                        # Replace escaped newlines with actual newlines
                                        if isinstance(result, str):
                                            formatted_result = result.replace("\\n", "\n")
                                            # Split by lines and preserve indentation
                                            lines = formatted_result.split("\n")
                                            formatted_text = Text()
                                            for line in lines:
                                                formatted_text.append(f"{line}\n")
                                            content_group.append(formatted_text)
                                        else:
                                            # For any other type, convert to string
                                            content_group.append(Text(str(result)))
                            
                            # Create a panel with the content group
                            code_panel = create_panel(
                                content=Group(*content_group),
                                title=f"Tool: run_python ({tool_id})",
                                border_style="yellow",
                                logger=self.logger
                            )
                            ordered_panels.append(code_panel)
                            
                            # Add token count panel with purple border
                            input_token_count = tool_detail.get("token_count", 0)
                            result_token_count = tool_detail.get("result_token_count", 0)
                            
                            token_content = Text()
                            token_content.append(f"Input tokens: {input_token_count}\n", style="cyan")
                            if tool_detail.get("result") is not None:
                                token_content.append(f"Output tokens: {result_token_count}\n", style="green")
                            token_content.append(f"Total tokens: {input_token_count + result_token_count}", style="bold")
                            
                            token_panel = create_panel(
                                content=token_content,
                                title="Tokens",
                                border_style="purple",
                                logger=self.logger
                            )
                            ordered_panels.append(token_panel)
                            
                        except Exception as e:
                            self.logger.error(f"Error creating markdown panel: {e}")
                            # Fallback to standard panel
                            self._add_standard_tool_panel(ordered_panels, tool_detail)
                    else:
                        # If markdown is disabled, use standard panel
                        self._add_standard_tool_panel(ordered_panels, tool_detail)
                else:
                    # Standard handling for other tools
                    self._add_standard_tool_panel(ordered_panels, tool_detail)
        
        # 7. Thinking panel (if we have thinking content)
        if self.show_thinking and self.thinking_content:
            self.logger.debug("Adding thinking panel")
            thinking_panel = create_panel(
                content=Text(self.thinking_content),
                title=f"Thinking ({self.timer.elapsed:.1f}s)",
                border_style="green",
                logger=self.logger
            )
            ordered_panels.append(thinking_panel)
            
            # Add token count panel for thinking content
            thinking_token_count = self.count_tokens(self.thinking_content)
            token_panel = create_panel(
                content=Text(f"Token count: {thinking_token_count}", style="bold"),
                title="Tokens",
                border_style="purple",
                logger=self.logger
            )
            ordered_panels.append(token_panel)
        
        # 8. Final response panel (if we have a response)
        if self.response_content:
            content = self.response_content
            if self.markdown:
                self.logger.debug("Converting response to markdown")
                escaped_content = escape_markdown_tags(content, self.tags_to_include_in_markdown)
                content = Markdown(escaped_content)
            
            response_panel = create_panel(
                content=content,
                title=f"Response ({self.timer.elapsed:.1f}s)",
                border_style="blue",
                logger=self.logger
            )
            ordered_panels.append(response_panel)
            
            # Add token count panel for final response
            response_token_count = self.count_tokens(self.response_content)
            token_panel = create_panel(
                content=Text(f"Token count: {response_token_count}", style="bold"),
                title="Tokens",
                border_style="purple",
                logger=self.logger
            )
            ordered_panels.append(token_panel)
        
        try:
            self.logger.debug(f"Updating live display with {len(ordered_panels)} panels")
            self.live.update(Group(*ordered_panels))
        except Exception as e:
            self.logger.error(f"Error updating display: {e}")
    
    def _add_standard_tool_panel(self, ordered_panels, tool_detail):
        """Add a standard tool panel for non-run_python tools or as fallback."""
        tool_name = tool_detail["name"]
        arguments = tool_detail["arguments"]
        result = tool_detail.get("result")
        input_token_count = tool_detail.get("token_count", 0)
        result_token_count = tool_detail.get("result_token_count", 0)
        tool_id = tool_detail.get("id", "unknown")
        
        tool_content = Text()
        tool_content.append("Input:\n", style="bold")
        tool_content.append(f"{arguments}\n\n")
        
        if result is not None:
            tool_content.append("Output:\n", style="bold")
            tool_content.append(f"{result}")
        else:
            tool_content.append("Waiting for response...", style="italic")
        
        tool_panel = create_panel(
            content=tool_content,
            title=f"Tool: {tool_name} ({tool_id})",
            border_style="yellow",
            logger=self.logger
        )
        ordered_panels.append(tool_panel)
        
        # Add token count panel with purple border
        token_content = Text()
        token_content.append(f"Input tokens: {input_token_count}\n", style="cyan")
        if result is not None:
            token_content.append(f"Output tokens: {result_token_count}\n", style="green")
        token_content.append(f"Total tokens: {input_token_count + result_token_count}", style="bold")
        
        token_panel = create_panel(
            content=token_content,
            title="Tokens",
            border_style="purple",
            logger=self.logger
        )
        ordered_panels.append(token_panel)


async def run_example():
    """Example usage of RichCodeUICallback with TinyAgent."""
    import asyncio
    import os
    import sys
    from tinyagent import TinyAgent
    from tinyagent.hooks.logging_manager import LoggingManager
    
    # Create and configure logging manager
    log_manager = LoggingManager(default_level=logging.INFO)
    log_manager.set_levels({
        'tinyagent.hooks.rich_code_ui_callback': logging.DEBUG,  # Debug for this module
        'tinyagent.tiny_agent': logging.INFO,                   # Info for TinyAgent
        'tinyagent.mcp_client': logging.INFO,                   # Info for MCPClient
    })
    
    # Configure a console handler
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    
    # Get module-specific loggers
    ui_logger = log_manager.get_logger('tinyagent.hooks.rich_code_ui_callback')
    agent_logger = log_manager.get_logger('tinyagent.tiny_agent')
    
    ui_logger.debug("Starting RichCodeUICallback example")
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        ui_logger.error("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Initialize the agent with our logger
    agent = TinyAgent(model="gpt-4.1-mini", api_key=api_key, logger=agent_logger)
    
    # Connect to MCP servers as required
    await agent.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    # Define a run_python tool
    async def run_python(code_lines):
        try:
            code = "\n".join(code_lines)
            # In a real implementation, you'd run this code with appropriate safety measures
            result = f"Executed Python code successfully. Result: This is a simulated result for demo"
            return result
        except Exception as e:
            return f"Error executing Python code: {str(e)}"
    
    # Register the tool with the agent
    agent.register_tool(run_python)
    
    # Add the Rich Code UI callback with our logger
    rich_ui = RichCodeUICallback(
        markdown=True,
        show_message=True,
        show_thinking=True,
        show_tool_calls=True,
        logger=ui_logger
    )
    agent.add_callback(rich_ui)
    
    # Run the agent with the required example input
    user_input = "Plan a trip to Toronto for 7 days. In the next month."
    ui_logger.info(f"Running agent with input: {user_input}")
    result = await agent.run(user_input)
    
    ui_logger.info(f"Final result: {result}")
    
    # Clean up
    await agent.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_example())