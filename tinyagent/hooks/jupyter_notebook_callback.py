from contextvars import ContextVar
import io
import logging
from contextlib import redirect_stdout
from typing import Any, List, Optional

from IPython.display import display
from ipywidgets import Accordion, HTML, Output, VBox
from rich.console import Console
from rich.logging import RichHandler
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.json import JSON
import json
from rich.rule import Rule

# Context variable to hold the stack of output widgets
_ui_context_stack = ContextVar("ui_context_stack", default=None)


class JupyterNotebookCallback:
    """
    A callback for TinyAgent that provides a rich, hierarchical, and collapsible
    UI within a Jupyter Notebook environment using ipywidgets.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._token = None  # Will only be set for the top-level UI

        # Each instance prepares its container but doesn't show it yet.
        self.main_container = VBox()
        self.root_output = Output()
        self.main_container.children = [self.root_output]

        # Check if a UI context already exists.
        if _ui_context_stack.get() is None:
            # This is the top-level agent. Display the UI and set the context.
            self._token = _ui_context_stack.set([self.root_output])
            display(self.main_container)

    def _get_current_output(self) -> Output:
        """Get the current output widget from the top of the stack."""
        stack = _ui_context_stack.get()
        if not stack:
            raise RuntimeError("UI context stack is not initialized.")
        return stack[-1]

    def _push_output(self, new_output: Output):
        """Push a new output widget onto the stack."""
        stack = _ui_context_stack.get()
        stack.append(new_output)
        _ui_context_stack.set(stack)

    def _pop_output(self):
        """Pop an output widget from the stack."""
        stack = _ui_context_stack.get()
        if len(stack) > 1:
            stack.pop()
            _ui_context_stack.set(stack)

    def _render_to_current_output(self, content: Any):
        """Render content to the current output widget."""
        output_widget = self._get_current_output()
        with output_widget:
            # Create a new console for each render to avoid output duplication
            temp_console = Console(force_jupyter=True)
            temp_console.print(content)

    async def __call__(self, event_name: str, agent: Any, **kwargs: Any) -> None:
        """Main callback entry point."""
        handler = getattr(self, f"_handle_{event_name}", None)
        if handler:
            await handler(agent, **kwargs)

    async def _handle_agent_start(self, agent: Any, **kwargs: Any):
        parent_output = self._get_current_output()

        agent_box = VBox()
        agent_output = Output()
        accordion = Accordion(children=[agent_box])
        
        agent_name = agent.metadata.get("name", f"Agent Run (Session: {agent.session_id})")
        accordion.set_title(0, f"▶️ Agent Start: {agent_name}")
        
        with parent_output:
            display(accordion)

        agent_box.children = (agent_output,)
        self._push_output(agent_output)

    async def _handle_agent_end(self, agent: Any, **kwargs: Any):
        self._pop_output()

    async def _handle_tool_start(self, agent: Any, **kwargs: Any):
        parent_output = self._get_current_output()
        tool_call = kwargs.get("tool_call", {})
        func_info = tool_call.get("function", {})
        tool_name = func_info.get("name", "unknown_tool")

        tool_output = Output()
        accordion = Accordion(children=[tool_output])
        accordion.set_title(0, f"🛠️ Tool Call: {tool_name}")

        with parent_output:
            display(accordion)
        
        try:
            args = json.loads(func_info.get("arguments", "{}"))
            self._render_to_current_output(Panel(JSON(json.dumps(args)), title="Arguments", border_style="cyan"))
        except json.JSONDecodeError:
            self._render_to_current_output(Panel(func_info.get("arguments", "{}"), title="Arguments (raw)", border_style="cyan"))


        self._push_output(tool_output)

    async def _handle_tool_end(self, agent: Any, **kwargs: Any):
        result = kwargs.get("result", "")
        current_output = self._get_current_output()

        try:
            parsed_result = json.loads(result)
            
            if isinstance(parsed_result, dict):
                # It's a dictionary, so we'll make it collapsible.
                item_accordions = []
                for key, value in parsed_result.items():
                    value_output = Output()
                    
                    with value_output:
                        # Render the full value inside the output widget.
                        temp_console = Console(force_jupyter=True)
                        temp_console.print(Text(str(value)))

                    # Create a new accordion for this key-value pair.
                    accordion = Accordion(children=[value_output])
                    
                    # Generate a preview for the accordion title.
                    preview = str(value).split('\n', 1)[0]
                    if len(preview) > 100:
                        preview = preview[:97] + "..."
                    
                    accordion.set_title(0, f"{key}: {preview}")
                    item_accordions.append(accordion)
                
                result_vbox = VBox(item_accordions)

                with current_output:
                    # Render a title for the result section.
                    temp_console = Console(force_jupyter=True)
                    temp_console.print(Rule("[bold green]Result[/bold green]"))
                    # Display the collapsible widgets.
                    display(result_vbox)

            else:
                # It's valid JSON but not a dictionary, so we'll pretty-print it.
                self._render_to_current_output(Panel(JSON(json.dumps(parsed_result)), title="Result", border_style="green"))

        except (json.JSONDecodeError, TypeError):
            # It's not JSON, so we'll display it as plain text.
            self._render_to_current_output(Panel(Text(str(result)), title="Result", border_style="green"))
        
        self._pop_output()

    async def _handle_llm_start(self, agent: Any, **kwargs: Any):
        messages = kwargs.get("messages", [])
        content = Text(f"LLM Call with {len(messages)} messages...", style="bold")
        panel = Panel(content, title="🧠 LLM Start", border_style="magenta")
        self._render_to_current_output(panel)

    async def _handle_message_add(self, agent: Any, **kwargs: Any):
        message = kwargs.get("message", {})
        role = message.get("role")
        content = message.get("content", "")

        if role == "user":
            panel = Panel(Markdown(content), title="👤 User", border_style="bold blue")
            self._render_to_current_output(panel)
        elif role == "assistant" and content:
             panel = Panel(Markdown(content), title="🤖 Assistant", border_style="bold green")
             self._render_to_current_output(panel)

    async def close(self):
        """Clean up resources."""
        # Only the top-level UI that created the context should reset it.
        if self._token:
            _ui_context_stack.reset(self._token)
            self._token = None 