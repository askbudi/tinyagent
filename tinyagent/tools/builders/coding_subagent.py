"""
Pre-built coding subagent tools.

This module provides ready-to-use coding subagents optimized for different
programming tasks and scenarios.
"""

from ..subagent import create_coding_subagent, SubagentConfig


# Standard coding subagent
coding_agent = create_coding_subagent(
    name="coding_agent",
    description="Full-featured coding assistant for software development tasks",
    model="gpt-5-mini",
    max_turns=25,
    temperature=0.0
)


# Python specialist subagent
python_specialist = create_coding_subagent(
    name="python_specialist", 
    description="Python programming specialist for scripts, analysis, and applications",
    model="gpt-5-mini",
    max_turns=20,
    temperature=0.0,
    system_prompt=(
        "You are a Python programming expert specializing in writing clean, efficient, "
        "and well-documented Python code. You excel at data analysis, web development, "
        "automation scripts, and algorithm implementation. Always follow Python best "
        "practices, use appropriate libraries, and include comprehensive error handling. "
        "Test your code thoroughly and provide clear explanations of your approach."
    )
)


# Code reviewer subagent
code_reviewer = create_coding_subagent(
    name="code_reviewer",
    description="Code review specialist for analyzing and improving code quality", 
    model="gpt-5-mini",
    max_turns=15,
    temperature=0.0,
    enable_shell_tool=False,  # Focus on analysis, not execution
    system_prompt=(
        "You are a senior code reviewer with expertise across multiple programming languages. "
        "Your role is to analyze code for quality, security, performance, and maintainability. "
        "Provide constructive feedback with specific suggestions for improvement. Look for "
        "code smells, potential bugs, security vulnerabilities, and opportunities for "
        "optimization. Structure your reviews with clear categories: strengths, issues, "
        "recommendations, and overall assessment."
    )
)


# Debugging specialist subagent
debug_specialist = create_coding_subagent(
    name="debug_specialist",
    description="Debugging expert for identifying and fixing code issues",
    model="gpt-5-mini", 
    max_turns=20,
    temperature=0.0,
    system_prompt=(
        "You are a debugging expert skilled at identifying, analyzing, and fixing code issues. "
        "When presented with buggy code or error messages, systematically analyze the problem, "
        "identify the root cause, and provide clear solutions. Use debugging tools and "
        "techniques to isolate issues. Explain your debugging process and provide prevention "
        "strategies to avoid similar issues in the future."
    )
)


# Quick coding helper
quick_coder = create_coding_subagent(
    name="quick_coder",
    description="Fast coding assistant for simple programming tasks",
    model="gpt-5-mini",
    max_turns=10,
    temperature=0.0,
    system_prompt=(
        "You are a fast and efficient coding assistant for quick programming tasks. "
        "Focus on delivering working solutions quickly while maintaining code quality. "
        "Provide concise, functional code with brief explanations. Ideal for small "
        "scripts, utility functions, and straightforward programming challenges."
    )
)


# Export all coding subagents
__all__ = [
    "coding_agent",
    "python_specialist",
    "code_reviewer", 
    "debug_specialist",
    "quick_coder"
]