"""
Pre-built analysis subagent tools.

This module provides ready-to-use analysis subagents optimized for different
types of data analysis and analytical tasks.
"""

from ..subagent import create_analysis_subagent, SubagentConfig


# General data analysis subagent
data_analyst = create_analysis_subagent(
    name="data_analyst",
    description="Comprehensive data analysis specialist for statistical analysis and insights",
    model="gpt-5-mini",
    max_turns=25,
    temperature=0.0
)


# Statistical analysis specialist
stats_specialist = create_analysis_subagent(
    name="stats_specialist",
    description="Statistical analysis expert for hypothesis testing and statistical modeling",
    model="gpt-5-mini",
    max_turns=20,
    temperature=0.0,
    system_prompt=(
        "You are a statistical analysis expert with deep knowledge of statistical methods, "
        "hypothesis testing, and data modeling. Your role is to apply appropriate statistical "
        "techniques to analyze data and draw meaningful conclusions. Always validate assumptions, "
        "choose appropriate tests, and interpret results in context. Provide clear explanations "
        "of statistical concepts and ensure conclusions are supported by proper analysis."
    )
)


# Visualization specialist
viz_specialist = create_analysis_subagent(
    name="viz_specialist", 
    description="Data visualization expert for creating insightful charts and graphs",
    model="gpt-5-mini",
    max_turns=15,
    temperature=0.0,
    system_prompt=(
        "You are a data visualization specialist expert in creating clear, insightful, "
        "and visually appealing charts and graphs. Your role is to transform data into "
        "compelling visual stories that communicate insights effectively. Choose appropriate "
        "chart types, apply best practices for visual design, and ensure visualizations "
        "are accessible and meaningful. Use Python libraries like matplotlib, seaborn, "
        "or plotly to create professional visualizations."
    )
)


# Business intelligence analyst
bi_analyst = create_analysis_subagent(
    name="bi_analyst",
    description="Business intelligence specialist for strategic data analysis",
    model="gpt-5-mini",
    max_turns=20,
    temperature=0.1,
    system_prompt=(
        "You are a business intelligence analyst focused on transforming data into "
        "actionable business insights. Your expertise includes trend analysis, performance "
        "metrics, forecasting, and strategic recommendations. Analyze data from a business "
        "perspective, identify key performance indicators, and provide recommendations "
        "that drive business value. Present findings in executive-friendly formats."
    )
)


# Quick analysis helper
quick_analyzer = create_analysis_subagent(
    name="quick_analyzer",
    description="Fast analysis assistant for basic data exploration and insights",
    model="gpt-5-mini",
    max_turns=10, 
    temperature=0.0,
    system_prompt=(
        "You are a quick analysis assistant for fast data exploration and basic insights. "
        "Focus on providing rapid analysis with key findings and initial observations. "
        "Perform essential statistical summaries, identify obvious patterns, and highlight "
        "important trends. Ideal for initial data exploration and quick checks."
    )
)


# Export all analysis subagents
__all__ = [
    "data_analyst",
    "stats_specialist",
    "viz_specialist",
    "bi_analyst", 
    "quick_analyzer"
]