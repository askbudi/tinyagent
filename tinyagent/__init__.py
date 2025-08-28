from .tiny_agent import TinyAgent,tool
from .mcp_client import MCPClient
from .code_agent import TinyCodeAgent
from .core import CustomInstructionLoader

# Import subagent tools for easy access
from .tools import (
    # Pre-built subagents for immediate use
    research_agent,
    coding_agent,
    data_analyst,
    
    # Factory functions for custom subagents
    create_research_subagent,
    create_coding_subagent,
    create_analysis_subagent,
    
    # Configuration and context management
    SubagentConfig,
    SubagentContext
)

__all__ = [
    "TinyAgent", 
    "MCPClient",
    "tool", 
    "TinyCodeAgent",
    "CustomInstructionLoader",
    
    # Pre-built subagents
    "research_agent",
    "coding_agent", 
    "data_analyst",
    
    # Factory functions
    "create_research_subagent",
    "create_coding_subagent",
    "create_analysis_subagent",
    
    # Configuration
    "SubagentConfig",
    "SubagentContext"
]