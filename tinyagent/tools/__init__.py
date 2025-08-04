"""
TinyAgent tools module.

This module provides various tools and subagents for TinyAgent and TinyCodeAgent,
including specialized subagents for different use cases and the factory functions
to create custom subagents.

Available tools:
- Subagent framework: Context-aware subagent tools for parallel task execution
- Pre-built subagents: Ready-to-use specialists for common tasks
- Factory functions: Create custom subagents with specific configurations
"""

# Import subagent framework
from .subagent import (
    # Configuration
    SubagentConfig,
    
    # Context management  
    SubagentContext,
    ContextManager,
    get_context_manager,
    cleanup_global_context_manager,
    
    # Factory functions
    create_subagent_tool,
    create_research_subagent,
    create_coding_subagent,
    create_analysis_subagent,
    create_writing_subagent,
    create_planning_subagent,
    create_general_subagent,
    
    # Exceptions
    SubagentExecutionError,
    
    # Backwards compatibility
    create_task_tool
)

# Import pre-built subagents
from .builders import (
    # Research subagents
    research_agent,
    quick_research_agent,
    deep_research_agent,
    
    # Coding subagents
    coding_agent,
    python_specialist,
    code_reviewer,
    debug_specialist,
    quick_coder,
    
    # Analysis subagents
    data_analyst,
    stats_specialist,
    viz_specialist,
    bi_analyst,
    quick_analyzer
)

__all__ = [
    # Configuration
    "SubagentConfig",
    
    # Context management
    "SubagentContext", 
    "ContextManager",
    "get_context_manager",
    "cleanup_global_context_manager",
    
    # Factory functions
    "create_subagent_tool",
    "create_research_subagent",
    "create_coding_subagent",
    "create_analysis_subagent", 
    "create_writing_subagent",
    "create_planning_subagent",
    "create_general_subagent",
    
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
    
    # Exceptions
    "SubagentExecutionError",
    
    # Backwards compatibility
    "create_task_tool",
]