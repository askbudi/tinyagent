"""
Subagent tools for TinyAgent and TinyCodeAgent.

This module provides context-aware subagent tools that enable parallel task execution
with clean context isolation. Each subagent runs independently with its own context
window and resources, providing better scalability and resource management.

Main Components:
- SubagentConfig: Flexible configuration for subagent behavior
- SubagentContext: Context management for execution isolation  
- ContextManager: Resource management and cleanup
- Subagent tools: Factory functions for creating specialized subagents

Example Usage:
    # Create a coding subagent
    coding_tool = create_coding_subagent(
        name="code_helper",
        model="gpt-5-mini",
        max_turns=20
    )
    
    # Add to your main agent
    main_agent.add_tool(coding_tool)
    
    # Use in conversation
    result = await main_agent.run("Use code_helper to implement a sorting algorithm")
"""

from .config import SubagentConfig
from .context import (
    SubagentContext,
    ContextManager, 
    get_context_manager,
    cleanup_global_context_manager
)
from .subagent_tool import (
    create_subagent_tool,
    create_research_subagent,
    create_coding_subagent,
    create_analysis_subagent,
    create_writing_subagent,
    create_planning_subagent,
    create_general_subagent,
    SubagentExecutionError,
    # Backwards compatibility
    create_task_tool
)

__all__ = [
    # Configuration
    "SubagentConfig",
    
    # Context management
    "SubagentContext",
    "ContextManager",
    "get_context_manager", 
    "cleanup_global_context_manager",
    
    # Tool creation
    "create_subagent_tool",
    "create_research_subagent",
    "create_coding_subagent", 
    "create_analysis_subagent",
    "create_writing_subagent",
    "create_planning_subagent",
    "create_general_subagent",
    
    # Exceptions
    "SubagentExecutionError",
    
    # Backwards compatibility
    "create_task_tool",
]