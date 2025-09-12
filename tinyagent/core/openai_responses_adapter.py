from typing import Any, Dict, List, Optional


class ChatMessage:
    """Minimal chat message shim matching LiteLLM-like access pattern."""

    def __init__(self, content: str = "", tool_calls: Optional[List[Any]] = None):
        self.content = content
        self.tool_calls = tool_calls or []


class ChatChoice:
    """Minimal choice shim with a `message` attribute."""

    def __init__(self, message: ChatMessage):
        self.message = message


class ChatResponse:
    """Minimal response shim to look like `litellm` responses for the agent."""

    def __init__(self, choices: List[ChatChoice], usage: Optional[Dict[str, Any]] = None):
        self.choices = choices
        self.usage = usage or {}


class ToolFunction:
    """Represents a function call object in a tool call, like Chat Completions."""

    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "arguments": self.arguments}

    # Provide dict-like access for downstream hooks expecting Chat-style dicts
    def get(self, key: str, default: Any = None) -> Any:
        if key == "name":
            return self.name
        if key == "arguments":
            return self.arguments
        return default

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val


class ToolCall:
    """Represents a single tool call with id + function field."""

    def __init__(self, call_id: str, function: ToolFunction):
        self.id = call_id
        self.function = function

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "function": self.function.to_dict()}

    # Provide dict-like access for downstream hooks expecting Chat-style dicts
    def get(self, key: str, default: Any = None) -> Any:
        if key == "id":
            return self.id
        if key == "function":
            return self.function
        return default

    def __getitem__(self, key: str) -> Any:
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val


