from .tiny_agent import TinyAgent, tool
from .legacy_mcp_client import MCPClient  # Deprecated, use new MCP classes below
from .mcp_client import TinyMCPTools, TinyMultiMCPTools, MCPServerConfig
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
    "MCPClient",  # Deprecated - will be removed in v0.2.0
    "TinyMCPTools",  # New Agno-style MCP client
    "TinyMultiMCPTools",  # Multi-server MCP manager
    "MCPServerConfig",  # Server configuration class
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
