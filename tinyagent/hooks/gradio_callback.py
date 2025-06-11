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
import gradio as gr
from gradio import ChatMessage

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
                        tool_detail = {
                            "id": tool_id,
                            "name": tool_name,
                            "arguments": formatted_args,
                            "result": None,
                            "token_count": token_count,
                            "result_token_count": 0,
                            "timestamp": current_time,
                            "result_timestamp": None
                        }
                        
                        # Special handling for run_python tool - extract code_lines
                        if tool_name == "run_python":
                            try:
                                # Look for code in different possible field names
                                code_content = None
                                for field in ['code_lines', 'code', 'script', 'python_code']:
                                    if field in parsed_args:
                                        code_content = parsed_args[field]
                                        break
                                
                                if code_content is not None:
                                    tool_detail["code_lines"] = code_content
                                    self.logger.debug(f"Stored code content for run_python tool {tool_id}")
                            except Exception as e:
                                self.logger.error(f"Error processing run_python arguments: {e}")
                        
                        self.tool_call_details.append(tool_detail)
                        self.logger.debug(f"Added tool call detail: {tool_name} (ID: {tool_id}, Tokens: {token_count})")
                        
                        # If this is a final_answer or ask_question tool, we'll handle it specially later
                        # when the result comes in
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
                        
                        # Special handling for final_answer and ask_question tools
                        # Add their results directly as assistant messages in the chat
                        if tool_detail["name"] in ["final_answer", "ask_question"]:
                            self.assistant_text_responses.append({
                                "content": content,
                                "token_count": token_count,
                                "timestamp": current_time,
                                "from_tool": True,
                                "tool_name": tool_detail["name"]
                            })
                            self.logger.debug(f"Added {tool_detail['name']} result as assistant message")
                        
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
            self.logger.debug(f"Token usage: {usage}")
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
            for i, tool_detail in enumerate(sorted_tool_details):
                tool_name = tool_detail["name"]
                arguments = tool_detail["arguments"]
                result = tool_detail["result"]
                result_status = "⏳ Processing..." if result is None else "✅ Done"
                input_tokens = tool_detail.get("token_count", 0)
                output_tokens = tool_detail.get("result_token_count", 0)
                
                # Special handling for final_answer and ask_question tools
                #if tool_name in ["final_answer", "ask_question"] and result is not None:
                    # Don't add these as tool calls, they'll be shown as regular messages
                    #continue
                
                # Create collapsible tool call section using Gradio's markdown format
                parts.append(f"\n\n<details><summary>🛠️ **Tool: {tool_name}** ({result_status}) - {input_tokens+output_tokens} tokens</summary>")
                parts.append(f"\n\n**Input Arguments:**\n```json\n{arguments}\n```")
                
                if result is not None:
                    parts.append(f"\n\n**Output:** ({output_tokens} tokens)\n```\n{result}\n```")
                
                parts.append("\n</details>")

        # 3. Add Thinking Process (if enabled and available, and no text response yet)
        # Only show thinking if there isn't a more concrete text response or tool call happening
        if self.show_thinking and self.thinking_content and not sorted_text_responses and not sorted_tool_details:
            parts.append("\n\n<details><summary>🧠 **Thinking Process**</summary>\n\n```\n" + self.thinking_content + "\n```\n</details>")

        # If parts is empty after all checks, use the initial display_content
        if not parts:
             return display_content
        else:
            return "".join(parts)

    def _get_token_usage_text(self) -> str:
        """Format the token usage string."""
        if not any(self.token_usage.values()):
            return "Tokens: 0"
        return (f"Tokens: I {self.token_usage['prompt_tokens']} | " +
                f"O {self.token_usage['completion_tokens']} | " +
                f"Total {self.token_usage['total_tokens']}")

    def _format_run_python_tool(self, tool_detail: dict) -> str:
        """
        Format run_python tool call with proper markdown formatting for code and output.
        
        Args:
            tool_detail: Tool call detail dictionary
            
        Returns:
            Formatted markdown string
        """
        tool_name = tool_detail["name"]
        tool_id = tool_detail.get("id", "unknown")
        code_lines = tool_detail.get("code_lines", [])
        result = tool_detail.get("result")
        input_tokens = tool_detail.get("token_count", 0)
        output_tokens = tool_detail.get("result_token_count", 0)
        total_tokens = input_tokens + output_tokens
        
        # Start building the formatted content
        parts = []
        
        # Handle different code_lines formats
        combined_code = ""
        if code_lines:
            if isinstance(code_lines, list):
                # Standard case: list of code lines
                combined_code = "\n".join(code_lines)
            elif isinstance(code_lines, str):
                # Handle case where code_lines is a single string
                combined_code = code_lines
            else:
                # Convert other types to string
                combined_code = str(code_lines)
        
        # If we have code content, show it as Python code block
        if combined_code.strip():
            parts.append(f"**Python Code:**\n```python\n{combined_code}\n```")
        else:
            # Try to extract code from arguments as fallback
            try:
                args_dict = json.loads(tool_detail['arguments'])
                # Check for different possible code field names
                code_content = None
                for field in ['code_lines', 'code', 'script', 'python_code']:
                    if field in args_dict:
                        code_content = args_dict[field]
                        break
                
                if code_content:
                    if isinstance(code_content, list):
                        combined_code = "\n".join(code_content)
                    else:
                        combined_code = str(code_content)
                    
                    if combined_code.strip():
                        parts.append(f"**Python Code:**\n```python\n{combined_code}\n```")
                    else:
                        # Final fallback to showing raw arguments
                        parts.append(f"**Input Arguments:**\n```json\n{tool_detail['arguments']}\n```")
                else:
                    # No code found, show raw arguments
                    parts.append(f"**Input Arguments:**\n```json\n{tool_detail['arguments']}\n```")
            except (json.JSONDecodeError, KeyError):
                # If we can't parse arguments, show them as-is
                parts.append(f"**Input Arguments:**\n```json\n{tool_detail['arguments']}\n```")
        
        # Add the output if available
        if result is not None:
            parts.append(f"\n**Output:** ({output_tokens} tokens)")
            
            try:
                # Try to parse result as JSON for better formatting
                result_json = json.loads(result)
                parts.append(f"```json\n{json.dumps(result_json, indent=2)}\n```")
            except (json.JSONDecodeError, TypeError):
                # Handle plain text result
                if isinstance(result, str):
                    # Replace escaped newlines with actual newlines for better readability
                    formatted_result = result.replace("\\n", "\n")
                    parts.append(f"```\n{formatted_result}\n```")
                else:
                    parts.append(f"```\n{str(result)}\n```")
        else:
            parts.append(f"\n**Status:** ⏳ Processing...")
        
        # Add token information
        parts.append(f"\n**Token Usage:** {total_tokens} total ({input_tokens} input + {output_tokens} output)")
        
        return "\n".join(parts)

    async def interact_with_agent(self, user_input_processed, chatbot_history):
        """
        Process user input, interact with the agent, and stream updates to Gradio UI.
        Each tool call and response will be shown as a separate message.
        """
        self.logger.info(f"Starting interaction for: {user_input_processed[:50]}...")
        
        # Reset state for new interaction to prevent showing previous content
        self.thinking_content = ""
        self.tool_calls = []
        self.tool_call_details = []
        self.assistant_text_responses = []
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.is_running = True
        self.last_update_yield_time = 0
        self.logger.debug("Reset interaction state for new conversation turn")
 
        # 1. Add user message to chatbot history as a ChatMessage
        chatbot_history.append(
            ChatMessage(role="user", content=user_input_processed)
        )
 
        # 2. Add typing indicator immediately after user message
        typing_message = ChatMessage(
            role="assistant", 
            content="🤔 Thinking..."
        )
        chatbot_history.append(typing_message)
        typing_message_index = len(chatbot_history) - 1
 
        # Initial yield to show user message and typing indicator
        yield chatbot_history, self._get_token_usage_text()
 
        # Kick off the agent in the background
        loop = asyncio.get_event_loop()
        agent_task = asyncio.create_task(self.current_agent.run(user_input_processed))
 
        displayed_tool_calls = set()
        displayed_text_responses = set()
        thinking_removed = False
        update_interval = 0.3
        min_yield_interval = 0.2
        
        # Track tool calls that are in progress (showing "working...")
        in_progress_tool_calls = {}
 
        while not agent_task.done():
            now = time.time()
            if now - self.last_update_yield_time >= min_yield_interval:
                sorted_tool_details = sorted(self.tool_call_details, key=lambda x: x.get("timestamp", 0))
                sorted_text_responses = sorted(self.assistant_text_responses, key=lambda x: x.get("timestamp", 0))
 
                # Remove typing indicator once we have actual content to show
                if not thinking_removed and (sorted_text_responses or sorted_tool_details):
                    # Remove the typing indicator
                    if typing_message_index < len(chatbot_history):
                        chatbot_history.pop(typing_message_index)
                        thinking_removed = True
                        self.logger.debug("Removed typing indicator")
 
                # → New assistant text chunks
                for resp in sorted_text_responses:
                    content = resp["content"]
                    if content not in displayed_text_responses:
                        chatbot_history.append(
                            ChatMessage(role="assistant", content=content)
                        )
                        displayed_text_responses.add(content)
                        self.logger.debug(f"Added new text response: {content[:50]}...")
 
                # → Show tool calls with "working..." status when they start
                if self.show_tool_calls:
                    for tool in sorted_tool_details:
                        tid = tool["id"]
                        tname = tool["name"]
                        
                        # If we haven't displayed this tool call yet
                        if tid not in displayed_tool_calls and tid not in in_progress_tool_calls:
                            in_tok = tool.get("token_count", 0)
                            
                            # Create "working..." message for this tool call
                            if tname == "run_python":
                                # Special formatting for run_python
                                body = self._format_run_python_tool(tool)
                            else:
                                # Standard formatting for other tools
                                body = (
                                    f"**Input Arguments:**\n```json\n{tool['arguments']}\n```\n\n"
                                    f"**Output:** ⏳ Working...\n"
                                )
                            
                            # Add to chatbot with "working" status
                            msg = ChatMessage(
                                role="assistant",
                                content=body,
                                metadata={
                                    "title": f"🛠️ {tname} — {in_tok} tokens",
                                    "status": "pending"
                                }
                            )
                            chatbot_history.append(msg)
                            # Track this tool call as in progress
                            in_progress_tool_calls[tid] = len(chatbot_history) - 1
                            self.logger.debug(f"Added in-progress tool call: {tname}")
                        
                        # If this tool call has completed and we're tracking it as in-progress
                        elif tid in in_progress_tool_calls and tool.get("result") is not None:
                            # Get the position in the chatbot history
                            pos = in_progress_tool_calls[tid]
                            in_tok = tool.get("token_count", 0)
                            out_tok = tool.get("result_token_count", 0)
                            tot_tok = in_tok + out_tok
                            
                            # Update the message with completed status and result
                            if tname == "run_python":
                                # Special formatting for completed run_python
                                body = self._format_run_python_tool(tool)
                            else:
                                # Standard formatting for other completed tools
                                body = (
                                    f"**Input Arguments:**\n```json\n{tool['arguments']}\n```\n\n"
                                    f"**Output:** ({out_tok} tokens)\n```json\n{tool['result']}\n```\n"
                                )
                            
                            # Update the existing message
                            chatbot_history[pos] = ChatMessage(
                                role="assistant",
                                content=body,
                                metadata={
                                    "title": f"🛠️ {tname} — {tot_tok} tokens ✅",
                                    "status": "done"
                                }
                            )
                            # Mark as displayed and remove from in-progress
                            displayed_tool_calls.add(tid)
                            del in_progress_tool_calls[tid]
                            self.logger.debug(f"Updated tool call to completed: {tname}")
 
                # yield updated history + token usage
                token_text = self._get_token_usage_text()
                yield chatbot_history, token_text
                self.last_update_yield_time = now
 
            await asyncio.sleep(update_interval)
 
        # Remove typing indicator if still present when agent finishes
        if not thinking_removed and typing_message_index < len(chatbot_history):
            chatbot_history.pop(typing_message_index)
            self.logger.debug("Removed typing indicator at end")
 
        # once the agent_task is done, add its final result if any
        try:
            final_text = await agent_task
        except Exception as e:
            final_text = f"Error: {e}"
            self.is_running = False
 
        if final_text not in displayed_text_responses:
            chatbot_history.append(
                ChatMessage(role="assistant", content=final_text)
            )
            self.logger.debug(f"Added final result: {final_text[:50]}...")
 
        # final token usage
        yield chatbot_history, self._get_token_usage_text()

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

        # Add tool calls if enabled and details exist
        if self.show_tool_calls and sorted_tool_details:
            formatted_parts.append("\n\n---\n")
            
            for i, tool_detail in enumerate(sorted_tool_details):
                tool_name = tool_detail["name"]
                arguments = tool_detail["arguments"]
                result = tool_detail["result"] or "No result captured."
                input_tokens = tool_detail.get("token_count", 0)
                output_tokens = tool_detail.get("result_token_count", 0)
                
                # Skip final_answer and ask_question tools in the tool call section
                # as they're already shown as regular messages
                #if tool_name in ["final_answer", "ask_question"]:
                #    continue
                
                formatted_parts.append(f"\n<details><summary>🛠️ **Tool {i+1}: {tool_name}** - {input_tokens+output_tokens} tokens</summary>\n")
                formatted_parts.append(f"\n**Input Arguments:**\n```json\n{arguments}\n```")
                formatted_parts.append(f"\n**Output:** ({output_tokens} tokens)\n```\n{result}\n```\n</details>")

        # Add thinking process if enabled and content exists
        if self.show_thinking and self.thinking_content:
            # Avoid showing thinking if it's identical to the final response text
            if self.thinking_content.strip() != response_text.strip():
                 formatted_parts.append("\n\n<details><summary>🧠 **Thinking Process**</summary>\n\n```\n" + self.thinking_content + "\n```\n</details>")

        # Add token usage summary
        if any(self.token_usage.values()):
            formatted_parts.append("\n\n---\n")
            formatted_parts.append(f"**Token Usage:** Prompt: {self.token_usage['prompt_tokens']} | " +
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

        with gr.Blocks(
            title=title,
            theme=gr.themes.Default(font=[gr.themes.GoogleFont("Inter"), "Arial", "sans-serif"])
        ) as app:
            file_uploads_log = gr.State([])

            with gr.Row():
                # -- Left Sidebar --
                with gr.Column(scale=1):
                    gr.Markdown(f"# {title}")
                    if description:
                        gr.Markdown(description)

                    # 1) Collapsible File Upload Section
                    if self.file_upload_folder:
                        with gr.Accordion("Upload Files", open=False):
                            gr.Markdown("Upload files to be used by the agent")
                            file_upload = gr.File(label="Choose a file")
                            upload_status = gr.Textbox(label="Upload Status", visible=False, interactive=False)
                            file_upload.change(
                                fn=self.upload_file,
                                inputs=[file_upload, file_uploads_log],
                                outputs=[upload_status, file_uploads_log]
                            )

                    # 2) Available Tools Section
                    tools = getattr(agent, "available_tools", [])
                    with gr.Accordion(f"Available Tools ({len(tools)})", open=True):
                        
                        if not tools:
                            gr.Markdown("_No tools registered_")
                        else:
                            for tool_meta in tools:
                                fn = tool_meta.get("function", {})
                                tool_name = fn.get("name", "unknown")
                                with gr.Accordion(tool_name, open=False):
                                    # Description
                                    desc = fn.get("description")
                                    if desc:
                                        gr.Markdown(f"**Description:** {desc}")

                                    # JSON schema for function calling
                                    schema = fn.get("parameters")
                                    if schema:
                                        gr.JSON(value=schema, label="Function Calling Schema")
                                    else:
                                        gr.Markdown("_No schema available_")

                    # 3) Thinking / Tool‐call Toggles
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
                        show_thinking_checkbox.change(
                            fn=lambda x: setattr(self, "show_thinking", x),
                            inputs=show_thinking_checkbox,
                            outputs=None
                        )
                        show_tool_calls_checkbox.change(
                            fn=lambda x: setattr(self, "show_tool_calls", x),
                            inputs=show_tool_calls_checkbox,
                            outputs=None
                        )

                    # 4) Token Usage Display
                    with gr.Group():
                        gr.Markdown("## Token Usage")
                        self._token_usage_component = gr.Textbox(
                            label="Token Usage",
                            interactive=False,
                            value=self._get_token_usage_text()
                        )

                    # Footer
                    gr.Markdown(
                        "<div style='text-align: center; margin-top: 20px;'>"
                        "Powered by <a href='https://github.com/askbudi/tinyagent' target='_blank'>TinyAgent</a>"
                        "</div>"
                    )

                # -- Right Chat Column (unchanged) --
                with gr.Column(scale=3):
                    # Chat interface - Assign component to self for updates
                    self._chatbot_component = gr.Chatbot(
                        [], # Start empty
                        label="Chat History",
                        height=600,
                        type="messages", # Use messages type for better formatting
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
                        outputs=[self._chatbot_component, self._token_usage_component], # Update chat and tokens
                        queue=True # Explicitly enable queue for this async generator
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
                        outputs=[self._chatbot_component, self._token_usage_component], # Update chat and tokens
                        queue=True # Explicitly enable queue for this async generator
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
        """Clear the conversation history (UI + agent), reset state completely, and update UI."""
        self.logger.debug("Clearing conversation completely (UI + agent with new session)")
        # Reset UI‐side state
        self.thinking_content = ""
        self.tool_calls = []
        self.tool_call_details = []
        self.assistant_text_responses = []
        self.token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.is_running = False

        # Completely reset the agent state with a new session
        try:
            if self.current_agent:
                # Generate a new session ID for a fresh start
                import uuid
                new_session_id = str(uuid.uuid4())
                self.current_agent.session_id = new_session_id
                self.logger.debug(f"Generated new session ID: {new_session_id}")
                
                # Reset all agent state
                # 1. Clear conversation history (preserve system message)
                if self.current_agent.messages:
                    system_msg = self.current_agent.messages[0]
                    self.current_agent.messages = [system_msg]
                else:
                    # Rebuild default system prompt if missing
                    default_system_prompt = (
                        "You are a helpful AI assistant with access to a variety of tools. "
                        "Use the tools when appropriate to accomplish tasks. "
                        "If a tool you need isn't available, just say so."
                    )
                    self.current_agent.messages = [{
                        "role": "system",
                        "content": default_system_prompt
                    }]
                
                # 2. Reset session state
                self.current_agent.session_state = {}
                
                # 3. Reset token usage in metadata
                if hasattr(self.current_agent, 'metadata') and 'usage' in self.current_agent.metadata:
                    self.current_agent.metadata['usage'] = {
                        "prompt_tokens": 0, 
                        "completion_tokens": 0, 
                        "total_tokens": 0
                    }
                
                # 4. Reset any other accumulated state that might affect behavior
                self.current_agent.is_running = False
                
                # 5. Reset session load flag to prevent any deferred loading of old session
                self.current_agent._needs_session_load = False
                
                self.logger.info(f"Completely reset TinyAgent with new session: {new_session_id}")
        except Exception as e:
            self.logger.error(f"Failed to reset TinyAgent completely: {e}")

        # Return cleared UI components: empty chat + fresh token usage
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
        
        # Use the same event loop for Gradio
        launch_kwargs = {
            "share": share,
            "prevent_thread_lock": True  # This is crucial - allows the main event loop to continue running
        }
        launch_kwargs.update(kwargs) # Allow overriding share/debug etc.
        
        # Get the current event loop
        loop = asyncio.get_event_loop()
        self.logger.debug(f"Using event loop for Gradio: {loop}")
        
        app.queue()
        return app.launch(**launch_kwargs) # Return the app instance


from tinyagent.tiny_agent import tool
@tool(name="get_weather",description="Get the weather for a given city.")
def get_weather(city: str)->str:
    """Get the weather for a given city.
    Args:
        city: The city to get the weather for

    Returns:
        The weather for the given city
    """

    return f"The weather in {city} is sunny."

async def run_example():
    """Example usage of GradioCallback with TinyAgent."""
    import os
    import sys
    import tempfile
    import shutil
    import asyncio
    from tinyagent import TinyAgent  # Assuming TinyAgent is importable
    from tinyagent.hooks.logging_manager import LoggingManager  # Assuming LoggingManager exists

    # --- Logging Setup (Simplified) ---
    log_manager = LoggingManager(default_level=logging.INFO)
    log_manager.set_levels({
        'tinyagent.hooks.gradio_callback': logging.DEBUG,
        'tinyagent.tiny_agent': logging.DEBUG,
        'tinyagent.mcp_client': logging.DEBUG,
    })
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
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

    # Ensure we're using a single event loop for everything
    loop = asyncio.get_event_loop()
    ui_logger.debug(f"Using event loop: {loop}")

    # Initialize the agent
    agent = TinyAgent(model="gpt-4.1-mini", api_key=api_key, logger=agent_logger)

    agent.add_tool(get_weather)

    # Create the Gradio callback
    gradio_ui = GradioCallback(
        file_upload_folder=upload_folder,
        show_thinking=True,
        show_tool_calls=True,
        logger=ui_logger # Pass the specific logger
    )
    agent.add_callback(gradio_ui)

    # Connect to MCP servers
    try:
        ui_logger.info("Connecting to MCP servers...")
        # Use standard MCP servers as per contribution guide
        await agent.connect_to_server("npx",["-y","@openbnb/mcp-server-airbnb","--ignore-robots-txt"])
        await agent.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
        ui_logger.info("Connected to MCP servers.")
    except Exception as e:
        ui_logger.error(f"Failed to connect to MCP servers: {e}", exc_info=True)
        # Continue without servers - we still have the local get_weather tool

    # Create the Gradio app but don't launch it yet
    #app = gradio_ui.create_app(
    #    agent,
    #    title="TinyAgent Chat Interface",
    #    description="Chat with TinyAgent. Try asking: 'Plan a trip to Toronto for 7 days in the next month.'",
    #)
    
    # Configure the queue without extra parameters
    #app.queue()
    
    # Launch the app in a way that doesn't block our event loop
    ui_logger.info("Launching Gradio interface...")
    try:
        # Launch without blocking
        #app.launch(
        #    share=False,
        #    prevent_thread_lock=True,  # Critical to not block our event loop
        #    show_error=True
        #)
        gradio_ui.launch(
            agent,
            title="TinyAgent Chat Interface",
            description="Chat with TinyAgent. Try asking: 'Plan a trip to Toronto for 7 days in the next month.'",
            share=False,
            prevent_thread_lock=True,  # Critical to not block our event loop
            show_error=True
        )
        ui_logger.info("Gradio interface launched (non-blocking).")
        
        # Keep the main event loop running to handle both Gradio and MCP operations
        # This is the key part - we need to keep our main event loop running
        # but also allow it to process both Gradio and MCP client operations
        while True:
            await asyncio.sleep(1)  # More efficient than an Event().wait()
            
    except KeyboardInterrupt:
        ui_logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        ui_logger.error(f"Failed to launch or run Gradio app: {e}", exc_info=True)
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