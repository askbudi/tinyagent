from contextvars import ContextVar
import io
import logging
from contextlib import redirect_stdout
from typing import Any, List, Optional
import asyncio
import html
import json
import re

from IPython.display import display
from ipywidgets import Accordion, HTML, Output, VBox, Button, HBox
from ipywidgets import Text as IPyText
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.json import JSON
from rich.rule import Rule

# Import token tracking for usage display
try:
    from .token_tracker import TokenTracker, create_token_tracker
    TOKEN_TRACKING_AVAILABLE = True
except ImportError:
    TOKEN_TRACKING_AVAILABLE = False

# Try to import markdown for enhanced rendering
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

# Context variable to hold the stack of container widgets
_ui_context_stack = ContextVar("ui_context_stack", default=None)


class OptimizedJupyterNotebookCallback:
    """
    An optimized version of JupyterNotebookCallback designed for long agent runs.
    Uses minimal widgets and efficient HTML accumulation to prevent UI freeze.
    """

    def __init__(
        self, 
        logger: Optional[logging.Logger] = None, 
        auto_display: bool = True, 
        max_turns: int = 30,
        max_content_length: int = 100000,  # Limit total HTML content length
        max_visible_turns: int = 20,       # Limit visible conversation turns
        enable_markdown: bool = True,      # Whether to process markdown
        show_raw_responses: bool = False,  # Show raw responses instead of formatted
        enable_token_tracking: bool = True # Whether to show token tracking accordion
    ):
        """
        Initialize the optimized callback.
        
        Args:
            logger: Optional logger instance
            auto_display: Whether to automatically display the UI
            max_turns: Maximum turns for agent runs
            max_content_length: Maximum HTML content length before truncation
            max_visible_turns: Maximum visible conversation turns (older ones get archived)
            enable_markdown: Whether to process markdown (set False for better performance)
            show_raw_responses: Show raw responses instead of formatted (better performance)
            enable_token_tracking: Whether to show token tracking accordion
        """
        self.logger = logger or logging.getLogger(__name__)
        self.max_turns = max_turns
        self.max_content_length = max_content_length
        self.max_visible_turns = max_visible_turns
        self.enable_markdown = enable_markdown
        self.show_raw_responses = show_raw_responses
        self.enable_token_tracking = enable_token_tracking and TOKEN_TRACKING_AVAILABLE
        self.agent: Optional[Any] = None
        self._auto_display = auto_display

        # Content accumulation
        self.content_buffer = []
        self.turn_count = 0
        self.archived_turns = 0

        # Token tracking
        self.token_tracker: Optional[TokenTracker] = None
        self._last_token_update = 0  # Throttle token updates
        self._token_update_interval = 2.0  # Update every 2 seconds at most
        
        # Single widgets for the entire UI
        self.content_html = HTML(value="")
        self._create_footer()
        self._create_token_accordion()
        
        # Build main container with token tracking if enabled
        if self.enable_token_tracking:
            self.main_container = VBox([self.content_html, self.footer_box, self.token_accordion])
        else:
            self.main_container = VBox([self.content_html, self.footer_box])

        if self._auto_display:
            self._initialize_ui()

    def _initialize_ui(self):
        """Initialize the UI display."""
        display(self.main_container)
        self.logger.debug("OptimizedJupyterNotebookCallback UI initialized")

    def _create_footer(self):
        """Creates the footer widgets for user interaction."""
        self.input_text = IPyText(
            placeholder='Send a message to the agent...',
            layout={'width': '70%'},
            disabled=True
        )
        self.submit_button = Button(
            description="Submit",
            tooltip="Send the message to the agent",
            disabled=True,
            button_style='primary'
        )
        self.resume_button = Button(
            description="Resume",
            tooltip="Resume the agent's operation",
            disabled=True
        )
        self.clear_button = Button(
            description="Clear",
            tooltip="Clear the conversation display",
            disabled=False,
            button_style='warning'
        )
        self.footer_box = HBox([self.input_text, self.submit_button, self.resume_button, self.clear_button])

    def _setup_footer_handlers(self):
        """Sets up event handlers for the footer widgets."""
        if not self.agent:
            return

        async def _run_agent_task(coro):
            """Wrapper to run agent tasks and manage widget states."""
            self.input_text.disabled = True
            self.submit_button.disabled = True
            self.resume_button.disabled = True
            try:
                result = await coro
                self.logger.debug(f"Agent task completed with result: {result}")
                return result
            except Exception as e:
                self.logger.error(f"Error running agent from UI: {e}", exc_info=True)
                self._add_content(f'<div style="color: red; padding: 10px; border: 1px solid red; margin: 5px 0;"><strong>Error:</strong> {html.escape(str(e))}</div>')
            finally:
                self.input_text.disabled = False
                self.submit_button.disabled = False
                self.resume_button.disabled = False

        def on_submit(widget):
            value = widget.value
            if not value or not self.agent:
                return
            widget.value = ""
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))
                else:
                    asyncio.create_task(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))

        def on_submit_click(button):
            value = self.input_text.value
            if not value or not self.agent:
                return
            self.input_text.value = ""
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))
                else:
                    asyncio.create_task(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))

        def on_resume_click(button):
            if not self.agent:
                return
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(_run_agent_task(self.agent.resume()))
                else:
                    asyncio.create_task(_run_agent_task(self.agent.resume()))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_agent_task(self.agent.resume()))

        def on_clear_click(button):
            """Clear the conversation display."""
            self.content_buffer = []
            self.turn_count = 0
            self.archived_turns = 0
            self._update_display()

        self.input_text.on_submit(on_submit)
        self.submit_button.on_click(on_submit_click)
        self.resume_button.on_click(on_resume_click)
        self.clear_button.on_click(on_clear_click)

    def _create_token_accordion(self):
        """Create the token tracking accordion widget."""
        if not self.enable_token_tracking:
            self.token_accordion = VBox()  # Empty container
            return
            
        # Create the content area for token information
        self.token_content = HTML(value=self._get_initial_token_display())
        
        # Create refresh button
        self.refresh_tokens_button = Button(
            description="🔄 Refresh",
            tooltip="Refresh token usage information",
            button_style='info',
            layout={'width': 'auto'}
        )
        self.refresh_tokens_button.on_click(self._refresh_token_display)
        
        # Create the accordion content
        token_box = VBox([
            HBox([self.refresh_tokens_button]),
            self.token_content
        ])
        
        # Create the accordion
        self.token_accordion = Accordion(
            children=[token_box],
            titles=["💰 Token Usage & Costs"],
            selected_index=None  # Start collapsed
        )

    def _get_initial_token_display(self) -> str:
        """Get the initial token display HTML."""
        return """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 15px;">
            <div style="color: #666; text-align: center; padding: 20px;">
                <p>🔌 <strong>Token tracking will appear here once the agent starts running.</strong></p>
                <p style="font-size: 0.9em;">Real-time token counts and costs will be displayed automatically.</p>
            </div>
        </div>
        """

    def _refresh_token_display(self, button=None):
        """Refresh the token display manually."""
        if self.token_tracker:
            self._update_token_display()
        else:
            # Try to find token tracker from agent callbacks
            if self.agent and hasattr(self.agent, 'callbacks'):
                for callback in self.agent.callbacks:
                    if hasattr(callback, 'get_total_usage'):  # Duck typing check for TokenTracker
                        self.token_tracker = callback
                        self._update_token_display()
                        return
            
            # No tracker found
            self.token_content.value = """
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 15px;">
                <div style="color: #ff6b6b; text-align: center; padding: 20px; border: 1px solid #ff6b6b; border-radius: 5px; background-color: #fff5f5;">
                    <p><strong>⚠️ No token tracker found</strong></p>
                    <p style="font-size: 0.9em;">Add a TokenTracker to your agent to see usage information:<br>
                    <code>agent.add_callback(create_token_tracker("my_agent"))</code></p>
                </div>
            </div>
            """

    def _update_token_display(self):
        """Update the token display with current usage information."""
        if not self.token_tracker or not self.enable_token_tracking:
            return
            
        try:
            # Get usage data
            total_usage = self.token_tracker.get_total_usage(include_children=True)
            model_breakdown = self.token_tracker.get_model_breakdown(include_children=True)
            provider_breakdown = self.token_tracker.get_provider_breakdown(include_children=True)
            session_duration = self.token_tracker.get_session_duration()
            
            # Build HTML display
            html_content = self._build_token_display_html(
                total_usage, model_breakdown, provider_breakdown, session_duration
            )
            
            self.token_content.value = html_content
            
        except Exception as e:
            self.logger.error(f"Error updating token display: {e}")
            self.token_content.value = f"""
            <div style="color: #ff6b6b; padding: 15px; border: 1px solid #ff6b6b; border-radius: 5px; background-color: #fff5f5;">
                <p><strong>❌ Error updating token display:</strong></p>
                <p style="font-size: 0.9em;">{html.escape(str(e))}</p>
            </div>
            """

    def _build_token_display_html(self, total_usage, model_breakdown, provider_breakdown, session_duration) -> str:
        """Build the HTML content for token display."""
        
        # Main stats
        total_tokens = f"{total_usage.total_tokens:,}" if total_usage.total_tokens else "0"
        total_cost = f"${total_usage.cost:.6f}" if total_usage.cost else "$0.000000"
        api_calls = f"{total_usage.call_count}" if total_usage.call_count else "0"
        duration_mins = f"{session_duration/60:.1f}" if session_duration else "0.0"
        
        html_parts = [
            """
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 15px;">
            """,
            # Main summary
            f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0; font-size: 1.1em;">📊 Overall Usage</h3>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 0.9em;">
                    <div><strong>Total Tokens:</strong> {total_tokens}</div>
                    <div><strong>Total Cost:</strong> {total_cost}</div>
                    <div><strong>API Calls:</strong> {api_calls}</div>
                    <div><strong>Session Time:</strong> {duration_mins} min</div>
                </div>
            </div>
            """
        ]
        
        # Token breakdown
        if total_usage.prompt_tokens or total_usage.completion_tokens:
            html_parts.append(f"""
            <div style="background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 12px; margin-bottom: 15px;">
                <h4 style="margin: 0 0 8px 0; color: #495057; font-size: 1em;">🔢 Token Breakdown</h4>
                <div style="font-size: 0.85em; color: #6c757d;">
                    <div>📝 <strong>Prompt tokens:</strong> {total_usage.prompt_tokens:,}</div>
                    <div>💬 <strong>Completion tokens:</strong> {total_usage.completion_tokens:,}</div>
            """)
            
            # Add special token types if present
            if total_usage.thinking_tokens > 0:
                html_parts.append(f"<div>🤔 <strong>Thinking tokens:</strong> {total_usage.thinking_tokens:,}</div>")
            if total_usage.reasoning_tokens > 0:
                html_parts.append(f"<div>🧠 <strong>Reasoning tokens:</strong> {total_usage.reasoning_tokens:,}</div>")
            if total_usage.cache_creation_input_tokens > 0:
                html_parts.append(f"<div>💾 <strong>Cache creation:</strong> {total_usage.cache_creation_input_tokens:,}</div>")
            if total_usage.cache_read_input_tokens > 0:
                html_parts.append(f"<div>📖 <strong>Cache read:</strong> {total_usage.cache_read_input_tokens:,}</div>")
                
            html_parts.append("</div></div>")
        
        # Model breakdown
        if len(model_breakdown) > 0:
            html_parts.append("""
            <div style="background-color: #e3f2fd; border: 1px solid #bbdefb; border-radius: 6px; padding: 12px; margin-bottom: 15px;">
                <h4 style="margin: 0 0 8px 0; color: #1565c0; font-size: 1em;">🤖 By Model</h4>
                <div style="font-size: 0.85em;">
            """)
            
            for model, stats in sorted(model_breakdown.items(), key=lambda x: x[1].cost, reverse=True):
                cost_str = f"${stats.cost:.6f}" if stats.cost else "$0.000000"
                html_parts.append(f"""
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #e3f2fd;">
                    <span><strong>{html.escape(model)}</strong></span>
                    <span>{stats.total_tokens:,} tokens • {cost_str}</span>
                </div>
                """)
            
            html_parts.append("</div></div>")
        
        # Provider breakdown (if multiple providers)
        if len(provider_breakdown) > 1:
            html_parts.append("""
            <div style="background-color: #e8f5e8; border: 1px solid #c8e6c9; border-radius: 6px; padding: 12px; margin-bottom: 15px;">
                <h4 style="margin: 0 0 8px 0; color: #2e7d32; font-size: 1em;">🏢 By Provider</h4>
                <div style="font-size: 0.85em;">
            """)
            
            for provider, stats in sorted(provider_breakdown.items(), key=lambda x: x[1].cost, reverse=True):
                cost_str = f"${stats.cost:.6f}" if stats.cost else "$0.000000"
                html_parts.append(f"""
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #e8f5e8;">
                    <span><strong>{html.escape(provider.title())}</strong></span>
                    <span>{stats.total_tokens:,} tokens • {cost_str}</span>
                </div>
                """)
            
            html_parts.append("</div></div>")
        
        # Cost efficiency (if we have data)
        if total_usage.call_count > 0 and total_usage.total_tokens > 0:
            avg_cost_per_call = total_usage.cost / total_usage.call_count
            cost_per_1k_tokens = (total_usage.cost / total_usage.total_tokens) * 1000
            
            html_parts.append(f"""
            <div style="background-color: #fff3e0; border: 1px solid #ffcc02; border-radius: 6px; padding: 12px;">
                <h4 style="margin: 0 0 8px 0; color: #ef6c00; font-size: 1em;">💡 Efficiency</h4>
                <div style="font-size: 0.85em; color: #ef6c00;">
                    <div>📊 <strong>Avg cost/call:</strong> ${avg_cost_per_call:.6f}</div>
                    <div>📈 <strong>Cost per 1K tokens:</strong> ${cost_per_1k_tokens:.6f}</div>
                </div>
            </div>
            """)
        
        html_parts.append("</div>")
        
        return "".join(html_parts)

    def _get_base_styles(self) -> str:
        """Get base CSS styles for formatting."""
        return """
        <style>
        .opt-content {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.5;
            padding: 8px;
            margin: 3px 0;
            border-radius: 4px;
            border-left: 3px solid #ddd;
        }
        .opt-user { background-color: #e3f2fd; border-left-color: #2196f3; }
        .opt-assistant { background-color: #e8f5e8; border-left-color: #4caf50; }
        .opt-tool { background-color: #fff3e0; border-left-color: #ff9800; }
        .opt-result { background-color: #f3e5f5; border-left-color: #9c27b0; }
        .opt-code {
            font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 3px;
            padding: 8px;
            margin: 4px 0;
            overflow-x: auto;
            white-space: pre-wrap;
        }
        .opt-summary {
            background-color: #f0f0f0;
            border: 1px solid #ccc;
            padding: 8px;
            margin: 5px 0;
            border-radius: 4px;
            font-size: 0.9em;
        }
        </style>
        """

    def _process_content(self, content: str, content_type: str = "text") -> str:
        """Process content for display with minimal overhead."""
        if self.show_raw_responses:
            return html.escape(str(content))
        
        if content_type == "markdown" and self.enable_markdown and MARKDOWN_AVAILABLE:
            try:
                md = markdown.Markdown(extensions=['fenced_code'])
                return md.convert(content)
            except:
                return html.escape(str(content))
        
        # Simple markdown-like processing for performance
        content = html.escape(str(content))
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
        content = content.replace('\n', '<br>')
        return content

    def _add_content(self, html_content: str):
        """Add content to the buffer and update display."""
        self.content_buffer.append(html_content)
        
        # Limit buffer size to prevent memory issues
        if len(self.content_buffer) > self.max_visible_turns * 5:  # Rough estimate of items per turn
            removed = self.content_buffer.pop(0)
            self.archived_turns += 1
        
        self._update_display()

    def _update_display(self):
        """Update the main HTML widget with accumulated content."""
        # Build the complete HTML
        styles = self._get_base_styles()
        
        content_html = [styles]
        
        # Add archived turns summary if any
        if self.archived_turns > 0:
            content_html.append(
                f'<div class="opt-summary">📁 {self.archived_turns} earlier conversation turns archived for performance</div>'
            )
        
        # Add current content
        content_html.extend(self.content_buffer)
        
        full_html = ''.join(content_html)
        
        # Truncate if too long
        if len(full_html) > self.max_content_length:
            truncate_point = self.max_content_length - 200
            full_html = full_html[:truncate_point] + '<div class="opt-summary">... [Content truncated for performance]</div>'
        
        self.content_html.value = full_html

    async def __call__(self, event_name: str, agent: Any, *args, **kwargs: Any) -> None:
        """
        Main callback entry point.
        
        This method handles both the new interface (kwargs_dict as positional arg)
        and the legacy interface (**kwargs) for backward compatibility.
        """
        # For legacy compatibility, extract kwargs from either interface
        if args and isinstance(args[0], dict):
            # New interface: kwargs_dict passed as positional argument
            event_kwargs = args[0]
        else:
            # Legacy interface: use **kwargs
            event_kwargs = kwargs
            
        if self.agent is None:
            self.agent = agent
            self._setup_footer_handlers()
            self._setup_token_tracking()
            
        handler = getattr(self, f"_handle_{event_name}", None)
        if handler:
            await handler(agent, **event_kwargs)
        
        # Update token display after LLM events (with throttling to prevent UI freeze)
        if event_name in ["llm_end", "agent_end"] and self.enable_token_tracking:
            self._update_token_display_throttled()

    def _update_token_display_throttled(self):
        """Update the token display with throttling to prevent UI freeze."""
        import time
        current_time = time.time()
        
        # Only update if enough time has passed since last update
        if current_time - self._last_token_update < self._token_update_interval:
            return
            
        self._last_token_update = current_time
        self._update_token_display()

    def _setup_token_tracking(self):
        """Set up token tracking by finding or creating a token tracker."""
        if not self.enable_token_tracking or self.token_tracker:
            return
            
        # Try to find existing token tracker in agent callbacks
        if self.agent and hasattr(self.agent, 'callbacks'):
            for callback in self.agent.callbacks:
                if hasattr(callback, 'get_total_usage'):  # Duck typing check for TokenTracker
                    self.token_tracker = callback
                    self.logger.debug(f"Found existing TokenTracker: {callback.name if hasattr(callback, 'name') else type(callback).__name__}")
                    # Force an initial update to populate the display
                    try:
                        self._update_token_display()
                    except Exception as e:
                        self.logger.warning(f"Failed to update token display after setup: {e}")
                    return
        
        # If no tracker found, suggest adding one in the display
        self.logger.debug("No TokenTracker found in agent callbacks")
        # Update display to show the "no tracker" message
        if hasattr(self, 'token_content'):
            self._refresh_token_display()

    async def _handle_agent_start(self, agent: Any, **kwargs: Any):
        """Handle agent start event."""
        self.input_text.disabled = True
        self.submit_button.disabled = True
        self.resume_button.disabled = True
        
        self.turn_count += 1
        agent_name = agent.metadata.get("name", f"Agent Run #{self.turn_count}")
        
        self._add_content(
            f'<div class="opt-content opt-assistant">'
            f'<strong>🚀 Agent Start:</strong> {html.escape(agent_name)} (Session: {agent.session_id})'
            f'</div>'
        )

    async def _handle_agent_end(self, agent: Any, **kwargs: Any):
        """Handle agent end event."""
        self.input_text.disabled = False
        self.submit_button.disabled = False
        self.resume_button.disabled = False
        
        result = kwargs.get("result", "")
        self._add_content(
            f'<div class="opt-content opt-assistant">'
            f'<strong>✅ Agent Completed</strong><br>'
            f'Result: {self._process_content(result)}'
            f'</div>'
        )

    async def _handle_message_add(self, agent: Any, **kwargs: Any):
        """Handle message add event."""
        message = kwargs.get("message", {})
        role = message.get("role")
        content = message.get("content", "")

        if role == "user":
            self._add_content(
                f'<div class="opt-content opt-user">'
                f'<strong>👤 User:</strong><br>'
                f'{self._process_content(content, "markdown")}'
                f'</div>'
            )
        elif role == "assistant" and content:
            self._add_content(
                f'<div class="opt-content opt-assistant">'
                f'<strong>🤖 Assistant:</strong><br>'
                f'{self._process_content(content, "markdown")}'
                f'</div>'
            )

    async def _handle_tool_start(self, agent: Any, **kwargs: Any):
        """Handle tool start event."""
        tool_call = kwargs.get("tool_call", {})
        func_info = tool_call.get("function", {})
        tool_name = func_info.get("name", "unknown_tool")
        
        try:
            args = json.loads(func_info.get("arguments", "{}"))
            args_display = json.dumps(args, indent=2) if args else "No arguments"
        except:
            args_display = func_info.get("arguments", "Invalid JSON")
        
        self._add_content(
            f'<div class="opt-content opt-tool">'
            f'<strong>🛠️ Tool Call:</strong> {html.escape(tool_name)}<br>'
            f'<details><summary>Arguments</summary>'
            f'<pre class="opt-code">{html.escape(args_display)}</pre>'
            f'</details>'
            f'</div>'
        )

    async def _handle_tool_end(self, agent: Any, **kwargs: Any):
        """Handle tool end event."""
        result = kwargs.get("result", "")
        
        # Limit result size for display
        if len(result) > 1000:
            result_display = result[:1000] + "\n... [truncated]"
        else:
            result_display = result
        
        self._add_content(
            f'<div class="opt-content opt-result">'
            f'<strong>📤 Tool Result:</strong><br>'
            f'<details><summary>Show Result</summary>'
            f'<pre class="opt-code">{html.escape(result_display)}</pre>'
            f'</details>'
            f'</div>'
        )

    async def _handle_llm_start(self, agent: Any, **kwargs: Any):
        """Handle LLM start event."""
        messages = kwargs.get("messages", [])
        self._add_content(
            f'<div class="opt-content opt-assistant">'
            f'🧠 <strong>LLM Call</strong> with {len(messages)} messages'
            f'</div>'
        )

    def reinitialize_ui(self):
        """Reinitialize the UI display."""
        self.logger.debug("Reinitializing OptimizedJupyterNotebookCallback UI")
        display(self.main_container)
        if self.agent:
            self._setup_footer_handlers()

    def show_ui(self):
        """Display the UI."""
        display(self.main_container)

    async def close(self):
        """Clean up resources."""
        self.content_buffer = []
        self.logger.debug("OptimizedJupyterNotebookCallback closed")

    async def _handle_agent_cleanup(self, agent: Any, **kwargs: Any):
        """Handle agent cleanup."""
        await self.close()


class JupyterNotebookCallback:
    """
    A callback for TinyAgent that provides a rich, hierarchical, and collapsible
    UI within a Jupyter Notebook environment using ipywidgets with enhanced markdown support.
    """

    def __init__(self, logger: Optional[logging.Logger] = None, auto_display: bool = True, max_turns: int = 30, enable_token_tracking: bool = True):
        self.logger = logger or logging.getLogger(__name__)
        self.max_turns = max_turns
        self._token = None
        self.agent: Optional[Any] = None
        self._auto_display = auto_display
        self.enable_token_tracking = enable_token_tracking and TOKEN_TRACKING_AVAILABLE

        # Token tracking
        self.token_tracker: Optional[TokenTracker] = None
        self._last_token_update = 0  # Throttle token updates
        self._token_update_interval = 2.0  # Update every 2 seconds at most

        # 1. Create the main UI structure for this instance.
        self.root_container = VBox()
        self._create_footer()
        self._create_token_accordion()
        
        # Build main container with token tracking if enabled
        if self.enable_token_tracking:
            self.main_container = VBox([self.root_container, self.footer_box, self.token_accordion])
        else:
            self.main_container = VBox([self.root_container, self.footer_box])

        # 2. Always set up a new context stack for this instance.
        # This ensures each callback instance gets its own UI display.
        if self._auto_display:
            self._initialize_ui()

    def _initialize_ui(self):
        """Initialize the UI display for this callback instance."""
        # Reset any existing context to ensure clean state
        try:
            # Clear any existing context for this instance
            if _ui_context_stack.get() is not None:
                # If there's an existing context, we'll create our own fresh one
                pass
        except LookupError:
            # No existing context, which is fine
            pass
        
        # Set up our own context stack
        self._token = _ui_context_stack.set([self.root_container])
        
        # Display the entire structure for this instance
        display(self.main_container)
        
        self.logger.debug("JupyterNotebookCallback UI initialized and displayed")

    def _create_footer(self):
        """Creates the footer widgets for user interaction."""
        self.input_text = IPyText(
            placeholder='Send a message to the agent...',
            layout={'width': '70%'},
            disabled=True
        )
        self.submit_button = Button(
            description="Submit",
            tooltip="Send the message to the agent",
            disabled=True,
            button_style='primary'
        )
        self.resume_button = Button(
            description="Resume",
            tooltip="Resume the agent's operation",
            disabled=True
        )
        self.footer_box = HBox([self.input_text, self.submit_button, self.resume_button])

    def _setup_footer_handlers(self):
        """Sets up event handlers for the footer widgets."""
        if not self.agent:
            return

        async def _run_agent_task(coro):
            """Wrapper to run agent tasks and manage widget states."""
            self.input_text.disabled = True
            self.submit_button.disabled = True
            self.resume_button.disabled = True
            try:
                result = await coro
                self.logger.debug(f"Agent task completed with result: {result}")
                return result
            except Exception as e:
                self.logger.error(f"Error running agent from UI: {e}", exc_info=True)
                # Create an error HTML widget to show the error to the user
                container = self._get_current_container()
                error_html = HTML(value=f"<div style='color: red; padding: 10px; border: 1px solid red;'><strong>Error:</strong> {html.escape(str(e))}</div>")
                container.children += (error_html,)
            finally:
                # agent_end event re-enables widgets, but this is a fallback.
                self.input_text.disabled = False
                self.submit_button.disabled = False
                self.resume_button.disabled = False

        def on_submit(widget):
            value = widget.value
            if not value or not self.agent:
                return
            widget.value = ""
            
            # Use asyncio.ensure_future instead of create_task for better Jupyter compatibility
            try:
                # Get the current event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If the loop is already running (typical in Jupyter), use ensure_future
                    asyncio.ensure_future(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))
                else:
                    # If no loop is running, create a task
                    asyncio.create_task(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))
            except RuntimeError:
                # Fallback for edge cases
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))

        def on_submit_click(button):
            value = self.input_text.value
            if not value or not self.agent:
                return
            self.input_text.value = ""
            
            # Use asyncio.ensure_future instead of create_task for better Jupyter compatibility
            try:
                # Get the current event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If the loop is already running (typical in Jupyter), use ensure_future
                    asyncio.ensure_future(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))
                else:
                    # If no loop is running, create a task
                    asyncio.create_task(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))
            except RuntimeError:
                # Fallback for edge cases
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_agent_task(self.agent.run(value, max_turns=self.max_turns)))

        def on_resume_click(button):
            if not self.agent:
                return
            
            # Use asyncio.ensure_future instead of create_task for better Jupyter compatibility
            try:
                # Get the current event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If the loop is already running (typical in Jupyter), use ensure_future
                    asyncio.ensure_future(_run_agent_task(self.agent.resume()))
                else:
                    # If no loop is running, create a task
                    asyncio.create_task(_run_agent_task(self.agent.resume()))
            except RuntimeError:
                # Fallback for edge cases
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_agent_task(self.agent.resume()))

        self.input_text.on_submit(on_submit)
        self.submit_button.on_click(on_submit_click)
        self.resume_button.on_click(on_resume_click)

    def _create_token_accordion(self):
        """Create the token tracking accordion widget."""
        if not self.enable_token_tracking:
            self.token_accordion = VBox()  # Empty container
            return
            
        # Create the content area for token information
        self.token_content = HTML(value=self._get_initial_token_display())
        
        # Create refresh button
        self.refresh_tokens_button = Button(
            description="🔄 Refresh",
            tooltip="Refresh token usage information",
            button_style='info',
            layout={'width': 'auto'}
        )
        self.refresh_tokens_button.on_click(self._refresh_token_display)
        
        # Create the accordion content
        token_box = VBox([
            HBox([self.refresh_tokens_button]),
            self.token_content
        ])
        
        # Create the accordion
        self.token_accordion = Accordion(
            children=[token_box],
            titles=["💰 Token Usage & Costs"],
            selected_index=None  # Start collapsed
        )

    def _get_initial_token_display(self) -> str:
        """Get the initial token display HTML."""
        return """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 15px;">
            <div style="color: #666; text-align: center; padding: 20px;">
                <p>🔌 <strong>Token tracking will appear here once the agent starts running.</strong></p>
                <p style="font-size: 0.9em;">Real-time token counts and costs will be displayed automatically.</p>
            </div>
        </div>
        """

    def _refresh_token_display(self, button=None):
        """Refresh the token display manually."""
        if self.token_tracker:
            self._update_token_display()
        else:
            # Try to find token tracker from agent callbacks
            if self.agent and hasattr(self.agent, 'callbacks'):
                for callback in self.agent.callbacks:
                    if hasattr(callback, 'get_total_usage'):  # Duck typing check for TokenTracker
                        self.token_tracker = callback
                        self._update_token_display()
                        return
            
            # No tracker found
            self.token_content.value = """
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 15px;">
                <div style="color: #ff6b6b; text-align: center; padding: 20px; border: 1px solid #ff6b6b; border-radius: 5px; background-color: #fff5f5;">
                    <p><strong>⚠️ No token tracker found</strong></p>
                    <p style="font-size: 0.9em;">Add a TokenTracker to your agent to see usage information:<br>
                    <code>agent.add_callback(create_token_tracker("my_agent"))</code></p>
                </div>
            </div>
            """

    def _update_token_display(self):
        """Update the token display with current usage information."""
        if not self.token_tracker or not self.enable_token_tracking:
            return
            
        try:
            # Get usage data
            total_usage = self.token_tracker.get_total_usage(include_children=True)
            model_breakdown = self.token_tracker.get_model_breakdown(include_children=True)
            provider_breakdown = self.token_tracker.get_provider_breakdown(include_children=True)
            session_duration = self.token_tracker.get_session_duration()
            
            # Build HTML display
            html_content = self._build_token_display_html(
                total_usage, model_breakdown, provider_breakdown, session_duration
            )
            
            self.token_content.value = html_content
            
        except Exception as e:
            self.logger.error(f"Error updating token display: {e}")
            self.token_content.value = f"""
            <div style="color: #ff6b6b; padding: 15px; border: 1px solid #ff6b6b; border-radius: 5px; background-color: #fff5f5;">
                <p><strong>❌ Error updating token display:</strong></p>
                <p style="font-size: 0.9em;">{html.escape(str(e))}</p>
            </div>
            """

    def _build_token_display_html(self, total_usage, model_breakdown, provider_breakdown, session_duration) -> str:
        """Build the HTML content for token display."""
        
        # Main stats
        total_tokens = f"{total_usage.total_tokens:,}" if total_usage.total_tokens else "0"
        total_cost = f"${total_usage.cost:.6f}" if total_usage.cost else "$0.000000"
        api_calls = f"{total_usage.call_count}" if total_usage.call_count else "0"
        duration_mins = f"{session_duration/60:.1f}" if session_duration else "0.0"
        
        html_parts = [
            """
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 15px;">
            """,
            # Main summary
            f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                <h3 style="margin: 0 0 10px 0; font-size: 1.1em;">📊 Overall Usage</h3>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 0.9em;">
                    <div><strong>Total Tokens:</strong> {total_tokens}</div>
                    <div><strong>Total Cost:</strong> {total_cost}</div>
                    <div><strong>API Calls:</strong> {api_calls}</div>
                    <div><strong>Session Time:</strong> {duration_mins} min</div>
                </div>
            </div>
            """
        ]
        
        # Token breakdown
        if total_usage.prompt_tokens or total_usage.completion_tokens:
            html_parts.append(f"""
            <div style="background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 12px; margin-bottom: 15px;">
                <h4 style="margin: 0 0 8px 0; color: #495057; font-size: 1em;">🔢 Token Breakdown</h4>
                <div style="font-size: 0.85em; color: #6c757d;">
                    <div>📝 <strong>Prompt tokens:</strong> {total_usage.prompt_tokens:,}</div>
                    <div>💬 <strong>Completion tokens:</strong> {total_usage.completion_tokens:,}</div>
            """)
            
            # Add special token types if present
            if total_usage.thinking_tokens > 0:
                html_parts.append(f"<div>🤔 <strong>Thinking tokens:</strong> {total_usage.thinking_tokens:,}</div>")
            if total_usage.reasoning_tokens > 0:
                html_parts.append(f"<div>🧠 <strong>Reasoning tokens:</strong> {total_usage.reasoning_tokens:,}</div>")
            if total_usage.cache_creation_input_tokens > 0:
                html_parts.append(f"<div>💾 <strong>Cache creation:</strong> {total_usage.cache_creation_input_tokens:,}</div>")
            if total_usage.cache_read_input_tokens > 0:
                html_parts.append(f"<div>📖 <strong>Cache read:</strong> {total_usage.cache_read_input_tokens:,}</div>")
                
            html_parts.append("</div></div>")
        
        # Model breakdown
        if len(model_breakdown) > 0:
            html_parts.append("""
            <div style="background-color: #e3f2fd; border: 1px solid #bbdefb; border-radius: 6px; padding: 12px; margin-bottom: 15px;">
                <h4 style="margin: 0 0 8px 0; color: #1565c0; font-size: 1em;">🤖 By Model</h4>
                <div style="font-size: 0.85em;">
            """)
            
            for model, stats in sorted(model_breakdown.items(), key=lambda x: x[1].cost, reverse=True):
                cost_str = f"${stats.cost:.6f}" if stats.cost else "$0.000000"
                html_parts.append(f"""
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #e3f2fd;">
                    <span><strong>{html.escape(model)}</strong></span>
                    <span>{stats.total_tokens:,} tokens • {cost_str}</span>
                </div>
                """)
            
            html_parts.append("</div></div>")
        
        # Provider breakdown (if multiple providers)
        if len(provider_breakdown) > 1:
            html_parts.append("""
            <div style="background-color: #e8f5e8; border: 1px solid #c8e6c9; border-radius: 6px; padding: 12px; margin-bottom: 15px;">
                <h4 style="margin: 0 0 8px 0; color: #2e7d32; font-size: 1em;">🏢 By Provider</h4>
                <div style="font-size: 0.85em;">
            """)
            
            for provider, stats in sorted(provider_breakdown.items(), key=lambda x: x[1].cost, reverse=True):
                cost_str = f"${stats.cost:.6f}" if stats.cost else "$0.000000"
                html_parts.append(f"""
                <div style="display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #e8f5e8;">
                    <span><strong>{html.escape(provider.title())}</strong></span>
                    <span>{stats.total_tokens:,} tokens • {cost_str}</span>
                </div>
                """)
            
            html_parts.append("</div></div>")
        
        # Cost efficiency (if we have data)
        if total_usage.call_count > 0 and total_usage.total_tokens > 0:
            avg_cost_per_call = total_usage.cost / total_usage.call_count
            cost_per_1k_tokens = (total_usage.cost / total_usage.total_tokens) * 1000
            
            html_parts.append(f"""
            <div style="background-color: #fff3e0; border: 1px solid #ffcc02; border-radius: 6px; padding: 12px;">
                <h4 style="margin: 0 0 8px 0; color: #ef6c00; font-size: 1em;">💡 Efficiency</h4>
                <div style="font-size: 0.85em; color: #ef6c00;">
                    <div>📊 <strong>Avg cost/call:</strong> ${avg_cost_per_call:.6f}</div>
                    <div>📈 <strong>Cost per 1K tokens:</strong> ${cost_per_1k_tokens:.6f}</div>
                </div>
            </div>
            """)
        
        html_parts.append("</div>")
        
        return "".join(html_parts)

    def _setup_token_tracking(self):
        """Set up token tracking by finding or creating a token tracker."""
        if not self.enable_token_tracking or self.token_tracker:
            return
            
        # Try to find existing token tracker in agent callbacks
        if self.agent and hasattr(self.agent, 'callbacks'):
            for callback in self.agent.callbacks:
                if hasattr(callback, 'get_total_usage'):  # Duck typing check for TokenTracker
                    self.token_tracker = callback
                    self.logger.debug("Found existing TokenTracker in agent callbacks")
                    return
        
        # If no tracker found, suggest adding one in the display
        self.logger.debug("No TokenTracker found in agent callbacks")

    # --- Context Stack Management ---
    def _get_current_container(self) -> VBox:
        """Get the current container widget from the top of the stack."""
        stack = _ui_context_stack.get()
        if not stack:
            raise RuntimeError("UI context stack is not initialized.")
        return stack[-1]

    def _push_container(self, new_container: VBox):
        """Push a new container widget onto the stack."""
        stack = _ui_context_stack.get()
        stack.append(new_container)
        _ui_context_stack.set(stack)

    def _pop_container(self):
        """Pop a container widget from the stack."""
        stack = _ui_context_stack.get()
        if len(stack) > 1:
            stack.pop()
        _ui_context_stack.set(stack)

    # --- Enhanced Rendering Logic ---
    def _get_base_styles(self) -> str:
        """Get base CSS styles for better formatting."""
        return """
        <style>
        .tinyagent-content {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            padding: 12px;
            margin: 5px 0;
            border-radius: 6px;
        }
        .tinyagent-code {
            font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
            background-color: #f6f8fa;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 12px;
            margin: 8px 0;
            overflow-x: auto;
            white-space: pre-wrap;
        }
        .tinyagent-inline-code {
            font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
            background-color: rgba(175, 184, 193, 0.2);
            padding: 2px 4px;
            border-radius: 3px;
            font-size: 0.9em;
        }
        .tinyagent-key {
            font-weight: 600;
            color: #0969da;
        }
        .tinyagent-value {
            color: #656d76;
        }
        .tinyagent-json {
            background-color: #f6f8fa;
            border-left: 4px solid #0969da;
            padding: 12px;
            margin: 8px 0;
            border-radius: 0 6px 6px 0;
        }
        </style>
        """

    def _process_markdown(self, content: str) -> str:
        """Process markdown content and return HTML."""
        if not MARKDOWN_AVAILABLE:
            # Fallback: simple processing for basic markdown
            content = self._simple_markdown_fallback(content)
            return content
        
        # Use full markdown processing
        md = markdown.Markdown(extensions=['fenced_code', 'codehilite', 'tables'])
        return md.convert(content)

    def _simple_markdown_fallback(self, content: str) -> str:
        """Simple markdown processing when markdown library is not available."""
        # Basic markdown patterns
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)  # Bold
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)  # Italic
        content = re.sub(r'`([^`]+)`', r'<code class="tinyagent-inline-code">\1</code>', content)  # Inline code
        
        # Code blocks
        content = re.sub(r'```(\w+)?\n(.*?)\n```', 
                        r'<pre class="tinyagent-code">\2</pre>', 
                        content, flags=re.DOTALL)
        
        # Convert newlines to <br>
        content = content.replace('\n', '<br>')
        
        return content

    def _format_key_value_pairs(self, data: dict, max_value_length: int = 200) -> str:
        """Format key-value pairs in a human-readable way."""
        formatted_items = []
        
        for key, value in data.items():
            # Format the key
            key_html = f'<span class="tinyagent-key">{html.escape(str(key))}</span>'
            
            # Format the value based on its type
            if isinstance(value, str):
                # Check if it looks like code or JSON
                if value.strip().startswith(('{', '[')) or '\n' in value:
                    if len(value) > max_value_length:
                        value = value[:max_value_length] + "... (truncated)"
                    value_html = f'<pre class="tinyagent-code">{html.escape(value)}</pre>'
                else:
                    # Process as potential markdown
                    if len(value) > max_value_length:
                        value = value[:max_value_length] + "... (truncated)"
                    value_html = f'<span class="tinyagent-value">{self._process_markdown(value)}</span>'
            elif isinstance(value, (dict, list)):
                # JSON-like formatting
                json_str = json.dumps(value, indent=2, ensure_ascii=False)
                if len(json_str) > max_value_length:
                    json_str = json_str[:max_value_length] + "... (truncated)"
                value_html = f'<div class="tinyagent-json"><pre>{html.escape(json_str)}</pre></div>'
            else:
                value_html = f'<span class="tinyagent-value">{html.escape(str(value))}</span>'
            
            formatted_items.append(f'{key_html}: {value_html}')
        
        return '<br>'.join(formatted_items)

    def _create_enhanced_html_widget(self, content: str, style: str = "", content_type: str = "text") -> HTML:
        """Create an enhanced HTML widget with better formatting."""
        base_style = "font-family: inherit; margin: 5px 0;"
        full_style = base_style + style
        
        # Add base styles
        styles = self._get_base_styles()
        
        if content_type == "markdown":
            processed_content = self._process_markdown(content)
            html_content = f'{styles}<div class="tinyagent-content" style="{full_style}">{processed_content}</div>'
        elif content_type == "code":
            escaped_content = html.escape(str(content))
            html_content = f'{styles}<div style="{full_style}"><pre class="tinyagent-code">{escaped_content}</pre></div>'
        elif content_type == "json":
            try:
                parsed = json.loads(content)
                formatted_json = json.dumps(parsed, indent=2, ensure_ascii=False)
                escaped_content = html.escape(formatted_json)
                html_content = f'{styles}<div style="{full_style}"><div class="tinyagent-json"><pre>{escaped_content}</pre></div></div>'
            except:
                escaped_content = html.escape(str(content))
                html_content = f'{styles}<div style="{full_style}"><pre class="tinyagent-code">{escaped_content}</pre></div>'
        else:
            escaped_content = html.escape(str(content))
            html_content = f'{styles}<div class="tinyagent-content" style="{full_style}">{escaped_content}</div>'
        
        return HTML(value=html_content)

    def _render_enhanced_text(self, content: str, title: str = "", style: str = "", content_type: str = "markdown"):
        """Render text content using enhanced HTML widgets with markdown support."""
        container = self._get_current_container()
        
        if title:
            title_style = "font-weight: bold; color: #2196F3; border-bottom: 1px solid #ccc; margin-bottom: 10px; padding-bottom: 5px;"
            title_widget = HTML(value=f'{self._get_base_styles()}<div style="{title_style}">{html.escape(title)}</div>')
            container.children += (title_widget,)
        
        content_widget = self._create_enhanced_html_widget(content, style, content_type)
        container.children += (content_widget,)

    # --- Main Callback Entry Point ---
    async def __call__(self, event_name: str, agent: Any, *args, **kwargs: Any) -> None:
        """
        Main callback entry point.
        
        This method handles both the new interface (kwargs_dict as positional arg)
        and the legacy interface (**kwargs) for backward compatibility.
        """
        # For legacy compatibility, extract kwargs from either interface
        if args and isinstance(args[0], dict):
            # New interface: kwargs_dict passed as positional argument
            event_kwargs = args[0]
        else:
            # Legacy interface: use **kwargs
            event_kwargs = kwargs
            
        if self.agent is None:
            self.agent = agent
            self._setup_footer_handlers()
            self._setup_token_tracking()
            
        handler = getattr(self, f"_handle_{event_name}", None)
        if handler:
            await handler(agent, **event_kwargs)
        
        # Update token display after LLM events (with throttling to prevent UI freeze)
        if event_name in ["llm_end", "agent_end"] and self.enable_token_tracking:
            self._update_token_display_throttled()

    # --- Event Handlers ---
    async def _handle_agent_start(self, agent: Any, **kwargs: Any):
        parent_container = self._get_current_container()
        self.input_text.disabled = True
        self.submit_button.disabled = True
        self.resume_button.disabled = True

        agent_content_box = VBox()
        agent_name = agent.metadata.get("name", f"Agent Run (Session: {agent.session_id})")
        accordion = Accordion(children=[agent_content_box], titles=[f"▶️ Agent Start: {agent_name}"])
        
        parent_container.children += (accordion,)
        self._push_container(agent_content_box)

    async def _handle_agent_end(self, agent: Any, **kwargs: Any):
        self._pop_container()
        self.input_text.disabled = False
        self.submit_button.disabled = False
        self.resume_button.disabled = False

    async def _handle_tool_start(self, agent: Any, **kwargs: Any):
        parent_container = self._get_current_container()
        tool_call = kwargs.get("tool_call", {})
        func_info = tool_call.get("function", {})
        tool_name = func_info.get("name", "unknown_tool")

        tool_content_box = VBox()
        accordion = Accordion(children=[tool_content_box], titles=[f"🛠️ Tool Call: {tool_name}"])

        parent_container.children += (accordion,)
        
        # Render arguments with enhanced formatting
        try:
            args = json.loads(func_info.get("arguments", "{}"))
            if args:
                self._push_container(tool_content_box)
                args_html = self._format_key_value_pairs(args)
                styles = self._get_base_styles()
                widget = HTML(value=f'{styles}<div class="tinyagent-content" style="background-color: #e3f2fd;"><strong>Arguments:</strong><br>{args_html}</div>')
                tool_content_box.children += (widget,)
                self._pop_container()
            else:
                self._push_container(tool_content_box)
                self._render_enhanced_text("No arguments", style="background-color: #f5f5f5;")
                self._pop_container()
        except json.JSONDecodeError:
            # Fallback for invalid JSON
            self._push_container(tool_content_box)
            self._render_enhanced_text(f"**Arguments (raw):**\n```\n{func_info.get('arguments', '{}')}\n```", 
                                     style="background-color: #fff3e0;", content_type="markdown")
            self._pop_container()

        self._push_container(tool_content_box)

    async def _handle_tool_end(self, agent: Any, **kwargs: Any):
        result = kwargs.get("result", "")
        
        try:
            # Try to parse as JSON first
            parsed_result = json.loads(result)
            if isinstance(parsed_result, dict):
                # Create enhanced output for dictionary results
                result_html = self._format_key_value_pairs(parsed_result)
                styles = self._get_base_styles()
                widget = HTML(value=f'{styles}<div class="tinyagent-content" style="background-color: #e8f5e8; border-left: 3px solid #4caf50;"><strong>Result:</strong><br>{result_html}</div>')
                container = self._get_current_container()
                container.children += (widget,)
            else:
                # Non-dictionary JSON result
                self._render_enhanced_text(f"**Result:**\n```json\n{json.dumps(parsed_result, indent=2)}\n```", 
                                         style="background-color: #e8f5e8; border-left: 3px solid #4caf50;", 
                                         content_type="markdown")

        except (json.JSONDecodeError, TypeError):
            # Not JSON, treat as potential markdown
            # Check if it looks like code or structured data
            if result.strip().startswith(('{', '[', '<')) or '\n' in result:
                self._render_enhanced_text(f"**Result:**\n```\n{result}\n```", 
                                         style="background-color: #e8f5e8; border-left: 3px solid #4caf50;", 
                                         content_type="markdown")
            else:
                self._render_enhanced_text(f"**Result:** {result}", 
                                         style="background-color: #e8f5e8; border-left: 3px solid #4caf50;", 
                                         content_type="markdown")
        
        # Finally, pop the container off the stack
        self._pop_container()

    async def _handle_llm_start(self, agent: Any, **kwargs: Any):
        messages = kwargs.get("messages", [])
        text = f"🧠 **LLM Start:** Calling model with {len(messages)} messages..."
        self._render_enhanced_text(text, style="background-color: #f3e5f5; border-left: 3px solid #9c27b0;", content_type="markdown")

    async def _handle_message_add(self, agent: Any, **kwargs: Any):
        message = kwargs.get("message", {})
        role = message.get("role")
        content = message.get("content", "")

        if role == "user":
            self._render_enhanced_text(f"👤 **User:**\n\n{content}", 
                                     style="background-color: #e3f2fd; border-left: 3px solid #2196f3;", 
                                     content_type="markdown")
        elif role == "assistant" and content:
            self._render_enhanced_text(f"🤖 **Assistant:**\n\n{content}", 
                                     style="background-color: #e8f5e8; border-left: 3px solid #4caf50;", 
                                     content_type="markdown")

    # --- UI Management ---
    def reinitialize_ui(self):
        """Reinitialize the UI display. Useful if UI disappeared after creating new agents."""
        self.logger.debug("Reinitializing JupyterNotebookCallback UI")
        
        # Clean up existing context if any
        if self._token:
            try:
                _ui_context_stack.reset(self._token)
            except LookupError:
                # Context was already reset, which is fine
                pass
            self._token = None
        
        # Clear existing children to avoid duplicates
        self.root_container.children = ()
        
        # Reinitialize the UI
        self._initialize_ui()
        
        # Re-setup handlers if agent is available
        if self.agent:
            self._setup_footer_handlers()

    def show_ui(self):
        """Display the UI if it's not already shown."""
        if not self._token:
            self._initialize_ui()
        else:
            # UI is already initialized, just display it again
            display(self.main_container)

    # --- Cleanup ---
    async def close(self):
        """Clean up resources."""
        if self._token:
            try:
                _ui_context_stack.reset(self._token)
            except LookupError:
                # Context was already reset, which is fine
                pass
            self._token = None
        self.logger.debug("JupyterNotebookCallback closed and cleaned up")

    async def _handle_agent_cleanup(self, agent: Any, **kwargs: Any):
        """Handle agent cleanup to reset the UI context."""
        await self.close()


async def run_example():
    """Example usage of JupyterNotebookCallback with TinyAgent in Jupyter."""
    import os
    from tinyagent import TinyAgent
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Initialize the agent
    agent = TinyAgent(model="gpt-5-mini", api_key=api_key)
    
    # Add the Jupyter Notebook callback
    jupyter_ui = JupyterNotebookCallback()
    agent.add_callback(jupyter_ui)
    
    # Connect to MCP servers as per contribution guide
    await agent.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    print("Enhanced JupyterNotebookCallback example setup complete. Use the input field above to interact with the agent.")
    
    # Clean up
    # await agent.close()  # Commented out so the UI remains active for interaction

async def run_optimized_example():
    """Example usage of OptimizedJupyterNotebookCallback with TinyAgent in Jupyter."""
    import os
    from tinyagent import TinyAgent
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Initialize the agent
    agent = TinyAgent(model="gpt-5-mini", api_key=api_key)
    
    # Add the OPTIMIZED Jupyter Notebook callback for better performance
    jupyter_ui = OptimizedJupyterNotebookCallback(
        max_visible_turns=15,     # Limit visible turns
        max_content_length=50000, # Limit total content
        enable_markdown=True,     # Keep markdown but optimized
        show_raw_responses=False  # Show formatted responses
    )
    agent.add_callback(jupyter_ui)
    
    # Connect to MCP servers as per contribution guide
    await agent.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    print("OptimizedJupyterNotebookCallback example setup complete. This version handles long agent runs much better!")
    
    # Clean up
    # await agent.close()  # Commented out so the UI remains active for interaction 