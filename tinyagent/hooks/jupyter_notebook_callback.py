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
        show_raw_responses: bool = False   # Show raw responses instead of formatted
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
        """
        self.logger = logger or logging.getLogger(__name__)
        self.max_turns = max_turns
        self.max_content_length = max_content_length
        self.max_visible_turns = max_visible_turns
        self.enable_markdown = enable_markdown
        self.show_raw_responses = show_raw_responses
        self.agent: Optional[Any] = None
        self._auto_display = auto_display

        # Content accumulation
        self.content_buffer = []
        self.turn_count = 0
        self.archived_turns = 0

        # Single widgets for the entire UI
        self.content_html = HTML(value="")
        self._create_footer()
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

    async def __call__(self, event_name: str, agent: Any, **kwargs: Any) -> None:
        """Main callback entry point."""
        if self.agent is None:
            self.agent = agent
            self._setup_footer_handlers()
            
        handler = getattr(self, f"_handle_{event_name}", None)
        if handler:
            await handler(agent, **kwargs)

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

    def __init__(self, logger: Optional[logging.Logger] = None, auto_display: bool = True, max_turns: int = 30):
        self.logger = logger or logging.getLogger(__name__)
        self.max_turns = max_turns
        self._token = None
        self.agent: Optional[Any] = None
        self._auto_display = auto_display

        # 1. Create the main UI structure for this instance.
        self.root_container = VBox()
        self._create_footer()
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
    async def __call__(self, event_name: str, agent: Any, **kwargs: Any) -> None:
        """Main callback entry point."""
        if self.agent is None:
            self.agent = agent
            self._setup_footer_handlers()
            
        handler = getattr(self, f"_handle_{event_name}", None)
        if handler:
            await handler(agent, **kwargs)

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
    agent = TinyAgent(model="gpt-4.1-mini", api_key=api_key)
    
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
    agent = TinyAgent(model="gpt-4.1-mini", api_key=api_key)
    
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