class OpenAIResponsesAdapter:
    """
    Adapter that translates between TinyAgent's Chat-style messages/tools and
    OpenAI Responses API payloads and back, without changing external storage
    or hooks contracts. Intended to be mocked in tests.
    """

    @staticmethod
    def to_responses_request(
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        model: str,
        temperature: Optional[float] = None,
        previous_response_id: Optional[str] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None,
        **model_kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Build a reasonable Responses API request payload from chat `messages` & `tools`.

        Strategy:
        - Map the first system message to `instructions` when present.
        - Map remaining messages to `input` as a list of role+content objects (compatible input mode).
        - Pass-through `tools` as provided; Responses expects different tool config shapes for
          built-ins vs function tools, but we keep the contract here — the provider can translate
          if needed. For our adapter the important part is we keep the same schema externally.
        """
        req: Dict[str, Any] = {"model": model}

        if temperature is not None:
            req["temperature"] = temperature

        # Split off a system message if present
        instructions = None
        msg_items: List[Dict[str, Any]] = []
        user_messages: List[str] = []
        for i, m in enumerate(messages):
            role = m.get("role")
            content = m.get("content", "")
            # Skip tool messages; Responses `input` does not accept role="tool"
            if role == "tool":
                continue
            if i == 0 and role == "system":
                instructions = content
            else:
                # Collect as message objects (fallback) and also track last user text
                msg_items.append({"role": role, "content": content})
                if role == "user" and isinstance(content, str) and content.strip():
                    user_messages.append(content)

        # Only include instructions on the initial turn. For chained calls
        # (when previous_response_id is provided), omit instructions to let
        # the server continue the existing thread of thought.
        if instructions and not previous_response_id:
            req["instructions"] = instructions

        if tools:
            # Translate Chat Completions style function-tools to Responses style
            translated_tools: List[Dict[str, Any]] = []
            for t in tools:
                if isinstance(t, dict) and t.get("type") == "function" and isinstance(t.get("function"), dict):
                    fdef = t["function"]
                    name = fdef.get("name")
                    if name:
                        translated_tools.append(
                            {
                                "type": "function",
                                "name": name,
                                "description": fdef.get("description", ""),
                                "parameters": fdef.get("parameters", {"type": "object", "properties": {}}),
                            }
                        )
                else:
                    # Pass through anything else as-is
                    translated_tools.append(t)
            if translated_tools:
                req["tools"] = translated_tools

        # Include tool results for the next step of the agentic loop
        results_items: List[Dict[str, Any]] = []
        if tool_results:
            for r in tool_results:
                # Expect keys: tool_call_id, content
                call_id = r.get("tool_call_id") or r.get("id")
                output = r.get("content", "")
                name = r.get("name")
                if call_id:
                    # Per OpenAI Responses, function_call_output requires a string 'output'
                    results_items.append({
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": str(output),
                    })

        # Now set input:
        # - If chaining and we have tool results, send only function_call_output items
        # - If chaining but no tool results, pass the last user string to continue the thread
        # - If initial turn, pass the last user string
        if previous_response_id:
            if results_items:
                req["input"] = results_items
            else:
                req["input"] = (user_messages[-1] if user_messages else "")
        else:
            # Prefer last user message content as a simple string to avoid noisy history
            if user_messages:
                req["input"] = user_messages[-1]
            else:
                # Fallback: join all non-system contents
                joined = " \n\n".join([
                    str(m.get("content", "")) for m in messages if m.get("role") not in ("system", "tool")
                ]).strip()
                req["input"] = joined or ""

        # Add chaining information if present
        if previous_response_id:
            req["previous_response_id"] = previous_response_id

        # Merge through any extra kwargs (max_tokens, response_format, etc.)
        req.update(model_kwargs)
        return req

    @staticmethod
    def from_responses_result(resp: Dict[str, Any], original_response: Any = None) -> ChatResponse:
        """
        Convert a Responses result into a Chat-like response object with:
        - .choices[0].message.content
        - .choices[0].message.tool_calls (list of ToolCall)
        - .usage (dict) for accounting

        The adapter makes best-effort assumptions based on current Responses API
        shapes, but is tolerant to missing fields in mocked tests.
        
        Args:
            resp: Dictionary representation of the response
            original_response: Original LiteLLM response object (contains cost metadata)
        """
        output = resp.get("output", []) or []

        content_text_parts: List[str] = []
        tool_calls: List[ToolCall] = []

        for item in output:
            itype = item.get("type")
            if itype == "message":
                # Aggregate output_text content chunks
                for c in item.get("content", []) or []:
                    if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                        text = c.get("text", "")
                        if text:
                            content_text_parts.append(text)
            elif itype in ("function_call", "tool_call"):
                # Map function/tool call to Chat-style tool_calls
                # Prefer an id with 'call_' prefix when available
                cand_ids: List[str] = []
                if isinstance(item, dict):
                    cand_ids.append(item.get("call_id"))
                    cand_ids.append(item.get("id"))
                    fn = item.get("function") if isinstance(item.get("function"), dict) else None
                    if isinstance(fn, dict):
                        cand_ids.append(fn.get("call_id"))
                        cand_ids.append(fn.get("id"))
                call_id = next((c for c in cand_ids if isinstance(c, str) and c.startswith("call_")), None)
                if not call_id:
                    call_id = next((c for c in cand_ids if isinstance(c, str) and c), "toolcall_0")

                name = item.get("name") or (
                    item.get("function", {}).get("name") if isinstance(item.get("function"), dict) else None
                ) or "unknown_tool"

                # Arguments may be dict or string — Chat schema expects a JSON string
                args_obj = item.get("arguments")
                if isinstance(args_obj, (dict, list)):
                    import json as _json

                    arguments = _json.dumps(args_obj)
                else:
                    arguments = str(args_obj) if args_obj is not None else "{}"

                tool_calls.append(ToolCall(call_id, ToolFunction(name, arguments)))

        content_joined = "".join(content_text_parts)
        choice = ChatChoice(ChatMessage(content=content_joined, tool_calls=tool_calls))

        # Map basic usage
        usage = resp.get("usage", {}) or {}

        # Extract cost information from the original LiteLLM response if available
        if original_response is not None:
            # Method 1: Check for _hidden_params (LiteLLM specific)
            if hasattr(original_response, '_hidden_params') and isinstance(original_response._hidden_params, dict):
                response_cost = original_response._hidden_params.get("response_cost")
                if response_cost is not None and response_cost > 0:
                    usage['cost'] = response_cost
            
            # Method 2: Try to get cost using litellm.completion_cost if not found above
            if usage.get('cost', 0) == 0:
                try:
                    import litellm
                    if hasattr(litellm, 'completion_cost'):
                        cost = litellm.completion_cost(completion_response=original_response)
                        if cost and cost > 0:
                            usage['cost'] = cost
                except Exception:
                    # Ignore errors in cost calculation
                    pass

        chat_response = ChatResponse([choice], usage=usage)
        
        # Preserve the _hidden_params attribute for token tracker compatibility
        if original_response is not None and hasattr(original_response, '_hidden_params'):
            try:
                chat_response._hidden_params = original_response._hidden_params
            except Exception:
                # If we can't set the attribute, continue without it
                pass

        return chat_response
