"""
Main subagent tool implementation with hook-based architecture and factory integration.

This module provides the core subagent tool that creates isolated agent instances
for parallel task execution with clean context separation. It integrates seamlessly
with TinyAgent's hook system and supports custom agent factories for maximum flexibility.

Key Features:
- Hook-based architecture with LoggingManager integration
- Agent factory pattern support for custom agent creation
- Automatic parameter inheritance from parent agents
- Comprehensive error handling and resource management
- Support for all TinyAgent/TinyCodeAgent parameters

Examples:
    # Basic usage with automatic agent creation
    tool = create_subagent_tool(
        name="helper",
        config=SubagentConfig(model="gpt-5-mini")
    )
    
    # With parent agent inheritance
    config = SubagentConfig.from_parent_agent(
        parent_agent=main_agent,
        max_turns=20
    )
    tool = create_subagent_tool("helper", config)
    
    # With custom agent factory
    def my_factory(**kwargs):
        return TinyCodeAgent(**kwargs)
        
    tool = create_subagent_tool(
        name="coder",
        config=config,
        agent_factory=my_factory
    )
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any, Union, Callable, TYPE_CHECKING
from textwrap import dedent

from tinyagent import tool, TinyAgent
from tinyagent.code_agent.tiny_code_agent import TinyCodeAgent
from .config import SubagentConfig
from .context import get_context_manager, SubagentContext

if TYPE_CHECKING:
    from tinyagent.hooks.logging_manager import LoggingManager


class SubagentExecutionError(Exception):
    """Exception raised during subagent execution."""
    pass


async def _create_agent_from_config(
    config: SubagentConfig,
    context: SubagentContext,
    logger: Optional[logging.Logger] = None,
    agent_factory: Optional[Callable] = None
) -> Union[TinyAgent, TinyCodeAgent]:
    """
    Create an agent instance based on configuration.
    
    This function creates either a TinyAgent or TinyCodeAgent based on the configuration,
    or uses a custom agent factory if provided. It properly handles all configuration
    parameters and integrates with the hook system.
    
    Args:
        config: Subagent configuration with all parameters
        context: Execution context for resource management
        logger: Optional logger instance (uses config's logger if not provided)
        agent_factory: Optional custom factory function for creating agents
        
    Returns:
        Configured agent instance (TinyAgent, TinyCodeAgent, or custom agent)
        
    Examples:
        # Standard agent creation
        agent = await _create_agent_from_config(config, context, logger)
        
        # With custom factory
        def my_factory(**kwargs):
            return TinyCodeAgent(**kwargs)
        agent = await _create_agent_from_config(config, context, logger, my_factory)
    """
    # Use custom factory if provided
    if agent_factory:
        # Get all configuration parameters for the factory
        agent_kwargs = config.to_agent_kwargs(exclude_subagent_params=False)
        
        # Remove conflicting logger parameters - factory should handle this appropriately
        agent_kwargs.pop('logger', None)
        agent_kwargs.pop('log_manager', None)
        
        # Add the provided logger if available (factories can choose to use logger or log_manager)
        if logger:
            agent_kwargs['logger'] = logger
        if config.log_manager:
            agent_kwargs['log_manager'] = config.log_manager
        
        # Create agent using factory
        agent = agent_factory(**agent_kwargs)
    else:
        # Use standard agent creation
        agent_kwargs = config.to_agent_kwargs(exclude_subagent_params=True)
        
        # Determine if we need a code agent or regular agent
        needs_code_agent = config.enable_python_tool or config.enable_shell_tool
        
        if needs_code_agent:
            # For TinyCodeAgent, we need to handle logger/log_manager parameters carefully
            # TinyCodeAgent expects log_manager, not logger
            code_agent_kwargs = {
                **agent_kwargs,
                'enable_python_tool': config.enable_python_tool,
                'enable_shell_tool': config.enable_shell_tool,
                'local_execution': config.local_execution,
                'default_workdir': config.working_directory or config.default_workdir or os.getcwd(),
            }
            
            # Remove parameters that can cause conflicts
            code_agent_kwargs.pop('logger', None)
            code_agent_kwargs.pop('additional_params', None)  # TinyAgent doesn't accept this
            
            # If a logger is provided, we need to convert it to a log_manager-like object
            # or create a simple wrapper. For now, we'll skip the logger override for TinyCodeAgent
            # since it uses log_manager internally
            
            # Add provider config if specified
            if config.provider:
                code_agent_kwargs['provider'] = config.provider
            if config.provider_config:
                code_agent_kwargs['provider_config'] = config.provider_config.copy()
                
            # Add environment variables to provider config
            if config.environment_variables:
                if 'provider_config' not in code_agent_kwargs:
                    code_agent_kwargs['provider_config'] = {}
                code_agent_kwargs['provider_config']['environment_variables'] = config.environment_variables
            
            # Add tools if specified
            if config.tools:
                code_agent_kwargs['tools'] = config.tools
            
            agent = TinyCodeAgent(**code_agent_kwargs)
        else:
            # Create regular TinyAgent
            # Remove parameters that TinyAgent doesn't accept
            agent_kwargs.pop('logger', None)
            agent_kwargs.pop('log_manager', None)
            agent_kwargs.pop('additional_params', None)
            
            # Add the provided logger if available
            if logger:
                agent_kwargs['logger'] = logger
                
            if config.tools:
                agent_kwargs['tools'] = config.tools
            agent = TinyAgent(**agent_kwargs)
    
    # Add callbacks from configuration
    if config.callbacks:
        for callback in config.callbacks:
            agent.add_callback(callback)
    
    # Store agent in context for cleanup
    context.agent_instance = agent
    if hasattr(agent, 'close'):
        context.add_cleanup_callback(agent.close)
    
    return agent


def create_subagent_tool(
    name: str,
    config: SubagentConfig,
    description: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
    agent_factory: Optional[Callable] = None
) -> callable:
    """
    Create a subagent tool with comprehensive configuration support and factory integration.
    
    This is the main factory function for creating context-aware subagent tools that provide
    clean isolation, automatic resource management, and seamless integration with TinyAgent's
    hook system. It supports custom agent factories for maximum flexibility.
    
    Args:
        name: Name of the subagent tool (will appear in tool descriptions)
        config: SubagentConfig instance with all configuration parameters
        description: Optional custom tool description (auto-generated if not provided)
        logger: Optional logger instance (inherits from config.log_manager if not provided)
        agent_factory: Optional custom factory function for creating agents
        
    Returns:
        A tool function that can be added to parent agents
        
    Examples:
        # Basic usage with automatic configuration
        config = SubagentConfig(model="gpt-5-mini", max_turns=15)
        tool = create_subagent_tool("helper", config)
        main_agent.add_tool(tool)
        
        # With parent agent inheritance
        config = SubagentConfig.from_parent_agent(
            parent_agent=main_agent,
            model="claude-3-sonnet"
        )
        tool = create_subagent_tool("research_agent", config)
        
        # With custom agent factory
        def my_bash_factory(**kwargs):
            return bash_agent_factory(
                log_manager=kwargs.get('log_manager'),
                repo="my-repo",
                home_dir="/tmp",
                **kwargs
            )
        
        tool = create_subagent_tool(
            "bash_helper", 
            config, 
            agent_factory=my_bash_factory
        )
        
        # With custom description and logger
        logger = config.create_logger("custom_subagent")
        tool = create_subagent_tool(
            "custom_agent",
            config,
            description="Specialized agent for custom tasks",
            logger=logger
        )
    """
    # Use logger from config if not provided
    if logger is None:
        logger = config.create_logger(name)
    
    # Generate tool description if not provided
    if description is None:
        tool_description = _generate_tool_description(name, config)
    else:
        tool_description = description
    
    @tool(name=name, description=tool_description)
    async def subagent_tool(
        prompt: str,
        working_directory: Optional[str] = None,
        description: str = "Execute specialized subtask"
    ) -> str:
        """
        Execute a task using a specialized subagent with full hook integration.
        
        This function creates an isolated subagent instance that inherits configuration
        from the parent agent while maintaining complete context separation. The subagent
        can execute with custom factories and has access to all configured hooks and callbacks.
        
        Args:
            prompt: Detailed and complete prompt for the subagent task. Should include 
                   all necessary context, requirements, and expectations since the subagent
                   operates independently without access to parent agent's context.
            working_directory: Optional absolute path for the subagent's working directory.
                              If not provided, uses the configured working directory or 
                              defaults to current directory.
            description: Brief description of what this subagent will accomplish.
                        Used for logging, monitoring, and debugging purposes.
        
        Returns:
            The complete response from the subagent execution
            
        Raises:
            SubagentExecutionError: If subagent execution fails or times out
        """
        context_manager = get_context_manager(logger)
        
        # Use configured working directory if not provided
        effective_workdir = working_directory or config.working_directory
        
        async with context_manager.managed_context(
            task_description=description,
            working_directory=effective_workdir,
            environment_vars=config.environment_variables or {}
        ) as context:
            
            try:
                # Initialize context
                context.initial_prompt = prompt
                context.mark_started()
                context.add_log(f"Creating subagent '{name}' with model: {config.model}")
                
                if agent_factory:
                    context.add_log(f"Using custom agent factory: {agent_factory.__name__}")
                
                # Create the agent with optional factory
                agent = await _create_agent_from_config(
                    config=config, 
                    context=context, 
                    logger=logger,
                    agent_factory=agent_factory
                )
                context.add_log("Subagent created successfully")
                
                # Execute with timeout handling if configured
                if config.timeout:
                    context.add_log(f"Executing with timeout: {config.timeout}s")
                    try:
                        result = await asyncio.wait_for(
                            agent.run(prompt, max_turns=config.max_turns),
                            timeout=config.timeout
                        )
                    except asyncio.TimeoutError:
                        context.mark_timeout()
                        error_msg = f"Subagent '{name}' execution timed out after {config.timeout} seconds"
                        logger.warning(error_msg)
                        raise SubagentExecutionError(error_msg)
                else:
                    context.add_log(f"Executing without timeout, max_turns: {config.max_turns}")
                    result = await agent.run(prompt, max_turns=config.max_turns)
                
                # Mark completion and log results
                context.mark_completed(result)
                duration = context.get_duration()
                result_length = len(result) if result else 0
                
                context.add_log(f"Task completed successfully")
                context.add_log(f"Result length: {result_length} characters")
                context.add_log(f"Execution time: {duration:.2f}s")
                
                logger.info(
                    f"Subagent '{name}' completed task in {duration:.2f}s: {description[:50]}..."
                )
                
                return result
                
            except SubagentExecutionError:
                # Re-raise our custom exceptions without modification
                raise
            except Exception as e:
                # Handle unexpected errors
                error_msg = f"Subagent '{name}' execution failed: {str(e)}"
                context.mark_failed(error_msg)
                context.add_log(f"ERROR: {error_msg}")
                
                logger.error(f"Subagent '{name}' failed: {error_msg}", exc_info=True)
                raise SubagentExecutionError(error_msg) from e
    
    # Store metadata in the tool for inspection and debugging
    subagent_tool._subagent_config = config
    subagent_tool._subagent_name = name
    subagent_tool._agent_factory = agent_factory
    subagent_tool._logger = logger
    
    return subagent_tool


def _generate_tool_description(name: str, config: SubagentConfig) -> str:
    """
    Generate a comprehensive tool description based on configuration.
    
    Args:
        name: Name of the subagent tool
        config: Configuration object
        
    Returns:
        Formatted tool description string
    """
    return dedent(f"""
        Launch a specialized subagent '{name}' to handle subtasks with clean context isolation.
        
        Configuration:
        - Model: {config.model}
        - Max turns: {config.max_turns}
        - Python execution: {'enabled' if config.enable_python_tool else 'disabled'}
        - Shell execution: {'enabled' if config.enable_shell_tool else 'disabled'}
        - Timeout: {config.timeout}s if config.timeout else 'none'
        - Working directory: {config.working_directory or 'default'}
        
        This subagent operates in complete isolation from the main agent with its own:
        - Context window and conversation history
        - Resource management and cleanup
        - Hook integration (logging, callbacks, etc.)
        - Error handling and timeout management
        
        Usage Guidelines:
        1. Provide complete context in the prompt - subagent has no access to parent context
        2. Include all necessary information, requirements, and expectations
        3. Multiple subagents can run concurrently for parallel processing
        4. Each execution is stateless and independent
        5. Results are comprehensive and self-contained
        
        The subagent inherits configuration from the parent agent while maintaining
        complete operational independence.
    """).strip()


# Convenience functions for common subagent types

def create_research_subagent(
    name: str = "research_subagent",
    description: Optional[str] = None,
    **config_kwargs
) -> callable:
    """Create a subagent specialized for research tasks."""
    config = SubagentConfig.for_research(**config_kwargs)
    desc = description or "Research and analyze information on a specific topic"
    return create_subagent_tool(name, config, desc)


def create_coding_subagent(
    name: str = "coding_subagent", 
    description: Optional[str] = None,
    **config_kwargs
) -> callable:
    """Create a subagent specialized for coding tasks."""
    config = SubagentConfig.for_coding(**config_kwargs)
    desc = description or "Write, test, and debug code for a specific programming task"
    return create_subagent_tool(name, config, desc)


def create_analysis_subagent(
    name: str = "analysis_subagent",
    description: Optional[str] = None, 
    **config_kwargs
) -> callable:
    """Create a subagent specialized for data analysis tasks."""
    config = SubagentConfig.for_analysis(**config_kwargs)
    desc = description or "Perform data analysis and generate insights"
    return create_subagent_tool(name, config, desc)


def create_writing_subagent(
    name: str = "writing_subagent",
    description: Optional[str] = None,
    **config_kwargs
) -> callable:
    """Create a subagent specialized for writing tasks."""
    config = SubagentConfig.for_writing(**config_kwargs)
    desc = description or "Create well-structured written content"
    return create_subagent_tool(name, config, desc)


def create_planning_subagent(
    name: str = "planning_subagent",
    description: Optional[str] = None,
    **config_kwargs
) -> callable:
    """Create a subagent specialized for planning tasks."""
    config = SubagentConfig.for_planning(**config_kwargs)
    desc = description or "Create detailed plans and strategic approaches"
    return create_subagent_tool(name, config, desc)


# Backwards compatibility - renamed from "task" to "subagent"
def create_task_tool(*args, **kwargs):
    """
    Backwards compatibility function - use create_subagent_tool instead.
    
    This function is deprecated and will be removed in a future version.
    """
    import warnings
    warnings.warn(
        "create_task_tool is deprecated. Use create_subagent_tool instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return create_subagent_tool(*args, **kwargs)


# Default general-purpose subagent
def create_general_subagent(
    name: str = "subagent",
    model: str = "gpt-5-mini",
    max_turns: int = 15,
    enable_python: bool = True,
    enable_shell: bool = True,
    **kwargs
) -> callable:
    """
    Create a general-purpose subagent tool.
    
    This is equivalent to your original task tool but with enhanced features
    and proper context management.
    
    Args:
        name: Name of the tool
        model: Model to use for the subagent
        max_turns: Maximum number of conversation turns
        enable_python: Whether to enable Python execution
        enable_shell: Whether to enable shell execution
        **kwargs: Additional configuration options
        
    Returns:
        A configured subagent tool
    """
    config = SubagentConfig(
        model=model,
        max_turns=max_turns,
        enable_python_tool=enable_python,
        enable_shell_tool=enable_shell,
        system_prompt=(
            "You are a helpful AI assistant that can execute Python code and shell commands "
            "to solve problems. You have been created to handle a specific subtask independently. "
            "The main agent doesn't know anything about you, so provide complete information "
            "in your response. Use the available tools when appropriate to accomplish your objectives."
        ),
        **kwargs
    )
    
    description = (
        "Launch a general-purpose subagent that can handle various tasks including "
        "code execution, shell commands, analysis, and problem-solving"
    )
    
    return create_subagent_tool(name, config, description)