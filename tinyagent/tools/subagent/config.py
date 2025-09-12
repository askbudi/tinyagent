"""
Configuration classes for subagent tools with hook-based architecture.

This module provides flexible configuration options for creating specialized subagent tools
with seamless integration into TinyAgent's hook system, comprehensive parameter inheritance,
and future-proof extensibility.

Key Features:
- Full integration with TinyAgent's LoggingManager and callback system
- Automatic parameter inheritance from parent agents
- Support for all TinyAgent/TinyCodeAgent constructor parameters
- Future-proof architecture that adapts to new parameters automatically

Examples:
    # Create configuration from parent agent
    config = SubagentConfig.from_parent_agent(
        parent_agent=main_agent,
        model="gpt-5-mini",  # Override specific parameters
        max_turns=15,
        enable_python_tool=True
    )
    
    # Manual configuration with hooks
    config = SubagentConfig(
        model="claude-3-sonnet",
        log_manager=log_manager,
        session_id="session_123",
        user_id="user_456",
        callbacks=[token_tracker, gradio_callback]
    )
    
    # Use with agent factory
    tool = create_subagent_tool(
        name="coder",
        config=config,
        agent_factory=bash_agent_factory
    )
"""

import os
import logging
from typing import Dict, List, Optional, Any, Union, Callable, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from tinyagent.tiny_agent import TinyAgent
    from tinyagent.code_agent.tiny_code_agent import TinyCodeAgent
    from tinyagent.hooks.logging_manager import LoggingManager


