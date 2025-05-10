import asyncio
import json
import time
import logging
import tiktoken  # Add tiktoken import for token counting
from typing import Any, Dict, List, Optional, Set, Union

from rich.console import Console, Group
from rich.json import JSON
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.text import Text
from rich.box import HEAVY



class Timer:
    """Simple timer to track elapsed time."""
    
    def __init__(self, logger=None):
        self.start_time = None
        self.end_time = None
        self.logger = logger or logging.getLogger(__name__)
    
    def start(self):
        self.start_time = time.time()
        self.end_time = None
        self.logger.debug("Timer started")
    
    def stop(self):
        self.end_time = time.time()
        self.logger.debug(f"Timer stopped. Total elapsed: {self.elapsed:.2f}s")
    
    @property
    def elapsed(self) -> float:
        """Return elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time


def create_panel(content, title, border_style="blue", logger=None):
    """Create a rich panel with consistent styling."""
    log = logger or logging.getLogger(__name__)
    log.debug(f"Creating panel with title: {title}")
    return Panel(
        content, 
        title=title, 
        title_align="left", 
        border_style=border_style, 
        box=HEAVY, 
        expand=True, 
        padding=(1, 1)
    )


def escape_markdown_tags(content: str, tags: Set[str]) -> str:
    """Escape special tags in markdown content."""
    escaped_content = content
    for tag in tags:
        # Escape opening tag
        escaped_content = escaped_content.replace(f"<{tag}>", f"&lt;{tag}&gt;")
        # Escape closing tag
        escaped_content = escaped_content.replace(f"</{tag}>", f"&lt;/{tag}&gt;")
    return escaped_content


class RichUICallback:
    """
    A callback for TinyAgent that provides a rich terminal UI similar to Agno.
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
        Initialize the Rich UI callback.
        
        Args:
            console: Optional Rich console to use
            markdown: Whether to render responses as markdown
            show_message: Whether to show the user message
            show_thinking: Whether to show the thinking process
            show_tool_calls: Whether to show tool calls
            tags_to_include_in_markdown: Tags to include in markdown rendering
            logger: Optional logger to use
        """
        self.console = console or Console()
        self.markdown = markdown
        self.show_message = show_message
        self.show_thinking = show_thinking
        self.show_tool_calls = show_tool_calls
        self.tags_to_include_in_markdown = tags_to_include_in_markdown
        self.logger = logger or logging.getLogger(__name__)
        
        # State tracking
        self.live = None
        self.timer = Timer(logger=self.logger)
        self.panels = []
        self.status = None
        self.thinking_content = ""
        self.response_content = ""
        self.tool_calls = []
        self.tool_call_details = []  # Store detailed tool call info with inputs and outputs
        self.current_user_input = ""
        self.assistant_text_responses = []  # Store text responses from assistant
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        # Initialize tiktoken encoder for token counting
        try:
            self.encoder = tiktoken.get_encoding("o200k_base")
            self.logger.debug("Initialized tiktoken encoder with o200k_base encoding")
        except Exception as e:
            self.logger.error(f"Failed to initialize tiktoken encoder: {e}")
            self.encoder = None
        
        self.logger.debug("RichUICallback initialized")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in a string using tiktoken."""
        if not self.encoder or not text:
            return 0
        try:
            return len(self.encoder.encode(text))
        except Exception as e:
            self.logger.error(f"Error counting tokens: {e}")
            return 0
        
    async def __call__(self, event_name: str, agent: Any, **kwargs: Any) -> None:
        """
        Process events from the TinyAgent.
        
        Args:
            event_name: The name of the event
            agent: The TinyAgent instance
            **kwargs: Additional event data
        """
        self.logger.debug(f"Event received: {event_name}")
        
        if event_name == "agent_start":
            await self._handle_agent_start(agent, **kwargs)
        elif event_name == "message_add":
            await self._handle_message_add(agent, **kwargs)
        elif event_name == "llm_start":
            await self._handle_llm_start(agent, **kwargs)
        elif event_name == "llm_end":
            await self._handle_llm_end(agent, **kwargs)
        elif event_name == "agent_end":
            await self._handle_agent_end(agent, **kwargs)
        
        # Update the UI if we have an active live display
        if self.live:
            self.logger.debug("Updating display")
            self._update_display()
    
    async def _handle_agent_start(self, agent: Any, **kwargs: Any) -> None:
        """Handle the agent_start event."""
        self.logger.debug("Handling agent_start event")
        self.timer.start()
        self.panels = []
        self.thinking_content = ""
        self.response_content = ""
        self.tool_calls = []
        self.tool_call_details = []
        self.assistant_text_responses = []
        
        # Store the user input for display
        self.current_user_input = kwargs.get("user_input", "")
        self.logger.debug(f"User input: {self.current_user_input}")
        
        # Initialize the live display with auto_refresh 
        self.live = Live(
            console=self.console, 
            auto_refresh=True,
            refresh_per_second=4,
        )
        self.logger.debug("Starting live display")
        self.live.start()
        
        # Add the initial status
        self.status = Status("Thinking...", spinner="aesthetic", speed=0.4, refresh_per_second=10)
        self.panels = [self.status]
        
        # Add user message panel if enabled
        if self.show_message and self.current_user_input:
            self.logger.debug("Adding user message panel")
            message_panel = create_panel(
                content=Text(self.current_user_input, style="green"),
                title="User Message",
                border_style="cyan"
            )
            self.panels.append(message_panel)
        
        self._update_display()
    
    async def _handle_message_add(self, agent: Any, **kwargs: Any) -> None:
        """Handle the message_add event."""
        message = kwargs.get("message", {})
        self.logger.debug(f"Handling message_add event: {message.get('role', 'unknown')}")
        
        # Process tool calls in assistant messages
        if message.get("role") == "assistant":
            if "tool_calls" in message:
                self.logger.debug(f"Processing {len(message.get('tool_calls', []))} tool calls")
                for tool_call in message.get("tool_calls", []):
                    function_info = tool_call.get("function", {})
                    tool_name = function_info.get("name", "unknown")
                    args = function_info.get("arguments", "{}")
                    tool_id = tool_call.get("id", "unknown")
                    
                    try:
                        formatted_args = json.dumps(json.loads(args), indent=2)
                    except:
                        formatted_args = args
                    
                    # Count tokens in the tool call
                    token_count = self.count_tokens(f"{tool_name}({formatted_args})")
                    
                    # Add to simple tool calls list (for the summary panel)
                    self.tool_calls.append(f"{tool_name}({formatted_args})")
                    
                    # Add to detailed tool call info
                    self.tool_call_details.append({
                        "id": tool_id,
                        "name": tool_name,
                        "arguments": formatted_args,
                        "result": None,  # Will be filled when tool response comes
                        "token_count": token_count  # Store token count
                    })
                    
                    self.logger.debug(f"Added tool call: {tool_name} ({token_count} tokens)")
            elif "content" in message and message.get("content"):
                # This is a text response from the assistant
                content = message.get("content", "")
                token_count = self.count_tokens(content)
                self.assistant_text_responses.append({
                    "content": content,
                    "token_count": token_count
                })
                self.logger.debug(f"Added assistant text response: {content[:50]}... ({token_count} tokens)")
        
        # Process tool responses
        if message.get("role") == "tool":
            tool_name = message.get("name", "unknown")
            content = message.get("content", "")
            tool_call_id = message.get("tool_call_id", None)
            token_count = self.count_tokens(content)
            
            # Update the corresponding tool call detail with the result
            if tool_call_id:
                for tool_detail in self.tool_call_details:
                    if tool_detail["id"] == tool_call_id:
                        tool_detail["result"] = content
                        tool_detail["result_token_count"] = token_count
                        self.logger.debug(f"Updated tool call {tool_call_id} with result ({token_count} tokens)")
                        break
            
            # Also keep the old format for backward compatibility
            self.tool_calls.append(f"{tool_name} result: {content}")
            self.logger.debug(f"Added tool result: {tool_name} ({token_count} tokens)")
    
    async def _handle_llm_start(self, agent: Any, **kwargs: Any) -> None:
        """Handle the llm_start event."""
        self.logger.debug("Handling llm_start event")
        # Nothing specific to do here, the status is already showing "Thinking..."
    
    async def _handle_llm_end(self, agent: Any, **kwargs: Any) -> None:
        """Handle the llm_end event."""
        self.logger.debug("Handling llm_end event")
        response = kwargs.get("response", {})
        
        # Extract thinking content if available (from response.choices[0].message.content)
        try:
            message = response.choices[0].message
            if hasattr(message, "content") and message.content:
                self.thinking_content = message.content
                self.logger.debug(f"Extracted thinking content: {self.thinking_content[:50]}...")
        except (AttributeError, IndexError) as e:
            self.logger.debug(f"Could not extract thinking content: {e}")
            
        # Track token usage if available
        try:
            usage = response.usage
            if usage:
                self.token_usage["prompt_tokens"] += usage.prompt_tokens
                self.token_usage["completion_tokens"] += usage.completion_tokens
                self.token_usage["total_tokens"] += usage.total_tokens
                self.logger.debug(f"Updated token usage: {self.token_usage}")
        except (AttributeError, TypeError) as e:
            self.logger.debug(f"Could not extract token usage: {e}")
    
    async def _handle_agent_end(self, agent: Any, **kwargs: Any) -> None:
        """Handle the agent_end event."""
        self.logger.debug("Handling agent_end event")
        self.timer.stop()
        self.response_content = kwargs.get("result", "")
        self.logger.debug(f"Final response: {self.response_content[:50]}...")
        
        # Remove the status panel
        self.panels = [p for p in self.panels if not isinstance(p, Status)]
        
        # Add the final response panel
        if self.response_content:
            content = self.response_content
            if self.markdown:
                self.logger.debug("Converting response to markdown")
                escaped_content = escape_markdown_tags(content, self.tags_to_include_in_markdown)
                content = Markdown(escaped_content)
            
            response_panel = create_panel(
                content=content,
                title=f"Response ({self.timer.elapsed:.1f}s)",
                border_style="blue"
            )
            self.panels.append(response_panel)
        
        self._update_display()
        
        self.live.stop()
        self.logger.debug("Live display stopped")

    
    def _update_display(self) -> None:
        """Update the live display with current panels."""
        if not self.live:
            self.logger.debug("No live display to update")
            return
        
        # Start with a fresh list of panels in the specified order
        ordered_panels = []
        
        # 1. Status (if exists)
        status_panel = next((p for p in self.panels if isinstance(p, Status)), None)
        if status_panel:
            ordered_panels.append(status_panel)
        
        # 2. User Message (if exists)
        user_message_panel = next((p for p in self.panels if isinstance(p, Panel) and "User Message" in p.title), None)
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
                    border_style="yellow"
                )
                ordered_panels.append(tool_calls_panel)
        
        # 4. Assistant Text Responses
        for i, response_data in enumerate(self.assistant_text_responses):
            content = response_data["content"]
            token_count = response_data["token_count"]
            
            if self.markdown:
                self.logger.debug("Converting assistant response to markdown")
                escaped_content = escape_markdown_tags(content, self.tags_to_include_in_markdown)
                content = Markdown(escaped_content)
            
            response_panel = create_panel(
                content=content,
                title=f"Assistant Response {i+1}",
                border_style="blue"
            )
            ordered_panels.append(response_panel)
            
            # Add token count panel with purple border
            token_panel = create_panel(
                content=Text(f"Token count: {token_count}", style="bold"),
                title="Tokens",
                border_style="purple"
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
                border_style="bright_blue"
            )
            ordered_panels.append(token_panel)
        
        # 6. Detailed Tool Calls
        if self.show_tool_calls:
            for tool_detail in self.tool_call_details:
                tool_name = tool_detail["name"]
                arguments = tool_detail["arguments"]
                result = tool_detail["result"]
                input_token_count = tool_detail.get("token_count", 0)
                result_token_count = tool_detail.get("result_token_count", 0)
                
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
                    title=f"Tool: {tool_name}",
                    border_style="yellow"
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
                    border_style="purple"
                )
                ordered_panels.append(token_panel)
        
        # 7. Thinking panel (if we have thinking content)
        if self.show_thinking and self.thinking_content:
            self.logger.debug("Adding thinking panel")
            thinking_panel = create_panel(
                content=Text(self.thinking_content),
                title=f"Response ({self.timer.elapsed:.1f}s)",
                border_style="green"
            )
            ordered_panels.append(thinking_panel)
            
            # Add token count panel for thinking content
            thinking_token_count = self.count_tokens(self.thinking_content)
            token_panel = create_panel(
                content=Text(f"Token count: {thinking_token_count}", style="bold"),
                title="Tokens",
                border_style="purple"
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
                border_style="blue"
            )
            ordered_panels.append(response_panel)
            
            # Add token count panel for final response
            response_token_count = self.count_tokens(self.response_content)
            token_panel = create_panel(
                content=Text(f"Token count: {response_token_count}", style="bold"),
                title="Tokens",
                border_style="purple"
            )
            ordered_panels.append(token_panel)
        
        try:
            self.logger.debug(f"Updating live display with {len(ordered_panels)} panels")
            self.live.update(Group(*ordered_panels))
        except Exception as e:
            self.logger.error(f"Error updating display: {e}")


