"""
Pre-built subagent tools for common use cases.

This module provides ready-to-use subagent tools that can be directly added
to TinyAgent or TinyCodeAgent instances without additional configuration.

Available subagents:
- Research subagents: For information gathering and analysis
- Coding subagents: For software development tasks  
- Analysis subagents: For data analysis and insights

Example Usage:
    from tinyagent.tools.builders import coding_agent, research_agent
    
    # Add to your main agent
    main_agent.add_tool(coding_agent)
    main_agent.add_tool(research_agent)
    
    # Use in conversation
    await main_agent.run("Use coding_agent to implement a web scraper")
"""

# Import all pre-built subagents
from .research_subagent import (
    research_agent,
    quick_research_agent,
    deep_research_agent
)

from .coding_subagent import (
    coding_agent,
    python_specialist,
    code_reviewer,
    debug_specialist,
    quick_coder
)

from .analysis_subagent import (
    data_analyst,
    stats_specialist,
    viz_specialist,
    bi_analyst,
    quick_analyzer
)

# Also provide the factory functions for custom subagents
from ..subagent import (
    create_research_subagent,
    create_coding_subagent,
    create_analysis_subagent,
    create_writing_subagent,
    create_planning_subagent,
    create_general_subagent
)

__all__ = [
    # Pre-built research subagents
    "research_agent",
    "quick_research_agent", 
    "deep_research_agent",
    
    # Pre-built coding subagents
    "coding_agent",
    "python_specialist",
    "code_reviewer",
    "debug_specialist", 
    "quick_coder",
    
    # Pre-built analysis subagents
    "data_analyst",
    "stats_specialist",
    "viz_specialist",
    "bi_analyst",
    "quick_analyzer",
    
    # Factory functions for custom subagents
    "create_research_subagent",
    "create_coding_subagent", 
    "create_analysis_subagent",
    "create_writing_subagent",
    "create_planning_subagent",
    "create_general_subagent",
]