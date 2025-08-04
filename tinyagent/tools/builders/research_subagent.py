"""
Pre-built research subagent tool.

This module provides a ready-to-use research subagent optimized for information
gathering, analysis, and synthesis tasks.
"""

from ..subagent import create_research_subagent, SubagentConfig


# Create a standard research subagent
research_agent = create_research_subagent(
    name="research_agent",
    description="Specialized research assistant for comprehensive information gathering and analysis",
    model="gpt-4.1-mini",
    max_turns=20,
    temperature=0.1
)


# Create a quick research subagent for faster responses
quick_research_agent = create_research_subagent(
    name="quick_research",
    description="Fast research assistant for basic information gathering",
    model="gpt-4.1-mini", 
    max_turns=10,
    temperature=0.0
)


# Create a deep research subagent for thorough analysis
deep_research_agent = create_research_subagent(
    name="deep_research",
    description="Thorough research specialist for comprehensive analysis and synthesis",
    model="gpt-4.1-mini",
    max_turns=30,
    temperature=0.05,
    system_prompt=(
        "You are an expert research analyst with deep expertise in information gathering, "
        "critical analysis, and synthesis. Your task is to conduct comprehensive research "
        "that goes beyond surface-level information. Provide detailed findings with proper "
        "analysis, context, and implications. Consider multiple perspectives and evaluate "
        "the credibility and relevance of information. Structure your research findings "
        "clearly with executive summary, detailed analysis, and actionable insights."
    )
)


# Export all research subagents
__all__ = [
    "research_agent",
    "quick_research_agent", 
    "deep_research_agent"
]