async def run_example():
    """Example usage of RichUICallback with TinyAgent."""
    import os
    import sys
    from tinyagent import TinyAgent
    from tinyagent.hooks.logging_manager import LoggingManager
    
    # Create and configure logging manager
    log_manager = LoggingManager(default_level=logging.INFO)
    log_manager.set_levels({
        'tinyagent.hooks.rich_ui_callback': logging.DEBUG,  # Debug for this module
        'tinyagent.tiny_agent': logging.INFO,               # Info for TinyAgent
        'tinyagent.mcp_client': logging.INFO,               # Info for MCPClient
    })
    
    # Configure a console handler
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    
    # Get module-specific loggers
    ui_logger = log_manager.get_logger('tinyagent.hooks.rich_ui_callback')
    agent_logger = log_manager.get_logger('tinyagent.tiny_agent')
    mcp_logger = log_manager.get_logger('tinyagent.mcp_client')
    
    ui_logger.debug("Starting RichUICallback example")
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        ui_logger.error("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Initialize the agent with our logger
    agent = TinyAgent(model="gpt-4.1-mini", api_key=api_key, logger=agent_logger)
    
    # Add the Rich UI callback with our logger
    rich_ui = RichUICallback(
        markdown=True,
        show_message=True,
        show_thinking=True,
        show_tool_calls=True,
        logger=ui_logger  # Pass DEBUG level logger to RichUICallback
    )
    agent.add_callback(rich_ui)
    
    # Run the agent with a user query
    user_input = "What is the capital of France and what's the population this year?"
    ui_logger.info(f"Running agent with input: {user_input}")
    result = await agent.run(user_input)
    
    ui_logger.info(f"Final result: {result}")
    
    # Clean up
    await agent.close()


if __name__ == "__main__":
    asyncio.run(run_example())