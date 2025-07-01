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


class JupyterNotebookCallback:
    """
    A callback for TinyAgent that provides a rich, hierarchical, and collapsible
    UI within a Jupyter Notebook environment using ipywidgets with enhanced markdown support.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._token = None
        self.agent: Optional[Any] = None

        # 1. Create the main UI structure once.
        self.root_container = VBox()
        self._create_footer()
        self.main_container = VBox([self.root_container, self.footer_box])

        # 2. Set the context stack if this is the top-level UI.
        if _ui_context_stack.get() is None:
            self._token = _ui_context_stack.set([self.root_container])
            # 3. Display the entire structure once. All subsequent updates
            # will manipulate the children of these widgets.
            display(self.main_container)

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
                    asyncio.ensure_future(_run_agent_task(self.agent.run(value, max_turns=3)))
                else:
                    # If no loop is running, create a task
                    asyncio.create_task(_run_agent_task(self.agent.run(value, max_turns=3)))
            except RuntimeError:
                # Fallback for edge cases
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_agent_task(self.agent.run(value, max_turns=3)))

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
                    asyncio.ensure_future(_run_agent_task(self.agent.run(value, max_turns=10)))
                else:
                    # If no loop is running, create a task
                    asyncio.create_task(_run_agent_task(self.agent.run(value, max_turns=10)))
            except RuntimeError:
                # Fallback for edge cases
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(_run_agent_task(self.agent.run(value, max_turns=10)))

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

    # --- Cleanup ---
    async def close(self):
        """Clean up resources."""
        if self._token:
            _ui_context_stack.reset(self._token)
            self._token = None

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