@dataclass
class SubagentConfig:
    """
    Configuration class for subagent tools with comprehensive parameter support.
    
    This configuration class supports all TinyAgent/TinyCodeAgent parameters and provides
    seamless integration with the hook system. It can automatically inherit settings from
    a parent agent while allowing for specific overrides.
    
    The configuration follows a hook-based architecture that integrates with:
    - LoggingManager for centralized logging configuration
    - Callback system for token tracking, UI updates, etc.
    - Storage and session management
    - All future TinyAgent parameters automatically
    
    Attributes:
        # Core Agent Parameters (passed directly to TinyAgent/TinyCodeAgent)
        model: Model identifier (e.g., "gpt-5-mini", "claude-3-sonnet")
        api_key: API key for the model provider
        temperature: Model temperature (0.0-2.0)
        log_manager: LoggingManager instance for centralized logging
        session_id: Session identifier for tracking
        user_id: User identifier for tracking
        storage: Storage backend for persistence
        callbacks: List of callback functions for hooks
        
        # Code Agent Specific Parameters
        enable_python_tool: Enable Python code execution
        enable_shell_tool: Enable shell command execution
        local_execution: Use local execution instead of remote
        default_workdir: Default working directory
        provider: Execution provider (e.g., "seatbelt", "docker")
        provider_config: Provider-specific configuration
        
        # Subagent Specific Parameters
        max_turns: Maximum conversation turns for the subagent
        timeout: Execution timeout in seconds
        inherit_parent_hooks: Whether to inherit parent's callbacks
        working_directory: Override working directory for this subagent
        environment_variables: Environment variables for subagent execution
        
        # Advanced Configuration
        retry_config: Retry configuration for failed requests
        parallel_tool_calls: Enable parallel tool execution
        model_kwargs: Additional model-specific parameters
        additional_params: Any additional parameters for future extensibility
        
    Examples:
        # Inherit from parent with overrides
        config = SubagentConfig.from_parent_agent(
            parent_agent=main_agent,
            model="gpt-5-mini",
            max_turns=20,
            enable_python_tool=True
        )
        
        # Manual configuration
        config = SubagentConfig(
            model="claude-3-sonnet", 
            log_manager=my_log_manager,
            callbacks=[token_tracker],
            max_turns=15
        )
        
        # Specialized configurations
        research_config = SubagentConfig.for_research(
            parent_agent=main_agent,
            model="gpt-4o"
        )
    """
    
    # ============================================================================
    # Core Agent Parameters (TinyAgent/TinyCodeAgent constructor parameters)
    # ============================================================================
    
    model: str = "gpt-5-mini"
    """Model identifier for the subagent (e.g., 'gpt-5-mini', 'claude-3-sonnet')."""
    
    api_key: Optional[str] = None
    """API key for the model provider. Auto-detected from environment if None."""
    
    temperature: float = 0.0
    """Model temperature for response randomness (0.0-2.0)."""
    
    log_manager: Optional['LoggingManager'] = None
    """LoggingManager instance for centralized logging configuration."""
    
    session_id: Optional[str] = None
    """Session identifier for tracking and persistence."""
    
    user_id: Optional[str] = None
    """User identifier for tracking and personalization."""
    
    storage: Optional[Any] = None
    """Storage backend for conversation persistence."""
    
    callbacks: List[Callable] = field(default_factory=list)
    """List of callback functions for hooks (token tracking, UI updates, etc.)."""
    
    # ============================================================================
    # Code Agent Specific Parameters
    # ============================================================================
    
    enable_python_tool: bool = True
    """Enable Python code execution capabilities."""
    
    enable_shell_tool: bool = True
    """Enable shell command execution capabilities."""
    
    enable_file_tools: bool = True
    """Enable sandbox-constrained file tools (read_file, write_file, update_file, glob_tool, grep_tool)."""
    
    enable_todo_write: bool = True
    """Enable TodoWrite tool for task management."""
    
    local_execution: bool = True
    """Use local execution instead of remote execution."""
    
    default_workdir: Optional[str] = None
    """Default working directory for code execution."""
    
    provider: Optional[str] = None
    """Execution provider (e.g., 'seatbelt', 'docker', 'local')."""
    
    provider_config: Optional[Dict[str, Any]] = None
    """Provider-specific configuration dictionary."""
    
    tools: Optional[List[Any]] = None
    """Additional tools to make available to the subagent."""
    
    # ============================================================================
    # Subagent Specific Parameters
    # ============================================================================
    
    max_turns: int = 10
    """Maximum number of conversation turns for the subagent."""
    
    timeout: Optional[int] = None
    """Execution timeout in seconds. None for no timeout."""
    
    inherit_parent_hooks: bool = True
    """Whether to inherit callbacks and hooks from the parent agent."""
    
    working_directory: Optional[str] = None
    """Override working directory specifically for this subagent."""
    
    environment_variables: Optional[Dict[str, str]] = None
    """Environment variables for subagent execution."""
    
    # ============================================================================
    # Advanced Configuration
    # ============================================================================
    
    system_prompt: Optional[str] = None
    """Custom system prompt for the subagent. Auto-generated if None."""
    
    retry_config: Optional[Dict[str, Any]] = None
    """Retry configuration for failed API requests."""
    
    parallel_tool_calls: bool = True
    """Enable parallel tool execution for better performance."""
    
    model_kwargs: Dict[str, Any] = field(default_factory=dict)
    """Additional model-specific parameters."""
    
    additional_params: Dict[str, Any] = field(default_factory=dict)
    """Additional parameters for future extensibility and custom agent factories."""
    
    # Private field to store parent agent for system prompt building
    _parent_agent: Optional[Union['TinyAgent', 'TinyCodeAgent']] = field(default=None, init=False, repr=False)
    """Internal field to store parent agent reference for system prompt building."""
    
    def __post_init__(self):
        """
        Post-initialization to set defaults and validate configuration.
        
        This method is automatically called after object creation to:
        - Set API key from environment if not provided
        - Generate default system prompt if none provided
        - Validate all configuration parameters
        - Ensure working directory defaults are set correctly
        """
        # Set API key from environment if not provided
        if self.api_key is None:
            self.api_key = self._get_api_key_for_model(self.model)
        
        # Set default system prompt if none provided
        if self.system_prompt is None:
            self.system_prompt = self._build_system_prompt()
        
        # Set working directory defaults
        if self.working_directory is None and self.default_workdir:
            self.working_directory = self.default_workdir
        
        # Validate configuration
        self._validate_config()
    
    def _get_api_key_for_model(self, model: str) -> Optional[str]:
        """Get appropriate API key based on model name."""
        model_lower = model.lower()
        
        # OpenAI models
        if any(provider in model_lower for provider in ['gpt', 'o1', 'o3', 'o4']):
            return os.environ.get("OPENAI_API_KEY")
        
        # Anthropic models
        elif any(provider in model_lower for provider in ['claude', 'anthropic']):
            return os.environ.get("ANTHROPIC_API_KEY")
        
        # Google models
        elif any(provider in model_lower for provider in ['gemini', 'google']):
            return os.environ.get("GOOGLE_API_KEY")
        
        # Groq models
        elif 'groq' in model_lower:
            return os.environ.get("GROQ_API_KEY")
        
        # OpenRouter models
        elif 'openrouter' in model_lower:
            return os.environ.get("OPENROUTER_API_KEY")
        
        # Together AI models
        elif 'together' in model_lower:
            return os.environ.get("TOGETHERAI_API_KEY")
        
        # xAI models
        elif 'xai' in model_lower or 'grok' in model_lower:
            return os.environ.get("XAI_API_KEY")
        
        # Default fallback
        return os.environ.get("OPENAI_API_KEY")
    
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for subagents."""
        return (
            "You are a helpful AI assistant specialized in completing specific tasks. "
            "You have been created to handle a subtask with focused expertise. "
            "Complete the given task thoroughly and provide a clear, comprehensive response. "
            "Use the available tools when appropriate to accomplish your objectives."
        )
    
    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for subagents, similar to parent agents.
        
        If a parent agent was provided during creation, attempts to use its
        _build_system_prompt method for consistency. Otherwise falls back
        to a default prompt.
        
        Returns:
            System prompt string
        """
        # If we have a parent agent and it has a _build_system_prompt method, try to use it
        if self._parent_agent and hasattr(self._parent_agent, '_build_system_prompt'):
            try:
                # For TinyCodeAgent, we can use its _build_system_prompt method
                # This will include tool information, authorized imports, etc.
                return self._parent_agent._build_system_prompt()
            except Exception as e:
                # If parent's system prompt building fails, log and fall back
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to build system prompt from parent agent: {e}")
                return self._get_default_system_prompt()
        
        # If parent agent exists but doesn't have _build_system_prompt (like base TinyAgent),
        # use its default system prompt as a base or use a sensible default
        if self._parent_agent:
            # For TinyAgent, check if it has a system prompt in its messages
            if hasattr(self._parent_agent, 'messages') and self._parent_agent.messages:
                parent_system_msg = self._parent_agent.messages[0].get('content', '')
                if parent_system_msg and 'helpful AI assistant' in parent_system_msg:
                    # Adapt the parent's system prompt for subagent use
                    return (
                        "You are a helpful AI assistant specialized in completing specific tasks. "
                        "You have been created to handle a subtask with focused expertise. "
                        "Complete the given task thoroughly and provide a clear, comprehensive response. "
                        "Use the available tools when appropriate to accomplish your objectives."
                    )
        
        # Default fallback
        return self._get_default_system_prompt()
    
    def _validate_config(self):
        """Validate the configuration settings."""
        if self.max_turns <= 0:
            raise ValueError("max_turns must be greater than 0")
        
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be greater than 0")
        
        if self.temperature < 0 or self.temperature > 2:
            raise ValueError("temperature must be between 0 and 2")
    
    @classmethod
    def from_parent_agent(
        cls, 
        parent_agent: Union['TinyAgent', 'TinyCodeAgent'],
        **overrides
    ) -> 'SubagentConfig':
        """
        Create a SubagentConfig by inheriting settings from a parent agent.
        
        This method extracts relevant configuration from a parent agent and creates
        a new SubagentConfig that inherits the parent's settings while allowing
        for specific overrides. This ensures consistency between parent and child
        agents while enabling specialization.
        
        Args:
            parent_agent: The parent TinyAgent or TinyCodeAgent to inherit from
            **overrides: Any configuration parameters to override from the parent.
                        Special overrides:
                        - tracker_name: Custom name for child TokenTracker (if parent has one)
            
        Returns:
            A new SubagentConfig with inherited settings
            
        Examples:
            # Basic inheritance with model override
            config = SubagentConfig.from_parent_agent(
                parent_agent=main_agent,
                model="gpt-5-mini"
            )
            
            # Inherit everything, override specific settings
            config = SubagentConfig.from_parent_agent(
                parent_agent=main_agent,
                max_turns=20,
                enable_python_tool=True,
                system_prompt="You are a coding specialist..."
            )
            
            # Use with different execution settings
            config = SubagentConfig.from_parent_agent(
                parent_agent=main_agent,
                provider="docker",
                provider_config={"image": "python:3.11"},
                working_directory="/tmp/subagent"
            )
            
            # Custom token tracker name (if parent has TokenTracker)
            config = SubagentConfig.from_parent_agent(
                parent_agent=main_agent,
                tracker_name="specialized_research_agent",
                max_turns=15
            )
            
            # Explicit callbacks are merged with inherited TokenTracker
            config = SubagentConfig.from_parent_agent(
                parent_agent=main_agent,
                callbacks=[jupyter_callback, message_cleanup],  # These will be merged with TokenTracker
                tracker_name="TaskAgent_tracker"
            )
        """
        # Extract configuration from parent agent
        inherited_params = {}
        
        # Core parameters that should be inherited
        inherit_attrs = [
            'model', 'api_key', 'temperature', 'log_manager', 'session_id', 
            'user_id', 'storage', 'local_execution', 'default_workdir',
            'provider', 'provider_config', 'retry_config', 'parallel_tool_calls',
            'model_kwargs', 'enable_todo_write'
        ]
        
        # Parameters that need deep copying to avoid mutation
        deep_copy_attrs = {'model_kwargs', 'provider_config', 'retry_config'}
        
        for attr in inherit_attrs:
            if hasattr(parent_agent, attr):
                value = getattr(parent_agent, attr)
                if value is not None:
                    # Deep copy parameters that might be mutated by agents
                    if attr in deep_copy_attrs:
                        import copy
                        inherited_params[attr] = copy.deepcopy(value)
                    else:
                        inherited_params[attr] = value
        
        # Handle callbacks with inheritance control, including special TokenTracker handling
        # This processes parent callbacks and creates child TokenTracker if needed
        inherited_callbacks = []
        parent_token_tracker = None
        
        if hasattr(parent_agent, 'callbacks') and parent_agent.callbacks:
            # Look for TokenTracker in parent callbacks and handle specially
            for callback in parent_agent.callbacks:
                # Check if this is a TokenTracker by looking for its characteristic methods
                if (hasattr(callback, 'track_llm_call') and 
                    hasattr(callback, 'add_child_tracker') and
                    hasattr(callback, 'get_total_usage')):
                    parent_token_tracker = callback
                    # Don't add the parent's TokenTracker directly - we'll create a child instead
                else:
                    # Copy other non-TokenTracker callbacks as-is (only if no explicit callbacks provided)
                    if 'callbacks' not in overrides:
                        inherited_callbacks.append(callback)
            
            # If parent has a TokenTracker, create a child tracker for the subagent
            if parent_token_tracker:
                try:
                    # Import TokenTracker - we do this here to avoid circular imports
                    from tinyagent.hooks.token_tracker import TokenTracker
                    
                    # Create a child tracker with the parent tracker
                    # Use overrides.get() to allow customization of tracker name
                    subagent_name = overrides.get('tracker_name', f"{parent_token_tracker.name}_subagent")
                    child_tracker = TokenTracker(
                        name=subagent_name,
                        parent_tracker=parent_token_tracker,
                        logger=parent_token_tracker.logger,
                        enable_detailed_logging=parent_token_tracker.enable_detailed_logging,
                        track_per_model=parent_token_tracker.track_per_model,
                        track_per_provider=parent_token_tracker.track_per_provider
                    )
                    inherited_callbacks.append(child_tracker)
                except ImportError:
                    # If TokenTracker import fails, fall back to copying parent callbacks
                    if 'callbacks' not in overrides:
                        inherited_callbacks.extend(parent_agent.callbacks)
                except Exception:
                    # If any other error occurs, fall back to copying parent callbacks
                    if 'callbacks' not in overrides:
                        inherited_callbacks.extend(parent_agent.callbacks)
        
        # Set inherited callbacks only if no explicit callbacks were provided
        if 'callbacks' not in overrides and inherited_callbacks:
            inherited_params['callbacks'] = inherited_callbacks
        
        # Handle tools if present
        if hasattr(parent_agent, 'tools') and parent_agent.tools:
            inherited_params['tools'] = list(parent_agent.tools)
        
        # Special handling for code agent specific attributes
        if hasattr(parent_agent, 'enable_python_tool'):
            inherited_params['enable_python_tool'] = parent_agent.enable_python_tool
        if hasattr(parent_agent, 'enable_shell_tool'):
            inherited_params['enable_shell_tool'] = parent_agent.enable_shell_tool
        if hasattr(parent_agent, 'enable_file_tools'):
            inherited_params['enable_file_tools'] = parent_agent.enable_file_tools
        elif hasattr(parent_agent, '_file_tools_enabled'):
            inherited_params['enable_file_tools'] = parent_agent._file_tools_enabled
        
        # Filter out special overrides that are not SubagentConfig parameters
        special_overrides = {'tracker_name'}  # Add more as needed
        filtered_overrides = {k: v for k, v in overrides.items() if k not in special_overrides}
        
        # Apply filtered overrides
        inherited_params.update(filtered_overrides)
        
        # Handle special case: merge explicit callbacks with inherited TokenTracker
        if 'callbacks' in overrides and parent_token_tracker:
            explicit_callbacks = overrides['callbacks']
            merged_callbacks = list(explicit_callbacks) if explicit_callbacks else []
            
            # Add child TokenTracker to explicit callbacks if parent has one
            try:
                from tinyagent.hooks.token_tracker import TokenTracker
                
                subagent_name = overrides.get('tracker_name', f"{parent_token_tracker.name}_subagent")
                child_tracker = TokenTracker(
                    name=subagent_name,
                    parent_tracker=parent_token_tracker,
                    logger=parent_token_tracker.logger,
                    enable_detailed_logging=parent_token_tracker.enable_detailed_logging,
                    track_per_model=parent_token_tracker.track_per_model,
                    track_per_provider=parent_token_tracker.track_per_provider
                )
                merged_callbacks.append(child_tracker)
                inherited_params['callbacks'] = merged_callbacks
            except (ImportError, Exception):
                # If TokenTracker creation fails, just use explicit callbacks as-is
                pass
        
        # Create new config
        config = cls(**inherited_params)
        
        # Store parent agent reference for system prompt building
        config._parent_agent = parent_agent
        
        # Rebuild system prompt now that parent agent is available
        # Only rebuild if no explicit system_prompt was provided in overrides
        if 'system_prompt' not in overrides:
            config.system_prompt = config._build_system_prompt()
        
        return config
    
    def to_agent_kwargs(self, exclude_subagent_params: bool = True) -> Dict[str, Any]:
        """
        Convert configuration to kwargs suitable for TinyAgent/TinyCodeAgent constructor.
        
        This method transforms the SubagentConfig into a dictionary that can be used
        directly as keyword arguments for creating TinyAgent or TinyCodeAgent instances.
        
        Args:
            exclude_subagent_params: Whether to exclude subagent-specific parameters
                                   that are not valid for agent constructors
                                   
        Returns:
            Dictionary of parameters suitable for agent constructor
            
        Examples:
            # Get all parameters for agent creation
            agent_kwargs = config.to_agent_kwargs()
            agent = TinyCodeAgent(**agent_kwargs)
            
            # Include subagent params for custom factories
            all_kwargs = config.to_agent_kwargs(exclude_subagent_params=False)
            agent = custom_factory(**all_kwargs)
        """
        import copy
        
        # Parameters that are specific to subagents and should be excluded by default
        subagent_only_params = {
            'max_turns', 'timeout', 'inherit_parent_hooks', 'working_directory', 
            'environment_variables', 'callbacks', 'additional_params', '_parent_agent'
        }
        
        # Parameters that need deep copying to avoid mutation
        deep_copy_params = {
            'model_kwargs', 'provider_config', 'retry_config', 'additional_params'
        }
        
        # Get all non-None parameters
        kwargs = {}
        for field_name in self.__dataclass_fields__.keys():
            value = getattr(self, field_name)
            
            # Skip None values and subagent-only params if requested
            if value is None:
                continue
            # Always skip _parent_agent as it's internal and never should be passed to constructors
            if field_name == '_parent_agent':
                continue
            if exclude_subagent_params and field_name in subagent_only_params:
                continue
            
            # Handle special cases
            if field_name == 'callbacks' and not value:
                continue  # Skip empty callback list
            
            # Deep copy parameters that might be mutated by agents to prevent cross-agent pollution
            if field_name in deep_copy_params and value:
                kwargs[field_name] = copy.deepcopy(value)
            else:
                kwargs[field_name] = value
        
        # Add additional_params only if not excluding subagent params
        if not exclude_subagent_params:
            # Deep copy additional_params to prevent mutation
            if self.additional_params:
                kwargs.update(copy.deepcopy(self.additional_params))
        
        return kwargs
    
    def create_logger(self, name: str) -> logging.Logger:
        """
        Create a logger for the subagent using the configured LoggingManager.
        
        Args:
            name: Name for the logger (typically subagent name)
            
        Returns:
            Configured logger instance
            
        Examples:
            logger = config.create_logger("my_subagent")
            logger.info("Subagent starting...")
        """
        if self.log_manager:
            return self.log_manager.get_logger(f"subagent.{name}")
        else:
            return logging.getLogger(f"subagent.{name}")
    
    def copy_with_overrides(self, **overrides) -> 'SubagentConfig':
        """
        Create a copy of this configuration with specific overrides.
        
        Args:
            **overrides: Parameters to override in the copy
            
        Returns:
            New SubagentConfig instance with overrides applied
            
        Examples:
            # Create a copy with different model  
            new_config = config.copy_with_overrides(
                model="claude-3-sonnet",
                temperature=0.3
            )
        """
        # Convert current config to dict
        current_params = self.to_agent_kwargs(exclude_subagent_params=False)
        
        # Apply overrides
        current_params.update(overrides)
        
        return self.__class__(**current_params)
    
    @classmethod
    def for_research(cls, **kwargs) -> 'SubagentConfig':
        """Create a configuration optimized for research tasks."""
        defaults = {
            'model': 'gpt-5-mini',
            'max_turns': 15,
            'enable_python_tool': False,
            'enable_shell_tool': False,
            'system_prompt': (
                "You are a research assistant specialized in gathering, analyzing, and synthesizing information. "
                "Your task is to conduct thorough research on the given topic and provide comprehensive, "
                "well-structured findings. Focus on accuracy, relevance, and clarity in your research."
            ),
            'temperature': 0.1,
        }
        defaults.update(kwargs)
        return cls(**defaults)
    
    @classmethod
    def for_coding(cls, **kwargs) -> 'SubagentConfig':
        """Create a configuration optimized for coding tasks."""
        defaults = {
            'model': 'gpt-5-mini',
            'max_turns': 20,
            'enable_python_tool': True,
            'enable_shell_tool': True,
            'enable_file_tools': True,
            'system_prompt': (
                "You are a software development assistant specialized in writing, reviewing, and debugging code. "
                "You have access to Python execution and shell commands to test and validate your solutions. "
                "Write clean, efficient, and well-documented code. Test your implementations thoroughly."
            ),
            'temperature': 1.0,
        }
        defaults.update(kwargs)
        return cls(**defaults)
    
    @classmethod
    def for_analysis(cls, **kwargs) -> 'SubagentConfig':
        """Create a configuration optimized for data analysis tasks."""
        defaults = {
            'model': 'gpt-5-mini',
            'max_turns': 25,
            'enable_python_tool': True,
            'enable_shell_tool': False,
            'enable_file_tools': True,
            'system_prompt': (
                "You are a data analysis specialist focused on examining, interpreting, and deriving insights from data. "
                "Use Python tools to perform calculations, create visualizations, and conduct statistical analysis. "
                "Provide clear explanations of your analytical approach and findings."
            ),
            'temperature': 1.0,
        }
        defaults.update(kwargs)
        return cls(**defaults)
    
    @classmethod
    def for_writing(cls, **kwargs) -> 'SubagentConfig':
        """Create a configuration optimized for writing and content creation tasks."""
        defaults = {
            'model': 'gpt-5-mini',
            'max_turns': 10,
            'enable_python_tool': False,
            'enable_shell_tool': False,
            'system_prompt': (
                "You are a professional writer and content creator. Your expertise includes crafting "
                "clear, engaging, and well-structured written content across various formats and styles. "
                "Focus on clarity, coherence, and meeting the specific requirements of the writing task."
            ),
            'temperature': 1.0,
        }
        defaults.update(kwargs)
        return cls(**defaults)
    
    @classmethod
    def for_planning(cls, **kwargs) -> 'SubagentConfig':
        """Create a configuration optimized for planning and strategy tasks."""
        defaults = {
            'model': 'gpt-5-mini',
            'max_turns': 12,
            'enable_python_tool': False,
            'enable_shell_tool': False,
            'system_prompt': (
                "You are a strategic planning specialist focused on breaking down complex problems "
                "into actionable plans. Create detailed, step-by-step approaches with clear timelines, "
                "dependencies, and success criteria. Consider risks, resources, and alternative approaches."
            ),
            'temperature': 1.0,
        }
        defaults.update(kwargs)
        return cls(**defaults)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            'model': self.model,
            'api_key': self.api_key,
            'temperature': self.temperature,
            'max_turns': self.max_turns,
            'timeout': self.timeout,
            'enable_python_tool': self.enable_python_tool,
            'enable_shell_tool': self.enable_shell_tool,
            'enable_file_tools': self.enable_file_tools,
            'local_execution': self.local_execution,
            'default_workdir': self.default_workdir,
            'provider': self.provider,
            'provider_config': self.provider_config,
            'tools': self.tools,
            'inherit_parent_hooks': self.inherit_parent_hooks,
            'working_directory': self.working_directory,
            'environment_variables': self.environment_variables,
            'system_prompt': self.system_prompt,
            'retry_config': self.retry_config,
            'parallel_tool_calls': self.parallel_tool_calls,
            'model_kwargs': self.model_kwargs,
            'additional_params': self.additional_params,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SubagentConfig':
        """Create configuration from dictionary."""
        return cls(**data)