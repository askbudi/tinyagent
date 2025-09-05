"""
TinyAgent + OpenAI Responses API: 3 tools end-to-end.

This mirrors the LiteLLM three-tools example, but runs through TinyAgent’s
agent loop, hooks, and the Responses adapter.

Tools:
- word_count(text) -> int
- reverse_text(text) -> str
- vowel_count(text) -> int

Run:
  export OPENAI_API_KEY=...
  export TINYAGENT_LLM_API=responses
  python examples/tinyagent_responses_three_tools.py
"""

import asyncio
import os
import sys
from pathlib import Path


def _init_path():
    try:
        from tinyagent import TinyAgent  # noqa: F401
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root))


_init_path()

from tinyagent import TinyAgent, tool  # noqa: E402


@tool(name="word_count", description="Return the number of words in text.")
def word_count(text: str) -> int:
    return len([t for t in text.split() if t.strip()])


@tool(name="reverse_text", description="Reverse a string.")
def reverse_text(text: str) -> str:
    return text[::-1]


@tool(name="vowel_count", description="Count vowels (a,e,i,o,u) in a string.")
def vowel_count(text: str) -> int:
    return sum(1 for ch in text.lower() if ch in "aeiou")


def make_verbose_callback():
    def _short(s, n=200):
        s = str(s)
        return s if len(s) <= n else s[:n] + "..."

    async def cb(event_name: str, agent: TinyAgent, *args, **kwargs):
        if event_name == "agent_start":
            print(f"[agent_start] user_input={_short(kwargs.get('user_input'))}")
        elif event_name == "llm_start":
            k = args[0] if args else kwargs
            msgs = (k or {}).get("messages", [])
            tools = (k or {}).get("tools", [])
            print(f"[llm_start] messages={len(msgs)} tools={len(tools)}")
        elif event_name == "message_add":
            m = kwargs.get("message", {})
            role = m.get("role")
            content = m.get("content")
            print(f"[message_add] role={role} content={_short(content)}")
            if m.get("tool_calls"):
                print(f"  tool_calls={_short(m.get('tool_calls'))}")
        elif event_name == "tool_start":
            tc = kwargs.get("tool_call")
            name = getattr(tc.function, 'name', None) if tc else None
            args_str = getattr(tc.function, 'arguments', None) if tc else None
            print(f"[tool_start] name={name} args={_short(args_str)}")
        elif event_name == "tool_end":
            tc = kwargs.get("tool_call")
            res = kwargs.get("result")
            name = getattr(tc.function, 'name', None) if tc else None
            print(f"[tool_end] name={name} result={_short(res)}")
        elif event_name == "llm_end":
            rid = getattr(agent, "_responses_prev_id", None)
            print(f"[llm_end] last_response_id={rid}")
        elif event_name == "agent_end":
            print(f"[agent_end] result={_short(kwargs.get('result'))}")
        else:
            pass

    return cb


async def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Set a default trace file for Responses requests/responses
    if not os.getenv("RESPONSES_TRACE_FILE"):
        default_trace = str(Path.cwd() / "responses_trace.jsonl")
        os.environ["RESPONSES_TRACE_FILE"] = default_trace
        print(f"[trace] RESPONSES_TRACE_FILE set to {default_trace}")

    # Create TinyAgent in Responses mode (set via env)
    agent = await TinyAgent.create(model="gpt-5-mini", api_key=os.getenv("OPENAI_API_KEY"), parallel_tool_calls=False)
    agent.add_tools([word_count, reverse_text, vowel_count])
    agent.add_callback(make_verbose_callback())

    input_text = "Refactor often, test always."
    prompt = (
        "You MUST call all three tools on the same input text.\n"
        f"Input text: '{input_text}'.\n"
        "Steps:\n"
        "1) Call word_count(text) and wait for tool output.\n"
        "2) Then call reverse_text(text) and wait for output.\n"
        "3) Then call vowel_count(text) and wait for output.\n"
        "Finally, call final_answer summarizing the results in one concise sentence."
    )

    result = await agent.run(prompt, max_turns=12)
    print("\n=== Final ===")
    print(result)
    await agent.close()


if __name__ == "__main__":
    asyncio.run(main())

