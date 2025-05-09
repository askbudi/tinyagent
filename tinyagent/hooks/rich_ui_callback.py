import asyncio
import json
import time
import logging
from typing import Any, Dict, List, Optional, Set, Union

from rich.console import Console, Group
from rich.json import JSON
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.text import Text
from rich.box import HEAVY

# Set up logging
logger = logging.getLogger(__name__)

class Timer:
    """Simple timer to track elapsed time."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        self.start_time = time.time()
        self.end_time = None
        logger.debug("Timer started")
    
    def stop(self):
        self.end_time = time.time()
        logger.debug(f"Timer stopped. Total elapsed: {self.elapsed:.2f}s")
    
    @property
    def elapsed(self) -> float:
        """Return elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time is not None else time.time()
        return end - self.start_time


def create_panel(content, title, border_style="blue"):
    """Create a rich panel with consistent styling."""
    logger.debug(f"Creating panel with title: {title}")
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
        """
        self.console = console or Console()
        self.markdown = markdown
        self.show_message = show_message
        self.show_thinking = show_thinking
        self.show_tool_calls = show_tool_calls
        self.tags_to_include_in_markdown = tags_to_include_in_markdown
        
        # State tracking
        self.live = None
        self.timer = Timer()
        self.panels = []
        self.status = None
        self.thinking_content = ""
        self.response_content = ""
        self.tool_calls = []
        self.tool_call_details = []  # Store detailed tool call info with inputs and outputs
        self.current_user_input = ""
        self.assistant_text_responses = []  # Store text responses from assistant
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        logger.debug("RichUICallback initialized")
        
    async def __call__(self, event_name: str, agent: Any, **kwargs: Any) -> None:
        """
        Process events from the TinyAgent.
        
        Args:
            event_name: The name of the event
            agent: The TinyAgent instance
            **kwargs: Additional event data
        """
        logger.debug(f"Event received: {event_name}")
        
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
            logger.debug("Updating display")
            self._update_display()
    
    async def _handle_agent_start(self, agent: Any, **kwargs: Any) -> None:
        """Handle the agent_start event."""
        logger.debug("Handling agent_start event")
        self.timer.start()
        self.panels = []
        self.thinking_content = ""
        self.response_content = ""
        self.tool_calls = []
        self.tool_call_details = []
        self.assistant_text_responses = []
        
        # Store the user input for display
        self.current_user_input = kwargs.get("user_input", "")
        logger.debug(f"User input: {self.current_user_input}")
        
        # Initialize the live display with auto_refresh 
        self.live = Live(
            console=self.console, 
            auto_refresh=True,
            refresh_per_second=4,
        )
        logger.debug("Starting live display")
        self.live.start()
        
        # Add the initial status
        self.status = Status("Thinking...", spinner="aesthetic", speed=0.4, refresh_per_second=10)
        self.panels = [self.status]
        
        # Add user message panel if enabled
        if self.show_message and self.current_user_input:
            logger.debug("Adding user message panel")
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
        logger.debug(f"Handling message_add event: {message.get('role', 'unknown')}")
        
        # Process tool calls in assistant messages
        if message.get("role") == "assistant":
            if "tool_calls" in message:
                logger.debug(f"Processing {len(message.get('tool_calls', []))} tool calls")
                for tool_call in message.get("tool_calls", []):
                    function_info = tool_call.get("function", {})
                    tool_name = function_info.get("name", "unknown")
                    args = function_info.get("arguments", "{}")
                    tool_id = tool_call.get("id", "unknown")
                    
                    try:
                        formatted_args = json.dumps(json.loads(args), indent=2)
                    except:
                        formatted_args = args
                    
                    # Add to simple tool calls list (for the summary panel)
                    self.tool_calls.append(f"{tool_name}({formatted_args})")
                    
                    # Add to detailed tool call info
                    self.tool_call_details.append({
                        "id": tool_id,
                        "name": tool_name,
                        "arguments": formatted_args,
                        "result": None  # Will be filled when tool response comes
                    })
                    
                    logger.debug(f"Added tool call: {tool_name}")
            elif "content" in message and message.get("content"):
                # This is a text response from the assistant
                self.assistant_text_responses.append(message.get("content", ""))
                logger.debug(f"Added assistant text response: {message.get('content', '')[:50]}...")
        
        # Process tool responses
        if message.get("role") == "tool":
            tool_name = message.get("name", "unknown")
            content = message.get("content", "")
            tool_call_id = message.get("tool_call_id", None)
            
            # Update the corresponding tool call detail with the result
            if tool_call_id:
                for tool_detail in self.tool_call_details:
                    if tool_detail["id"] == tool_call_id:
                        tool_detail["result"] = content
                        logger.debug(f"Updated tool call {tool_call_id} with result")
                        break
            
            # Also keep the old format for backward compatibility
            self.tool_calls.append(f"{tool_name} result: {content}")
            logger.debug(f"Added tool result: {tool_name}")
    
    async def _handle_llm_start(self, agent: Any, **kwargs: Any) -> None:
        """Handle the llm_start event."""
        logger.debug("Handling llm_start event")
        # Nothing specific to do here, the status is already showing "Thinking..."
    
    async def _handle_llm_end(self, agent: Any, **kwargs: Any) -> None:
        """Handle the llm_end event."""
        logger.debug("Handling llm_end event")
        response = kwargs.get("response", {})
        
        # Extract thinking content if available (from response.choices[0].message.content)
        try:
            message = response.choices[0].message
            if hasattr(message, "content") and message.content:
                self.thinking_content = message.content
                logger.debug(f"Extracted thinking content: {self.thinking_content[:50]}...")
        except (AttributeError, IndexError) as e:
            logger.debug(f"Could not extract thinking content: {e}")
            
        # Track token usage if available
        try:
            usage = response.usage
            if usage:
                self.token_usage["prompt_tokens"] += usage.prompt_tokens
                self.token_usage["completion_tokens"] += usage.completion_tokens
                self.token_usage["total_tokens"] += usage.total_tokens
                logger.debug(f"Updated token usage: {self.token_usage}")
        except (AttributeError, TypeError) as e:
            logger.debug(f"Could not extract token usage: {e}")
    
    async def _handle_agent_end(self, agent: Any, **kwargs: Any) -> None:
        """Handle the agent_end event."""
        logger.debug("Handling agent_end event")
        self.timer.stop()
        self.response_content = kwargs.get("result", "")
        logger.debug(f"Final response: {self.response_content[:50]}...")
        
        # Remove the status panel
        self.panels = [p for p in self.panels if not isinstance(p, Status)]
        
        # Add the final response panel
        if self.response_content:
            content = self.response_content
            if self.markdown:
                logger.debug("Converting response to markdown")
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
        logger.debug("Live display stopped")

    
    def _update_display(self) -> None:
        """Update the live display with current panels."""
        if not self.live:
            logger.debug("No live display to update")
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
            logger.debug(f"Creating tool calls summary panel with {len(self.tool_calls)} calls")
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
        for i, response in enumerate(self.assistant_text_responses):
            content = response
            if self.markdown:
                logger.debug("Converting assistant response to markdown")
                escaped_content = escape_markdown_tags(content, self.tags_to_include_in_markdown)
                content = Markdown(escaped_content)
            
            response_panel = create_panel(
                content=content,
                title=f"Assistant Response {i+1}",
                border_style="blue"
            )
            ordered_panels.append(response_panel)
        
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
        
        # 7. Thinking panel (if we have thinking content)
        if self.show_thinking and self.thinking_content:
            logger.debug("Adding thinking panel")
            thinking_panel = create_panel(
                content=Text(self.thinking_content),
                title=f"Response ({self.timer.elapsed:.1f}s)",
                border_style="green"
            )
            ordered_panels.append(thinking_panel)
        
        # 8. Final response panel (if we have a response)
        if self.response_content:
            content = self.response_content
            if self.markdown:
                logger.debug("Converting response to markdown")
                escaped_content = escape_markdown_tags(content, self.tags_to_include_in_markdown)
                content = Markdown(escaped_content)
            
            response_panel = create_panel(
                content=content,
                title=f"Response ({self.timer.elapsed:.1f}s)",
                border_style="blue"
            )
            ordered_panels.append(response_panel)
        
        try:
            logger.debug(f"Updating live display with {len(ordered_panels)} panels")
            self.live.update(Group(*ordered_panels))
        except Exception as e:
            logger.error(f"Error updating display: {e}")


async def run_example():
    """Example usage of RichUICallback with TinyAgent."""
    import os
    from tinyagent import TinyAgent
    
    # Configure logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Initialize the agent
    agent = TinyAgent(model="gpt-4.1-mini", api_key=api_key)
    
    # Add the Rich UI callback
    rich_ui = RichUICallback(
        markdown=True,
        show_message=True,
        show_thinking=True,
        show_tool_calls=True,
    )
    agent.add_callback(rich_ui)
    
    # Run the agent with a user query
    user_input = "What is the capital of France and what's the population this year?"
    print(f"Running agent with input: {user_input}")
    result = await agent.run(user_input)
    
    print(f"Final result: {result}")
    
    # Clean up
    await agent.close()


if __name__ == "__main__":
    asyncio.run(run_example())