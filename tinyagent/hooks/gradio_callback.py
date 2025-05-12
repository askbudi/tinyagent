import asyncio
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import tiktoken
from tinyagent import TinyAgent

# Check if gradio is available
try:
    import gradio as gr
except ImportError:
    raise ModuleNotFoundError(
        "Please install 'gradio' to use the GradioCallback: `pip install gradio`"
    )


class GradioCallback:
    """
    A callback for TinyAgent that provides a Gradio web interface.
    This allows for interactive chat with the agent through a web UI.
    """
    
    def __init__(
        self,
        file_upload_folder: Optional[str] = None,
        allowed_file_types: Optional[List[str]] = None,
        show_thinking: bool = True,
        show_tool_calls: bool = True,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Gradio callback.
        
        Args:
            file_upload_folder: Optional folder to store uploaded files
            allowed_file_types: List of allowed file extensions (default: [".pdf", ".docx", ".txt"])
            show_thinking: Whether to show the thinking process
            show_tool_calls: Whether to show tool calls
            logger: Optional logger to use
        """
        self.logger = logger or logging.getLogger(__name__)
        self.show_thinking = show_thinking
        self.show_tool_calls = show_tool_calls
        
        # File upload settings
        self.file_upload_folder = Path(file_upload_folder) if file_upload_folder else None
        self.allowed_file_types = allowed_file_types or [".pdf", ".docx", ".txt"]
        
        if self.file_upload_folder and not self.file_upload_folder.exists():
            self.file_upload_folder.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Created file upload folder: {self.file_upload_folder}")
        
        # Initialize tiktoken encoder for token counting
        try:
            self.encoder = tiktoken.get_encoding("o200k_base")
            self.logger.debug("Initialized tiktoken encoder with o200k_base encoding")
        except Exception as e:
            self.logger.error(f"Failed to initialize tiktoken encoder: {e}")
            self.encoder = None
        
        # State tracking for the current agent interaction
        self.current_agent = None
        self.current_user_input = ""
        self.thinking_content = ""
        self.tool_calls = []
        self.tool_call_details = []
        self.assistant_text_responses = []
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.is_running = False
        self.last_update_yield_time = 0

        # References to Gradio UI components (will be set in create_app)
        self._chatbot_component = None
        self._token_usage_component = None

        self.logger.debug("GradioCallback initialized")
    
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
        self.logger.debug(f"Callback Event: {event_name}")
        self.current_agent = agent
        
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
    
    async def _handle_agent_start(self, agent: Any, **kwargs: Any) -> None:
        """Handle the agent_start event. Reset state."""
        self.logger.debug("Handling agent_start event")
        self.current_user_input = kwargs.get("user_input", "")
        self.thinking_content = ""
        self.tool_calls = []
        self.tool_call_details = []
        self.assistant_text_responses = []
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.is_running = True
        self.last_update_yield_time = 0
        self.logger.debug(f"Agent started for input: {self.current_user_input[:50]}...")
    
    async def _handle_message_add(self, agent: Any, **kwargs: Any) -> None:
        """Handle the message_add event. Store message details."""
        message = kwargs.get("message", {})
        role = message.get("role", "unknown")
        self.logger.debug(f"Handling message_add event: {role}")
        current_time = asyncio.get_event_loop().time()

        if role == "assistant":
            if "tool_calls" in message and message.get("tool_calls"):
                self.logger.debug(f"Processing {len(message['tool_calls'])} tool calls")
                for tool_call in message["tool_calls"]:
                    function_info = tool_call.get("function", {})
                    tool_name = function_info.get("name", "unknown")
                    args = function_info.get("arguments", "{}")
                    tool_id = tool_call.get("id", "unknown")

                    try:
                        # Attempt pretty formatting, fallback to raw string
                        parsed_args = json.loads(args)
                        formatted_args = json.dumps(parsed_args, indent=2)
                    except json.JSONDecodeError:
                        formatted_args = args # Keep as is if not valid JSON

                    token_count = self.count_tokens(f"{tool_name}({formatted_args})") # Count formatted

                    # Add to detailed tool call info if not already present by ID
                    if not any(tc['id'] == tool_id for tc in self.tool_call_details):
                        self.tool_call_details.append({
                            "id": tool_id,
                            "name": tool_name,
                            "arguments": formatted_args,
                            "result": None,
                            "token_count": token_count,
                            "result_token_count": 0,
                            "timestamp": current_time,
                            "result_timestamp": None
                        })
                        self.logger.debug(f"Added tool call detail: {tool_name} (ID: {tool_id}, Tokens: {token_count})")
                    else:
                         self.logger.debug(f"Tool call detail already exists for ID: {tool_id}")

            elif "content" in message and message.get("content"):
                content = message["content"]
                token_count = self.count_tokens(content)
                self.assistant_text_responses.append({
                    "content": content,
                    "token_count": token_count,
                    "timestamp": current_time
                })
                self.logger.debug(f"Added assistant text response: {content[:50]}... (Tokens: {token_count})")

        elif role == "tool":
            tool_name = message.get("name", "unknown")
            content = message.get("content", "")
            tool_call_id = message.get("tool_call_id", None)
            token_count = self.count_tokens(content)

            if tool_call_id:
                updated = False
                for tool_detail in self.tool_call_details:
                    if tool_detail["id"] == tool_call_id:
                        tool_detail["result"] = content
                        tool_detail["result_token_count"] = token_count
                        tool_detail["result_timestamp"] = current_time
                        self.logger.debug(f"Updated tool call {tool_call_id} with result (Tokens: {token_count})")
                        updated = True
                        break
                if not updated:
                     self.logger.warning(f"Received tool result for unknown tool_call_id: {tool_call_id}")
            else:
                self.logger.warning(f"Received tool result without tool_call_id: {tool_name}")
    
    async def _handle_llm_start(self, agent: Any, **kwargs: Any) -> None:
        """Handle the llm_start event."""
        self.logger.debug("Handling llm_start event")
        # Optionally clear previous thinking content if desired per LLM call
        # self.thinking_content = ""
    
    async def _handle_llm_end(self, agent: Any, **kwargs: Any) -> None:
        """Handle the llm_end event. Store thinking content and token usage."""
        self.logger.debug("Handling llm_end event")
        response = kwargs.get("response", {})

        # Extract thinking content (often the raw message content before tool parsing)
        try:
            message = response.choices[0].message
            # Only update thinking if there's actual content and no tool calls in this specific message
            # Tool calls are handled separately via message_add
            if hasattr(message, "content") and message.content and not getattr(message, "tool_calls", None):
                 # Check if this content is already in assistant_text_responses to avoid duplication
                if not any(resp['content'] == message.content for resp in self.assistant_text_responses):
                    self.thinking_content = message.content # Store as potential thinking
                    self.logger.debug(f"Stored potential thinking content: {self.thinking_content[:50]}...")
                else:
                    self.logger.debug("Content from llm_end already captured as assistant response.")

        except (AttributeError, IndexError, TypeError) as e:
            self.logger.debug(f"Could not extract thinking content from llm_end: {e}")

        # Track token usage
        try:
            usage = response.usage
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", 0)
                completion_tokens = getattr(usage, "completion_tokens", 0)
                self.token_usage["prompt_tokens"] += prompt_tokens
                self.token_usage["completion_tokens"] += completion_tokens
                # Recalculate total based on potentially cumulative prompt/completion
                self.token_usage["total_tokens"] = self.token_usage["prompt_tokens"] + self.token_usage["completion_tokens"]
                self.logger.debug(f"Updated token usage: Prompt +{prompt_tokens}, Completion +{completion_tokens}. Total: {self.token_usage}")
        except (AttributeError, TypeError) as e:
            self.logger.debug(f"Could not extract token usage from llm_end: {e}")
    
    async def _handle_agent_end(self, agent: Any, **kwargs: Any) -> None:
        """Handle the agent_end event. Mark agent as not running."""
        self.logger.debug("Handling agent_end event")
        self.is_running = False
        # Final result is handled by interact_with_agent after agent.run completes
        self.logger.debug(f"Agent finished. Final result: {kwargs.get('result', 'N/A')[:50]}...")
    
    def upload_file(self, file, file_uploads_log):
        """
        Handle file uploads in the Gradio interface.
        
        Args:
            file: The uploaded file
            file_uploads_log: List of previously uploaded files
            
        Returns:
            Tuple of (status_message, updated_file_uploads_log)
        """
        if file is None:
            return gr.Textbox(value="No file uploaded", visible=True), file_uploads_log
        
        file_ext = os.path.splitext(file.name)[1].lower()
        if file_ext not in self.allowed_file_types:
            return gr.Textbox("File type not allowed", visible=True), file_uploads_log
        
        original_name = os.path.basename(file.name)
        sanitized_name = re.sub(r"[^\w\-.]", "_", original_name)
        
        file_path = os.path.join(self.file_upload_folder, sanitized_name)
        shutil.copy(file.name, file_path)
        
        return gr.Textbox(f"File uploaded: {file_path}", visible=True), file_uploads_log + [file_path]
    
    def log_user_message(self, message, file_uploads_log):
        """
        Process user message, add files, and update chatbot history.
        This now ONLY prepares the input and adds the user message to the chat.
        It disables the send button while processing.

        Args:
            message: User message text
            file_uploads_log: List of uploaded files

        Returns:
            Tuple of (processed_message, initial_chatbot_state, disable_send_button)
        """
        processed_message = message
        # Check if there are file references to add to the message
        if file_uploads_log and len(file_uploads_log) > 0:
            file_list = "\n".join([f"- {os.path.basename(f)}" for f in file_uploads_log])
            processed_message = f"{message}\n\nFiles available:\n{file_list}"

        # Prepare the initial chatbot state for this turn
        # Assumes chatbot history is passed correctly or managed via gr.State
        # For simplicity, let's assume we get the history and append to it.
        # We need the actual chatbot component value here.
        # This part is tricky without direct access in this function signature.
        # Let's modify interact_with_agent to handle this.

        # Just return the processed message and disable the button
        # The chatbot update will happen in interact_with_agent
        return processed_message, gr.Button(interactive=False)
    
    def _build_current_assistant_message(self) -> str:
        """
        Construct the content for the assistant's message bubble based on current state.
        Prioritizes: Latest Text Response > Tool Calls > Thinking Content.
        """
        parts = []
        display_content = "Thinking..." # Default if nothing else is available yet

        # Sort details for consistent display order
        sorted_tool_details = sorted(self.tool_call_details, key=lambda x: x.get("timestamp", 0))
        sorted_text_responses = sorted(self.assistant_text_responses, key=lambda x: x.get("timestamp", 0))

        # 1. Get the latest assistant text response (if any)
        if sorted_text_responses:
            display_content = sorted_text_responses[-1]["content"]
            parts.append(display_content)
        # If there's no text response yet, but we have tool calls or thinking, use a placeholder
        elif sorted_tool_details or (self.show_thinking and self.thinking_content):
             parts.append("Working on it...") # More informative than just "Thinking..."

        # 2. Add Tool Call details (if enabled and available)
        if self.show_tool_calls and sorted_tool_details:
            parts.append("\n\n---\n**Tool Calls:**")
            for i, tool_detail in enumerate(sorted_tool_details):
                tool_name = tool_detail["name"]
                arguments = tool_detail["arguments"]
                result = tool_detail["result"]
                result_status = "⏳ Processing..." if result is None else "✅ Done"
                if result is not None and len(str(result)) > 100: # Truncate long results
                    result_display = f"```\n{str(result)[:100]}...\n```"
                elif result is not None:
                     result_display = f"```\n{result}\n```"
                else:
                    result_display = "" # No output shown until done

                parts.append(f"\n\n**Tool {i+1}: {tool_name}** ({result_status})")
                # Use details/summary for arguments to avoid clutter
                parts.append(f"\n<details><summary>Input Arguments</summary>\n\n```json\n{arguments}\n```\n</details>")
                if result_display:
                    parts.append(f"\n*Output:*\n{result_display}")

        # 3. Add Thinking Process (if enabled and available, and no text response yet)
        # Only show thinking if there isn't a more concrete text response or tool call happening
        if self.show_thinking and self.thinking_content and not sorted_text_responses and not sorted_tool_details:
            parts.append("\n\n---\n**Thinking Process:**\n```\n" + self.thinking_content + "\n```")

        # If parts is empty after all checks, use the initial display_content
        if not parts:
             return display_content
        else:
            return "".join(parts)

    def _get_token_usage_text(self) -> str:
        """Format the token usage string."""
        if not any(self.token_usage.values()):
            return "Tokens: 0"
        return (f"Tokens: P {self.token_usage['prompt_tokens']} | " +
                f"C {self.token_usage['completion_tokens']} | " +
                f"T {self.token_usage['total_tokens']}")

    async def interact_with_agent(self, user_input_processed, chatbot_history):
        """
        Process user input, interact with the agent, and stream updates to Gradio UI.

        Args:
            user_input_processed: User's message (potentially with file info)
            chatbot_history: The current list of messages from gr.Chatbot

        Yields:
            Tuple[List[Dict], str]: Updated chatbot history and token usage text
        """
        self.logger.info(f"Starting interaction for: {user_input_processed[:50]}...")

        # 1. Add user message to chatbot history
        chatbot_history.append({"role": "user", "content": user_input_processed})
        # 2. Add placeholder for assistant response
        chatbot_history.append({"role": "assistant", "content": "..."})

        # Initial yield to show user message and placeholder
        yield chatbot_history, self._get_token_usage_text()

        # 3. Run agent in background task
        # Agent run will trigger callbacks (_handle_... methods) which update self state
        agent_task = asyncio.create_task(self.current_agent.run(user_input_processed))

        # 4. Loop while agent is running, updating UI periodically
        update_interval = 0.3 # seconds
        min_yield_interval = 0.2 # Minimum time between yields to avoid flooding Gradio

        while not agent_task.done():
            current_time = time.time()
            # Throttle UI updates
            if current_time - self.last_update_yield_time >= min_yield_interval:
                # Build assistant message content from current callback state
                assistant_content = self._build_current_assistant_message()
                chatbot_history[-1]["content"] = assistant_content # Update placeholder

                # Get token usage text
                token_text = self._get_token_usage_text()

                yield chatbot_history, token_text
                self.last_update_yield_time = current_time

            await asyncio.sleep(update_interval) # Check periodically

        # 5. Agent finished, get final result and update UI one last time
        try:
            final_result_text = await agent_task
            self.logger.info("Agent task completed successfully.")
        except Exception as e:
            self.logger.error(f"Error during agent execution: {e}", exc_info=True)
            final_result_text = f"An error occurred: {e}"
            self.is_running = False # Ensure flag is reset on error

        # Format the final response including tool calls, thinking, tokens if enabled
        final_formatted_response = self._format_response(final_result_text)
        chatbot_history[-1]["content"] = final_formatted_response

        # Final token usage update
        token_text = self._get_token_usage_text()

        self.logger.debug("Yielding final state.")
        yield chatbot_history, token_text

        # Note: Button re-enabling happens in the .then() chain in create_app

    def _format_response(self, response_text):
        """
        Format the final response with thinking process, tool calls, and token usage.

        Args:
            response_text: The final response text from the agent

        Returns:
            Formatted response string with additional information in Markdown.
        """
        formatted_parts = []

        # Add the main response text
        formatted_parts.append(response_text)

        # Sort details for consistent display order
        sorted_tool_details = sorted(self.tool_call_details, key=lambda x: x.get("timestamp", 0))

        # Add thinking process if enabled and content exists
        if self.show_thinking and self.thinking_content:
            # Avoid showing thinking if it's identical to the final response text
            if self.thinking_content.strip() != response_text.strip():
                 formatted_parts.append("\n\n---\n**Thinking Process:**\n```\n" + self.thinking_content + "\n```")

        # Add tool calls if enabled and details exist
        if self.show_tool_calls and sorted_tool_details:
            formatted_parts.append("\n\n---\n**Tool Calls:**")
            for i, tool_detail in enumerate(sorted_tool_details):
                tool_name = tool_detail["name"]
                arguments = tool_detail["arguments"]
                result = tool_detail["result"] or "No result captured."
                input_tokens = tool_detail.get("token_count", 0)
                output_tokens = tool_detail.get("result_token_count", 0)

                formatted_parts.append(f"\n\n**Tool {i+1}: {tool_name}** (Input Tokens: {input_tokens}, Output Tokens: {output_tokens})")
                # Use details/summary for arguments to avoid clutter
                formatted_parts.append(f"\n<details><summary>Input Arguments</summary>\n\n```json\n{arguments}\n```\n</details>")
                formatted_parts.append(f"\n*Output:*\n```\n{result}\n```")


        # Add token usage summary (already displayed live, but good for final message)
        # This is slightly redundant with the dedicated token display, maybe remove?
        # Keeping it for now as it's part of the final message structure.
        if any(self.token_usage.values()):
            formatted_parts.append("\n\n---\n**Token Usage:**")
            formatted_parts.append(f"\nPrompt: {self.token_usage['prompt_tokens']} | " +
                                  f"Completion: {self.token_usage['completion_tokens']} | " +
                                  f"Total: {self.token_usage['total_tokens']}")

        return "".join(formatted_parts)

    def create_app(self, agent: TinyAgent, title: str = "TinyAgent Chat", description: str = None):
        """
        Create a Gradio app for the agent.

        Args:
            agent: The TinyAgent instance
            title: Title for the app
            description: Optional description

        Returns:
            A Gradio Blocks application
        """
        self.logger.debug("Creating Gradio app")
        self.current_agent = agent # Store agent reference

        with gr.Blocks(title=title, theme=gr.themes.Soft()) as app:
            # Use gr.State for file uploads log as it's simple data
            file_uploads_log = gr.State([])

            with gr.Row():
                with gr.Column(scale=1):
                    # Sidebar with title and description
                    gr.Markdown(f"# {title}")
                    if description:
                        gr.Markdown(description)
                    
                    # File upload section (if enabled)
                    if self.file_upload_folder:
                        with gr.Group():
                            gr.Markdown("## Upload Files")
                            file_upload = gr.File(label="Upload a file")
                            upload_status = gr.Textbox(label="Upload Status", visible=False, interactive=False)
                            
                            file_upload.change(
                                fn=self.upload_file,
                                inputs=[file_upload, file_uploads_log],
                                outputs=[upload_status, file_uploads_log]
                            )
                    
                    # Thinking and tool call toggles
                    with gr.Group():
                        gr.Markdown("## Display Options")
                        show_thinking_checkbox = gr.Checkbox(
                            label="Show thinking process", 
                            value=self.show_thinking
                        )
                        show_tool_calls_checkbox = gr.Checkbox(
                            label="Show tool calls", 
                            value=self.show_tool_calls
                        )
                        
                        # Update callback settings when checkboxes change
                        show_thinking_checkbox.change(
                            fn=lambda x: setattr(self, "show_thinking", x),
                            inputs=show_thinking_checkbox,
                            outputs=None # No direct output change needed
                        )
                        show_tool_calls_checkbox.change(
                            fn=lambda x: setattr(self, "show_tool_calls", x),
                            inputs=show_tool_calls_checkbox,
                            outputs=None # No direct output change needed
                        )
                    
                    # Token usage display
                    with gr.Group():
                        gr.Markdown("## Token Usage")
                        # Assign component to self for updates
                        self._token_usage_component = gr.Textbox(
                            label="Token Usage",
                            interactive=False,
                            value=self._get_token_usage_text() # Initial value
                        )
                    
                    # Add a footer with attribution
                    gr.Markdown(
                        "<div style='text-align: center; margin-top: 20px;'>"
                        "Powered by <a href='https://github.com/askdev-ai/tinyagent' target='_blank'>TinyAgent</a>"
                        "</div>"
                    )
                
                with gr.Column(scale=3):
                    # Chat interface - Assign component to self for updates
                    self._chatbot_component = gr.Chatbot(
                        [], # Start empty
                        label="Chat History",
                        height=600,
                         type="messages", # 'messages' type is deprecated/internal, use default
                        bubble_full_width=False,
                        show_copy_button=True,
                        render_markdown=True # Enable markdown rendering
                    )
                    
                    with gr.Row():
                        user_input = gr.Textbox(
                            placeholder="Type your message here...",
                            show_label=False,
                            container=False,
                            scale=9
                        )
                        submit_btn = gr.Button("Send", scale=1, variant="primary")
                    
                    # Clear button
                    clear_btn = gr.Button("Clear Conversation")
                    
                    # Store processed input temporarily between steps
                    processed_input_state = gr.State("")

                    # Event handlers - Chained logic
                    # 1. Process input, disable button
                    submit_action = submit_btn.click(
                        fn=self.log_user_message,
                        inputs=[user_input, file_uploads_log],
                        outputs=[processed_input_state, submit_btn], # Store processed input, disable btn
                        queue=False # Run quickly
                    ).then(
                        # 2. Clear the raw input box
                        fn=lambda: gr.Textbox(value=""),
                        inputs=None,
                        outputs=[user_input],
                        queue=False # Run quickly
                    ).then(
                        # 3. Run the main interaction loop (this yields updates)
                        fn=self.interact_with_agent,
                        inputs=[processed_input_state, self._chatbot_component],
                        outputs=[self._chatbot_component, self._token_usage_component] # Update chat and tokens
                        # queue=True # Run in background, default
                    ).then(
                        # 4. Re-enable the button after interaction finishes
                        fn=lambda: gr.Button(interactive=True),
                        inputs=None,
                        outputs=[submit_btn],
                        queue=False # Run quickly
                    )

                    # Also trigger on Enter key using the same chain
                    input_action = user_input.submit(
                         fn=self.log_user_message,
                        inputs=[user_input, file_uploads_log],
                        outputs=[processed_input_state, submit_btn], # Store processed input, disable btn
                        queue=False # Run quickly
                    ).then(
                        # 2. Clear the raw input box
                        fn=lambda: gr.Textbox(value=""),
                        inputs=None,
                        outputs=[user_input],
                        queue=False # Run quickly
                    ).then(
                        # 3. Run the main interaction loop (this yields updates)
                        fn=self.interact_with_agent,
                        inputs=[processed_input_state, self._chatbot_component],
                        outputs=[self._chatbot_component, self._token_usage_component] # Update chat and tokens
                        # queue=True # Run in background, default
                    ).then(
                        # 4. Re-enable the button after interaction finishes
                        fn=lambda: gr.Button(interactive=True),
                        inputs=None,
                        outputs=[submit_btn],
                        queue=False # Run quickly
                    )
                    
                    # Clear conversation
                    clear_btn.click(
                        fn=self.clear_conversation,
                        inputs=None, # No inputs needed
                        # Outputs: Clear chatbot and reset token text
                        outputs=[self._chatbot_component, self._token_usage_component],
                        queue=False # Run quickly
                    )

        self.logger.debug("Gradio app created")
        return app

    def clear_conversation(self):
        """Clear the conversation history, reset state, and update UI."""
        self.logger.debug("Clearing conversation")
        # Reset internal state
        self.thinking_content = ""
        self.tool_calls = []
        self.tool_call_details = []
        self.assistant_text_responses = []
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.is_running = False
        # Return empty state for UI components
        return [], self._get_token_usage_text()

    def launch(self, agent, title="TinyAgent Chat", description=None, share=False, **kwargs):
        """
        Launch the Gradio app.

        Args:
            agent: The TinyAgent instance
            title: Title for the app
            description: Optional description
            share: Whether to create a public link
            **kwargs: Additional arguments to pass to gradio.launch()

        Returns:
            The Gradio app instance and launch URLs.
        """
        self.logger.debug("Launching Gradio app")
        # Ensure the agent has this callback added
        if self not in agent.callbacks:
             agent.add_callback(self)
             self.logger.info("GradioCallback automatically added to the agent.")

        app = self.create_app(agent, title, description)
        # Add debug=True for more Gradio internal logging if needed
        # launch_kwargs = {"share": share, "debug": True}
        launch_kwargs = {"share": share}
        launch_kwargs.update(kwargs) # Allow overriding share/debug etc.
        app.launch(**launch_kwargs)
        return app # Return the app instance

async def run_example():
    """Example usage of GradioCallback with TinyAgent."""
    import os
    import sys
    import tempfile
    import shutil
    from tinyagent import TinyAgent # Assuming TinyAgent is importable
    from tinyagent.hooks.logging_manager import LoggingManager # Assuming LoggingManager exists

    # --- Logging Setup (Simplified) ---
    log_manager = LoggingManager(default_level=logging.INFO)
    log_manager.set_levels({
        'tinyagent.hooks.gradio_callback': logging.DEBUG, # Debug GradioCallback
        'tinyagent.tiny_agent': logging.DEBUG,
        'tinyagent.mcp_client': logging.DEBUG,
    })
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG # Handler level
    )
    ui_logger = log_manager.get_logger('tinyagent.hooks.gradio_callback')
    agent_logger = log_manager.get_logger('tinyagent.tiny_agent')
    ui_logger.info("--- Starting GradioCallback Example ---")
    # --- End Logging Setup ---

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        ui_logger.error("OPENAI_API_KEY environment variable not set.")
        return

    # Create a temporary folder for file uploads
    upload_folder = tempfile.mkdtemp(prefix="gradio_uploads_")
    ui_logger.info(f"Created temporary upload folder: {upload_folder}")

    # Initialize the agent
    agent = TinyAgent(model="gpt-4.1-mini", api_key=api_key, logger=agent_logger)

    # Connect to servers (as per contribution guide)
    try:
        ui_logger.info("Connecting to MCP servers...")
        await agent.connect_to_server("npx",["-y","@openbnb/mcp-server-airbnb","--ignore-robots-txt"])
        await agent.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
        ui_logger.info("Connected to MCP servers.")
    except Exception as e:
        ui_logger.error(f"Failed to connect to MCP servers: {e}", exc_info=True)
        # Decide if you want to continue without servers or exit
        # return

    # Create the Gradio callback
    gradio_ui = GradioCallback(
        file_upload_folder=upload_folder,
        show_thinking=True,
        show_tool_calls=True,
        logger=ui_logger # Pass the specific logger
    )

    # Launch the Gradio interface
    # The launch method now adds the callback to the agent automatically if needed.
    ui_logger.info("Launching Gradio interface...")
    try:
        gradio_ui.launch(
            agent,
            title="TinyAgent Chat Interface",
            description="Chat with TinyAgent. Try asking: 'Plan a trip to Toronto for 7 days in the next month.'",
            share=False # Set to True for public link if needed
        )
        # The script will block here until the Gradio server is closed (Ctrl+C)
    except Exception as e:
         ui_logger.error(f"Failed to launch Gradio app: {e}", exc_info=True)
    finally:
        # Clean up
        ui_logger.info("Cleaning up resources...")
        if os.path.exists(upload_folder):
            ui_logger.info(f"Removing temporary upload folder: {upload_folder}")
            shutil.rmtree(upload_folder)
        await agent.close()
        ui_logger.info("--- GradioCallback Example Finished ---")


if __name__ == "__main__":
    # Ensure asyncio event loop is handled correctly
    try:
        asyncio.run(run_example())
    except KeyboardInterrupt:
        print("\nExiting...")