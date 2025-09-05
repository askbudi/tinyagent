from .tiny_agent import TinyAgent, tool
from .mcp_client import MCPClient
from .core import CustomInstructionLoader

# Optional import: TinyCodeAgent may require extra dependencies (modal, docker, etc.)
try:
    from .code_agent import TinyCodeAgent  # type: ignore
    _HAS_TINY_CODE_AGENT = True
except Exception:  # ImportError or runtime deps missing
    TinyCodeAgent = None  # type: ignore
    _HAS_TINY_CODE_AGENT = False

_HAS_TOOLS = False
try:
    # Import subagent tools for easy access (optional)
    from .tools import (
        research_agent,
        coding_agent,
        data_analyst,
        create_research_subagent,
        create_coding_subagent,
        create_analysis_subagent,
        SubagentConfig,
        SubagentContext,
    )
    _HAS_TOOLS = True
except Exception:
    # Tools depend on optional environments; skip if unavailable
    pass

__all__ = [
    "TinyAgent",
    "MCPClient",
    "tool",
    "CustomInstructionLoader",
]

if _HAS_TINY_CODE_AGENT:
    __all__.append("TinyCodeAgent")

if _HAS_TOOLS:
    __all__ += [
        "research_agent",
        "coding_agent",
        "data_analyst",
        "create_research_subagent",
        "create_coding_subagent",
        "create_analysis_subagent",
        "SubagentConfig",
        "SubagentContext",
    ]
