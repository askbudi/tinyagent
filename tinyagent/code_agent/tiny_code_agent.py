import traceback
import os
import json
import shlex
from textwrap import dedent
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from tinyagent import TinyAgent, tool
from tinyagent.hooks.logging_manager import LoggingManager
from tinyagent.hooks.rich_code_ui_callback import RichCodeUICallback
# Conditional import for Jupyter callback - only import when needed
try:
    from tinyagent.hooks.jupyter_notebook_callback import JupyterNotebookCallback, OptimizedJupyterNotebookCallback
    JUPYTER_CALLBACKS_AVAILABLE = True
except ImportError:
    JUPYTER_CALLBACKS_AVAILABLE = False
    JupyterNotebookCallback = None
    OptimizedJupyterNotebookCallback = None
from .providers.base import CodeExecutionProvider
from .providers.modal_provider import ModalProvider
from .providers.seatbelt_provider import SeatbeltProvider
from .providers.bubblewrap_provider import BubblewrapProvider
from .providers.docker_provider import DockerProvider
from .helper import translate_tool_for_code_agent, load_template, render_system_prompt, prompt_code_example, prompt_qwen_helper
from .utils import truncate_output, format_truncation_message, get_system_info, get_helpful_error_tip, detect_system_capabilities, generate_dynamic_bash_description
from .tools.file_tools import read_file, write_file, update_file, glob_tool, grep_tool
from .shell_validator import SimpleShellValidator, create_validator_from_provider_config
import datetime


def detect_best_provider(local_execution: bool = False) -> str:
    """
    Automatically detect the best available provider for the current platform.
    
    Args:
        local_execution: If True, only consider local providers (seatbelt/bubblewrap/docker)
        
    Returns:
        String name of the best available provider
        
    Raises:
        RuntimeError: If no suitable provider is available
    """
    if local_execution:
        # For local execution, check for platform-specific sandboxing providers first
        if SeatbeltProvider.is_supported():
            return "seatbelt"
        elif BubblewrapProvider.is_supported():
            return "bubblewrap"
        elif DockerProvider.is_supported():
            return "docker"
        else:
            raise RuntimeError("No local provider available. Install Docker or platform-specific sandbox (macOS: sandbox-exec, Linux: bubblewrap).")
    else:
        # For remote execution, Modal is the primary option, but Docker can be a fallback
        if DockerProvider.is_supported():
            # For non-local execution, we can still use Docker as it's universal
            return "docker"
        else:
            return "modal"


def auto_select_provider(
    provider: Optional[str] = None, 
    local_execution: bool = False,
    allow_fallback: bool = True
) -> str:
    """
    Auto-select provider with fallback logic.
    
    Args:
        provider: Explicitly requested provider name, or None for auto-detection
        local_execution: Whether local execution is required
        allow_fallback: Whether to allow fallback to other providers
        
    Returns:
        String name of the selected provider
        
    Raises:
        RuntimeError: If the requested provider is not available and no fallback is possible
    """
    # If a specific provider is requested, try to use it
    if provider:
        provider = provider.lower()
        
        # Validate the requested provider
        if provider == "seatbelt":
            if SeatbeltProvider.is_supported():
                return provider
            elif allow_fallback:
                if local_execution and BubblewrapProvider.is_supported():
                    return "bubblewrap"
                elif local_execution and DockerProvider.is_supported():
                    return "docker"
                elif not local_execution and DockerProvider.is_supported():
                    return "docker"
                elif not local_execution:
                    return "modal"
                else:
                    raise RuntimeError("Seatbelt provider requested but not available. No suitable fallback found.")
            else:
                raise RuntimeError("Seatbelt provider is not supported on this system. It requires macOS with sandbox-exec.")
        
        elif provider == "bubblewrap":
            if BubblewrapProvider.is_supported():
                return provider
            elif allow_fallback:
                if local_execution and SeatbeltProvider.is_supported():
                    return "seatbelt"
                elif local_execution and DockerProvider.is_supported():
                    return "docker"
                elif not local_execution and DockerProvider.is_supported():
                    return "docker"
                elif not local_execution:
                    return "modal"
                else:
                    raise RuntimeError("Bubblewrap provider requested but not available. No suitable fallback found.")
            else:
                raise RuntimeError("Bubblewrap provider is not supported on this system. It requires Linux with bubblewrap.")
        
        elif provider == "docker":
            if DockerProvider.is_supported():
                return provider
            elif allow_fallback:
                if local_execution and SeatbeltProvider.is_supported():
                    return "seatbelt"
                elif local_execution and BubblewrapProvider.is_supported():
                    return "bubblewrap"
                elif not local_execution:
                    return "modal"
                else:
                    raise RuntimeError("Docker provider requested but not available. No suitable fallback found.")
            else:
                raise RuntimeError("Docker provider is not supported on this system. Docker must be installed and running.")
        
        elif provider == "modal":
            return provider  # Modal doesn't have platform requirements
        
        else:
            raise ValueError(f"Unknown provider: {provider}. Supported providers are: modal, seatbelt, bubblewrap, docker")
    
    # No specific provider requested, use auto-detection
    return detect_best_provider(local_execution)


DEFAULT_SUMMARY_SYSTEM_PROMPT = (
    "You are an expert coding assistant. Your goal is to generate a concise, structured summary "
    "of the conversation below that captures all essential information needed to continue "
    "development after context replacement. Include tasks performed, code areas modified or "
    "reviewed, key decisions or assumptions, test results or errors, and outstanding tasks or next steps."
    
)

class TinyCodeAgent(TinyAgent):
    """
    A TinyAgent specialized for code execution tasks with cross-platform provider support.
    
    This class provides a high-level interface for creating agents that can execute
    Python code using various providers with automatic platform detection:
    - Modal: Remote execution in cloud environments (platform-agnostic)
    - SeatbeltProvider: Local sandboxed execution on macOS using sandbox-exec
    - BubblewrapProvider: Local sandboxed execution on Linux using bubblewrap
    
    Features include:
    - Cross-platform automatic provider selection
    - Code execution in sandboxed environments
    - Shell command execution with safety checks
    - Environment variable management (SeatbeltProvider/BubblewrapProvider)
    - File system access controls
    - Memory management and conversation summarization
    - Git checkpoint automation
    - Output truncation controls
    - Graceful fallback between providers
    """
    
    def __init__(
        self,
        model: str = "gpt-5-mini",
        api_key: Optional[str] = None,
        log_manager: Optional[LoggingManager] = None,
        provider: Optional[str] = None,
        auto_provider_selection: bool = True,
        provider_fallback: bool = True,
        tools: Optional[List[Any]] = None,
        code_tools: Optional[List[Any]] = None,
        authorized_imports: Optional[List[str]] = None,
        system_prompt_template: Optional[str] = None,
        system_prompt: Optional[str] = None,
        provider_config: Optional[Dict[str, Any]] = None,
        user_variables: Optional[Dict[str, Any]] = None,
        pip_packages: Optional[List[str]] = None,
        local_execution: bool = False,
        check_string_obfuscation: bool = True,
        default_workdir: Optional[str] = None,
        summary_config: Optional[Dict[str, Any]] = None,
        ui: Optional[str] = None,
        truncation_config: Optional[Dict[str, Any]] = None,
        auto_git_checkpoint: bool = False,
        enable_python_tool: bool = True,
        enable_shell_tool: bool = True,
        enable_file_tools: bool = True,
        enable_todo_write: bool = True,
        debug_mode: bool = False,
        # Custom instruction parameters
        custom_instructions: Optional[Union[str, Path]] = None,
        enable_custom_instructions: bool = True,
        custom_instruction_config: Optional[Dict[str, Any]] = None,
        custom_instruction_file: str = "AGENTS.md",
        custom_instruction_directory: str = ".",
        custom_instruction_placeholder: str = "<user_specified_instruction></user_specified_instruction>",
        custom_instruction_subagent_inheritance: bool = True,
        **agent_kwargs
    ):
        """
        Initialize TinyCodeAgent.
        
        Args:
            model: The language model to use
            api_key: API key for the model
            log_manager: Optional logging manager
            provider: Code execution provider ("modal", "seatbelt", "bubblewrap", or None for auto-detection)
            auto_provider_selection: If True, automatically select the best available provider when provider is None
            provider_fallback: If True, allow fallback to other providers if the requested one is not available
            tools: List of tools available to the LLM (regular tools)
            code_tools: List of tools available in the Python execution environment
            authorized_imports: List of authorized Python imports
            system_prompt_template: Path to custom system prompt template
            provider_config: Configuration for the code execution provider
            user_variables: Dictionary of variables to make available in Python environment
            pip_packages: List of additional Python packages to install in Modal environment
            local_execution: If True, uses Modal's .local() method for local execution. 
                                If False, uses Modal's .remote() method for cloud execution (default: False)
            check_string_obfuscation: If True (default), check for string obfuscation techniques. Set to False to allow 
                                legitimate use of base64 encoding and other string manipulations.
            default_workdir: Default working directory for shell commands. If None, the current working directory is used.
            summary_config: Optional configuration for generating conversation summaries
            ui: The user interface callback to use ('rich', 'jupyter', or None).
            truncation_config: Configuration for output truncation (max_tokens, max_lines)
            auto_git_checkpoint: If True, automatically create git checkpoints after each successful shell command
            enable_python_tool: If True (default), enable the run_python tool for Python code execution
            enable_shell_tool: If True (default), enable the bash tool for shell command execution
            enable_file_tools: If True (default), enable sandbox-constrained file tools (read_file, write_file, update_file, glob_tool, grep_tool)
            enable_todo_write: If True (default), enable the TodoWrite tool for task management
            debug_mode: If True, print executed Python code for debugging purposes (default: False).
                       Can also be enabled by setting TINYAGENT_DEBUG_MODE environment variable to '1', 'true', 'yes', or 'on'
            custom_instructions: Custom instructions as string content or file path. Can also auto-detect AGENTS.md.
            enable_custom_instructions: Whether to enable custom instruction processing. Default is True.
            custom_instruction_config: Configuration for custom instruction loader.
            custom_instruction_file: Custom filename to search for (default: "AGENTS.md").
            custom_instruction_directory: Directory to search for files (default: current working directory).
            custom_instruction_placeholder: Placeholder text to replace in system prompt (default: "<user_specified_instruction></user_specified_instruction>").
            custom_instruction_subagent_inheritance: Whether subagents inherit instructions (default: True).
            **agent_kwargs: Additional arguments passed to TinyAgent
            
        Provider Config Options:
            For SeatbeltProvider:
                - seatbelt_profile: String containing seatbelt profile rules
                - seatbelt_profile_path: Path to a file containing seatbelt profile rules
                - python_env_path: Path to the Python environment to use
                - bypass_shell_safety: If True, bypass shell command safety checks (default: True for seatbelt)
                - additional_safe_shell_commands: Additional shell commands to consider safe
                - additional_safe_control_operators: Additional shell control operators to consider safe
                - additional_read_dirs: List of additional directories to allow read access to
                - additional_write_dirs: List of additional directories to allow write access to
                - environment_variables: Dictionary of environment variables to make available in the sandbox
            
            For BubblewrapProvider:
                - bubblewrap_profile: String containing bubblewrap profile rules (unused, kept for compatibility)
                - bubblewrap_profile_path: Path to a file containing bubblewrap profile rules (unused, kept for compatibility)
                - python_env_path: Path to the Python environment to use
                - bypass_shell_safety: If True, bypass shell command safety checks (default: True for bubblewrap)
                - additional_safe_shell_commands: Additional shell commands to consider safe
                - additional_safe_control_operators: Additional shell control operators to consider safe
                - additional_read_dirs: List of additional directories to allow read access to
                - additional_write_dirs: List of additional directories to allow write access to
                - environment_variables: Dictionary of environment variables to make available in the sandbox
            
            For ModalProvider:
                - pip_packages: List of additional Python packages to install
                - authorized_imports: List of authorized Python imports
                - bypass_shell_safety: If True, bypass shell command safety checks (default: False for modal)
                - additional_safe_shell_commands: Additional shell commands to consider safe
                - additional_safe_control_operators: Additional shell control operators to consider safe
                
        Truncation Config Options:
            - max_tokens: Maximum number of tokens to keep in output (default: 3000)
            - max_lines: Maximum number of lines to keep in output (default: 250)
            - enabled: Whether truncation is enabled (default: True)
        """
        self.model = model
        self.api_key = api_key
        self.log_manager = log_manager
        self.tools = tools or []  # LLM tools
        self.code_tools = code_tools or []  # Python environment tools
        self.authorized_imports = authorized_imports or ["tinyagent", "gradio", "requests", "asyncio"]
        self.provider_config = provider_config or {}
        self.user_variables = user_variables or {}
        self.pip_packages = pip_packages or []
        self.local_execution = local_execution
        self.auto_provider_selection = auto_provider_selection
        self.provider_fallback = provider_fallback
        
        # Auto-select provider if enabled
        if auto_provider_selection and provider is None:
            self.provider = auto_select_provider(
                provider=None,
                local_execution=local_execution,
                allow_fallback=provider_fallback
            )
        elif provider is not None:
            self.provider = auto_select_provider(
                provider=provider,
                local_execution=local_execution,
                allow_fallback=provider_fallback
            )
        else:
            # Fallback to modal if auto-selection is disabled and no provider specified
            self.provider = "modal"
        self.check_string_obfuscation = check_string_obfuscation
        self.default_workdir = default_workdir or os.getcwd()  # Default to current working directory if not specified
        self.auto_git_checkpoint = auto_git_checkpoint  # Enable/disable automatic git checkpoints
        
        # Store custom instruction parameters
        self.custom_instructions = custom_instructions
        self.enable_custom_instructions = enable_custom_instructions
        
        # Build custom instruction config from individual parameters
        self.custom_instruction_config = custom_instruction_config or {}
        self.custom_instruction_config.update({
            "auto_detect_agents_md": True,  # Enable auto-detection
            "custom_filename": custom_instruction_file,
            "execution_directory": custom_instruction_directory,
            "inherit_to_subagents": custom_instruction_subagent_inheritance
        })
        
        # Store individual parameters for access
        self.custom_instruction_file = custom_instruction_file
        self.custom_instruction_directory = custom_instruction_directory
        self.custom_instruction_placeholder = custom_instruction_placeholder
        self.custom_instruction_subagent_inheritance = custom_instruction_subagent_inheritance
        
        # Store tool enablement flags
        self._python_tool_enabled = enable_python_tool
        self._shell_tool_enabled = enable_shell_tool
        self._file_tools_enabled = enable_file_tools
        self._todo_write_enabled = enable_todo_write
        # Check environment variable first, then parameter
        env_debug = os.environ.get('TINYAGENT_DEBUG_MODE', '').lower() in ('1', 'true', 'yes', 'on')
        self._debug_mode = env_debug or debug_mode
        
        # Set up truncation configuration with defaults
        default_truncation = {
            "max_tokens": 3000,
            "max_lines": 250,
            "enabled": True
        }
        self.truncation_config = {**default_truncation, **(truncation_config or {})}
        
        # Create the code execution provider
        self.code_provider = self._create_provider(self.provider, self.provider_config)
        
        # Create shell validator with provider-specific configuration
        provider_config_with_type = self.provider_config.copy()
        provider_config_with_type['provider_type'] = self.provider
        self.shell_validator = create_validator_from_provider_config(provider_config_with_type)
        
        # Detect system capabilities for enhanced bash tool functionality
        self.system_capabilities = detect_system_capabilities()
        
        # Set user variables in the provider
        if self.user_variables:
            self.code_provider.set_user_variables(self.user_variables)
        
        # Build system prompt
        self.static_system_prompt= system_prompt
        self.system_prompt =  self._build_system_prompt(system_prompt_template)
        
        
        self.summary_config = summary_config or {}

        # Initialize the parent TinyAgent with the built system prompt
        # Note: We handle custom instructions in _build_system_prompt, so disable them in parent
        super().__init__(
            model=model,
            api_key=api_key,
            system_prompt=self.system_prompt,
            logger=log_manager.get_logger('tinyagent.tiny_agent') if log_manager else None,
            summary_config=summary_config,
            enable_todo_write=enable_todo_write,
            enable_custom_instruction=False,  # We handle custom instructions in _build_system_prompt
            **agent_kwargs
        )
        
        # Add the code execution tools
        self._setup_code_execution_tools()
        
        # Add LLM tools (not code tools - those go to the provider)
        if self.tools:
            self.add_tools(self.tools)

        # Add the selected UI callback
        if ui:
            self.add_ui_callback(ui)
    
    def _create_provider(self, provider_type: str, config: Dict[str, Any]) -> CodeExecutionProvider:
        """Create a code execution provider based on the specified type."""
        if provider_type.lower() == "modal":
            # Merge pip_packages from both sources (direct parameter and provider_config)
            config_pip_packages = config.get("pip_packages", [])
            final_pip_packages = list(set(self.pip_packages + config_pip_packages))
            
            # Merge authorized_imports from both sources (direct parameter and provider_config)
            config_authorized_imports = config.get("authorized_imports", [])
            final_authorized_imports = list(set(self.authorized_imports + config_authorized_imports))
            
            # Add file operation imports if file tools are enabled
            if self._file_tools_enabled:
                file_imports = ["os", "pathlib", "Path", "mimetypes", "re", "glob"]
                final_authorized_imports.extend(file_imports)
                final_authorized_imports = list(set(final_authorized_imports))  # Remove duplicates
            
            # Merge authorized_functions from both sources and add file operations if file tools are enabled
            config_authorized_functions = config.get("authorized_functions", [])
            final_authorized_functions = list(set(config_authorized_functions))
            
            # Add file operation functions if file tools are enabled
            if self._file_tools_enabled:
                file_functions = ["open", "Path.mkdir", "Path.exists", "Path.parent", "os.path.exists", "os.path.join", "os.listdir", "os.walk"]
                final_authorized_functions.extend(file_functions)
                final_authorized_functions = list(set(final_authorized_functions))  # Remove duplicates
            
            final_config = config.copy()
            final_config["pip_packages"] = final_pip_packages
            final_config["authorized_imports"] = final_authorized_imports
            final_config["authorized_functions"] = final_authorized_functions
            final_config["check_string_obfuscation"] = self.check_string_obfuscation
            
            # Shell safety configuration (default to False for Modal)
            bypass_shell_safety = config.get("bypass_shell_safety", False)
            additional_safe_shell_commands = config.get("additional_safe_shell_commands", None)
            additional_safe_control_operators = config.get("additional_safe_control_operators", None)
            
            return ModalProvider(
                log_manager=self.log_manager,
                code_tools=self.code_tools,
                local_execution=self.local_execution,
                bypass_shell_safety=bypass_shell_safety,
                additional_safe_shell_commands=additional_safe_shell_commands,
                additional_safe_control_operators=additional_safe_control_operators,
                **final_config
            )
        elif provider_type.lower() == "seatbelt":
            # Check if seatbelt is supported on this system
            if not SeatbeltProvider.is_supported():
                raise ValueError("Seatbelt provider is not supported on this system. It requires macOS with sandbox-exec.")
            
            # Seatbelt only works with local execution
            if not self.local_execution:
                raise ValueError("Seatbelt provider requires local execution mode. Please set local_execution=True.")
            
            # Create a copy of the config without the parameters we'll pass directly
            filtered_config = config.copy()
            for key in ['seatbelt_profile', 'seatbelt_profile_path', 'python_env_path', 
                        'bypass_shell_safety', 'additional_safe_shell_commands', 
                        'additional_safe_control_operators', 'additional_read_dirs',
                        'additional_write_dirs', 'environment_variables']:
                if key in filtered_config:
                    filtered_config.pop(key)
            
            # Get seatbelt profile configuration
            seatbelt_profile = config.get("seatbelt_profile", None)
            seatbelt_profile_path = config.get("seatbelt_profile_path", None)
            python_env_path = config.get("python_env_path", None)
            
            # Shell safety configuration (default to True for Seatbelt)
            bypass_shell_safety = config.get("bypass_shell_safety", True)
            additional_safe_shell_commands = config.get("additional_safe_shell_commands", None)
            additional_safe_control_operators = config.get("additional_safe_control_operators", None)
            
            # Additional directory access configuration
            additional_read_dirs = config.get("additional_read_dirs", None)
            additional_write_dirs = config.get("additional_write_dirs", None)
            
            # Environment variables to make available in the sandbox
            environment_variables = config.get("environment_variables", {})
            
            # Merge authorized_imports from both sources and add file operations if file tools are enabled
            config_authorized_imports = config.get("authorized_imports", [])
            final_authorized_imports = list(set(config_authorized_imports))
            
            # Add file operation imports if file tools are enabled
            if self._file_tools_enabled:
                file_imports = ["os", "pathlib", "Path", "mimetypes", "re", "glob"]
                final_authorized_imports.extend(file_imports)
                final_authorized_imports = list(set(final_authorized_imports))  # Remove duplicates
            
            # Update filtered_config with authorized_imports
            filtered_config["authorized_imports"] = final_authorized_imports
            
            # Merge authorized_functions from both sources and add file operations if file tools are enabled
            config_authorized_functions = config.get("authorized_functions", [])
            final_authorized_functions = list(set(config_authorized_functions))
            
            # Add file operation functions if file tools are enabled
            if self._file_tools_enabled:
                file_functions = ["open", "Path.mkdir", "Path.exists", "Path.parent", "os.path.exists", "os.path.join", "os.listdir", "os.walk"]
                final_authorized_functions.extend(file_functions)
                final_authorized_functions = list(set(final_authorized_functions))  # Remove duplicates
            
            # Update filtered_config with authorized_functions
            filtered_config["authorized_functions"] = final_authorized_functions
            
            # Create the seatbelt provider
            return SeatbeltProvider(
                log_manager=self.log_manager,
                code_tools=self.code_tools,
                seatbelt_profile=seatbelt_profile,
                seatbelt_profile_path=seatbelt_profile_path,
                python_env_path=python_env_path,
                bypass_shell_safety=bypass_shell_safety,
                additional_safe_shell_commands=additional_safe_shell_commands,
                additional_safe_control_operators=additional_safe_control_operators,
                additional_read_dirs=additional_read_dirs,
                additional_write_dirs=additional_write_dirs,
                environment_variables=environment_variables,
                **filtered_config
            )
        elif provider_type.lower() == "bubblewrap":
            # Check if bubblewrap is supported on this system
            if not BubblewrapProvider.is_supported():
                raise ValueError("Bubblewrap provider is not supported on this system. It requires Linux with bubblewrap.")
            
            # Bubblewrap only works with local execution
            if not self.local_execution:
                raise ValueError("Bubblewrap provider requires local execution mode. Please set local_execution=True.")
            
            # Create a copy of the config without the parameters we'll pass directly
            filtered_config = config.copy()
            for key in ['bubblewrap_profile', 'bubblewrap_profile_path', 'python_env_path', 
                        'bypass_shell_safety', 'additional_safe_shell_commands', 
                        'additional_safe_control_operators', 'additional_read_dirs',
                        'additional_write_dirs', 'environment_variables']:
                if key in filtered_config:
                    filtered_config.pop(key)
            
            # Get bubblewrap profile configuration
            bubblewrap_profile = config.get("bubblewrap_profile", None)
            bubblewrap_profile_path = config.get("bubblewrap_profile_path", None)
            python_env_path = config.get("python_env_path", None)
            
            # Shell safety configuration (default to True for Bubblewrap)
            bypass_shell_safety = config.get("bypass_shell_safety", True)
            additional_safe_shell_commands = config.get("additional_safe_shell_commands", None)
            additional_safe_control_operators = config.get("additional_safe_control_operators", None)
            
            # Additional directory access configuration
            additional_read_dirs = config.get("additional_read_dirs", None)
            additional_write_dirs = config.get("additional_write_dirs", None)
            
            # Environment variables to make available in the sandbox
            environment_variables = config.get("environment_variables", {})
            
            # Merge authorized_imports from both sources and add file operations if file tools are enabled
            config_authorized_imports = config.get("authorized_imports", [])
            final_authorized_imports = list(set(config_authorized_imports))
            
            # Add file operation imports if file tools are enabled
            if self._file_tools_enabled:
                file_imports = ["os", "pathlib", "Path", "mimetypes", "re", "glob"]
                final_authorized_imports.extend(file_imports)
                final_authorized_imports = list(set(final_authorized_imports))  # Remove duplicates
            
            # Update filtered_config with authorized_imports
            filtered_config["authorized_imports"] = final_authorized_imports
            
            # Merge authorized_functions from both sources and add file operations if file tools are enabled
            config_authorized_functions = config.get("authorized_functions", [])
            final_authorized_functions = list(set(config_authorized_functions))
            
            # Add file operation functions if file tools are enabled
            if self._file_tools_enabled:
                file_functions = ["open", "Path.mkdir", "Path.exists", "Path.parent", "os.path.exists", "os.path.join", "os.listdir", "os.walk"]
                final_authorized_functions.extend(file_functions)
                final_authorized_functions = list(set(final_authorized_functions))  # Remove duplicates
            
            # Update filtered_config with authorized_functions
            filtered_config["authorized_functions"] = final_authorized_functions
            
            # Create the bubblewrap provider
            return BubblewrapProvider(
                log_manager=self.log_manager,
                code_tools=self.code_tools,
                bubblewrap_profile=bubblewrap_profile,
                bubblewrap_profile_path=bubblewrap_profile_path,
                python_env_path=python_env_path,
                bypass_shell_safety=bypass_shell_safety,
                additional_safe_shell_commands=additional_safe_shell_commands,
                additional_safe_control_operators=additional_safe_control_operators,
                additional_read_dirs=additional_read_dirs,
                additional_write_dirs=additional_write_dirs,
                environment_variables=environment_variables,
                **filtered_config
            )
        elif provider_type.lower() == "docker":
            # Check if Docker is supported on this system
            if not DockerProvider.is_supported():
                raise ValueError("Docker provider is not supported on this system. Docker must be installed and running.")
            
            # Create a copy of the config without the parameters we'll pass directly
            filtered_config = config.copy()
            for key in ['docker_image', 'python_env_path', 'bypass_shell_safety', 
                        'additional_safe_shell_commands', 'additional_safe_control_operators', 
                        'additional_read_dirs', 'additional_write_dirs', 'environment_variables',
                        'container_name_prefix', 'enable_network', 'memory_limit', 'cpu_limit',
                        'timeout', 'auto_pull_image', 'volume_mount_path']:
                if key in filtered_config:
                    filtered_config.pop(key)
            
            # Get Docker-specific configuration
            docker_image = config.get("docker_image", "tinyagent-runtime:latest")
            python_env_path = config.get("python_env_path", None)  # Not used in Docker, kept for compatibility
            
            # Shell safety configuration (default to True for Docker)
            bypass_shell_safety = config.get("bypass_shell_safety", True)
            additional_safe_shell_commands = config.get("additional_safe_shell_commands", None)
            additional_safe_control_operators = config.get("additional_safe_control_operators", None)
            
            # Additional directory access configuration
            additional_read_dirs = config.get("additional_read_dirs", None)
            additional_write_dirs = config.get("additional_write_dirs", None)
            
            # Environment variables to make available in the container
            environment_variables = config.get("environment_variables", {})
            
            # Docker-specific configuration
            container_name_prefix = config.get("container_name_prefix", "tinyagent")
            enable_network = config.get("enable_network", False)
            memory_limit = config.get("memory_limit", "512m")
            cpu_limit = config.get("cpu_limit", "1.0")
            timeout = config.get("timeout", 300)
            auto_pull_image = config.get("auto_pull_image", True)
            volume_mount_path = config.get("volume_mount_path", "/workspace")
            
            # Merge authorized_imports from both sources and add file operations if file tools are enabled
            config_authorized_imports = config.get("authorized_imports", [])
            final_authorized_imports = list(set(config_authorized_imports))
            
            # Add file operation imports if file tools are enabled
            if self._file_tools_enabled:
                file_imports = ["os", "pathlib", "Path", "mimetypes", "re", "glob"]
                final_authorized_imports.extend(file_imports)
                final_authorized_imports = list(set(final_authorized_imports))  # Remove duplicates
            
            # Update filtered_config with authorized_imports
            filtered_config["authorized_imports"] = final_authorized_imports
            
            # Merge authorized_functions from both sources and add file operations if file tools are enabled
            config_authorized_functions = config.get("authorized_functions", [])
            final_authorized_functions = list(set(config_authorized_functions))
            
            # Add file operation functions if file tools are enabled
            if self._file_tools_enabled:
                file_functions = ["open", "Path.mkdir", "Path.exists", "Path.parent", "os.path.exists", "os.path.join", "os.listdir", "os.walk"]
                final_authorized_functions.extend(file_functions)
                final_authorized_functions = list(set(final_authorized_functions))  # Remove duplicates
            
            # Update filtered_config with authorized_functions
            filtered_config["authorized_functions"] = final_authorized_functions
            
            # Create the Docker provider
            return DockerProvider(
                log_manager=self.log_manager,
                code_tools=self.code_tools,
                docker_image=docker_image,
                python_env_path=python_env_path,
                bypass_shell_safety=bypass_shell_safety,
                additional_safe_shell_commands=additional_safe_shell_commands,
                additional_safe_control_operators=additional_safe_control_operators,
                additional_read_dirs=additional_read_dirs,
                additional_write_dirs=additional_write_dirs,
                environment_variables=environment_variables,
                container_name_prefix=container_name_prefix,
                enable_network=enable_network,
                memory_limit=memory_limit,
                cpu_limit=cpu_limit,
                timeout=timeout,
                auto_pull_image=auto_pull_image,
                volume_mount_path=volume_mount_path,
                **filtered_config
            )
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")            
    
    def _build_system_prompt(self, template_path: Optional[str] = None) -> str:
        """Build the system prompt for the code agent."""
        # Determine the base prompt
        if self.static_system_prompt is not None:
            # Use the provided static system prompt as base
            base_prompt = self.static_system_prompt
        elif template_path is None:
            # Use default template
            template_path = str(Path(__file__).parent.parent / "prompts" / "code_agent.yaml")
            
            # Translate code tools to code agent format
            code_tools_metadata = {}
            for tool in self.code_tools:
                if hasattr(tool, '_tool_metadata'):
                    metadata = translate_tool_for_code_agent(tool)
                    code_tools_metadata[metadata["name"]] = metadata
            
            # Load and render template
            try:
                template_str = load_template(template_path)
                system_prompt = render_system_prompt(
                    template_str, 
                    code_tools_metadata, 
                    {}, 
                    self.authorized_imports
                )
                base_prompt = system_prompt + prompt_code_example + prompt_qwen_helper
            except Exception as e:
                # Fallback to a basic prompt if template loading fails
                traceback.print_exc()
                print(f"Failed to load template from {template_path}: {e}")
                base_prompt = self._get_fallback_prompt()
        else:
            # Use provided template path
            # Translate code tools to code agent format
            code_tools_metadata = {}
            for tool in self.code_tools:
                if hasattr(tool, '_tool_metadata'):
                    metadata = translate_tool_for_code_agent(tool)
                    code_tools_metadata[metadata["name"]] = metadata
            
            # Load and render template
            try:
                template_str = load_template(template_path)
                system_prompt = render_system_prompt(
                    template_str, 
                    code_tools_metadata, 
                    {}, 
                    self.authorized_imports
                )
                base_prompt = system_prompt + prompt_code_example + prompt_qwen_helper
            except Exception as e:
                # Fallback to a basic prompt if template loading fails
                traceback.print_exc()
                print(f"Failed to load template from {template_path}: {e}")
                base_prompt = self._get_fallback_prompt()
        
        # Add user variables information to the prompt
        if self.user_variables:
            variables_info = self._build_variables_prompt()
            base_prompt += "\n\n" + variables_info
        
        # Add environment information if bash tool is enabled
        if self._shell_tool_enabled:
            env_info = self._build_env_prompt()
            base_prompt += "\n\n" + env_info
        
        # Apply custom instructions if enabled
        if self.enable_custom_instructions:
            try:
                from tinyagent.core.custom_instructions import CustomInstructionLoader
                
                # Create loader with configuration
                loader = CustomInstructionLoader(
                    enabled=self.enable_custom_instructions,
                    **self.custom_instruction_config
                )
                
                # Load custom instructions
                loader.load_instructions(self.custom_instructions)
                
                # Apply to system prompt with custom placeholder
                base_prompt = loader.apply_to_system_prompt(
                    base_prompt, 
                    placeholder=self.custom_instruction_placeholder
                )
                
                # Log status
                if loader.get_instructions():
                    if self.log_manager:
                        logger = self.log_manager.get_logger(__name__)
                        logger.info(f"Custom instructions applied from {loader.get_instruction_source()}")
                
            except Exception as e:
                if self.log_manager:
                    logger = self.log_manager.get_logger(__name__)
                    logger.error(f"Failed to apply custom instructions: {e}")
        
        return base_prompt
    
    def _get_fallback_prompt(self) -> str:
        """Get a fallback system prompt if template loading fails."""
        return dedent("""
        You are a helpful AI assistant that can execute Python code to solve problems.
        
        You have access to a run_python tool that can execute Python code in a sandboxed environment.
        Use this tool to solve computational problems, analyze data, or perform any task that requires code execution.
        
        When writing code:
        - Always think step by step about the task
        - Use print() statements to show intermediate results
        - Handle errors gracefully
        - Provide clear explanations of your approach
        
        The user cannot see the direct output of run_python, so use final_answer to show results.
        """)
    
    def _build_variables_prompt(self) -> str:
        """Build the variables section for the system prompt."""
        if not self.user_variables:
            return ""
        
        variables_lines = ["## Available Variables", ""]
        variables_lines.append("The following variables are pre-loaded and available in your Python environment:")
        variables_lines.append("")
        
        for var_name, var_value in self.user_variables.items():
            var_type = type(var_value).__name__
            
            # Try to get a brief description of the variable
            if hasattr(var_value, 'shape') and hasattr(var_value, 'dtype'):
                # Likely numpy array or pandas DataFrame
                if hasattr(var_value, 'columns'):
                    # DataFrame
                    desc = f"DataFrame with shape {var_value.shape} and columns: {list(var_value.columns)}"
                else:
                    # Array
                    desc = f"Array with shape {var_value.shape} and dtype {var_value.dtype}"
            elif isinstance(var_value, (list, tuple)):
                length = len(var_value)
                if length > 0:
                    first_type = type(var_value[0]).__name__
                    desc = f"{var_type} with {length} items (first item type: {first_type})"
                else:
                    desc = f"Empty {var_type}"
            elif isinstance(var_value, dict):
                keys_count = len(var_value)
                if keys_count > 0:
                    sample_keys = list(var_value.keys())[:3]
                    desc = f"Dictionary with {keys_count} keys. Sample keys: {sample_keys}"
                else:
                    desc = "Empty dictionary"
            elif isinstance(var_value, str):
                length = len(var_value)
                preview = var_value[:50] + "..." if length > 50 else var_value
                desc = f"String with {length} characters: '{preview}'"
            else:
                desc = f"{var_type}: {str(var_value)[:100]}"
            
            variables_lines.append(f"- **{var_name}** ({var_type}): {desc}")
        
        variables_lines.extend([
            "",
            "These variables are already loaded and ready to use in your code. You don't need to import or define them.",
            "You can directly reference them by name in your Python code."
        ])
        
        return "\n".join(variables_lines)
    
    def _build_code_tools_prompt(self) -> str:
        """Build the code tools section for the system prompt."""
        if not self.code_tools:
            return ""
        
        code_tools_lines = ["## Available Code Tools", ""]
        code_tools_lines.append("The following code tools are available in your Python environment:")
        code_tools_lines.append("")
        
        for tool in self.code_tools:
            if hasattr(tool, '_tool_metadata'):
                metadata = translate_tool_for_code_agent(tool)
                desc = f"- **{metadata['name']}** ({metadata['type']}): {metadata['description']}"
                code_tools_lines.append(desc)
        
        code_tools_lines.extend([
            "",
            "These tools are already loaded and ready to use in your code. You don't need to import or define them.",
            "You can directly reference them by name in your Python code."
        ])
        
        return "\n".join(code_tools_lines)
    
    def _build_env_prompt(self) -> str:
        """Build the environment section for the system prompt."""
        env_lines = ["<ENV>", ""]
        
        # Add current date
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        env_lines.append(f"Date: {current_date}")
        
        # Add system information
        system_info = get_system_info()
        env_lines.append(f"SystemInfo: {system_info}")
        
        env_lines.append("")
        env_lines.append("</ENV>")
        
        return "\n".join(env_lines)
    
    # Complex validation methods removed - now using SimpleShellValidator
    
    def _setup_code_execution_tools(self):
        """Set up the code execution tools using the code provider."""
        # Clear existing default tools to avoid duplicates
        # Remove existing default tools by name if they exist
        if hasattr(self, 'available_tools'):
            tools_to_remove = []
            for tool_dict in self.available_tools:
                if 'function' in tool_dict and 'name' in tool_dict['function']:
                    if tool_dict['function']['name'] in ['run_python', 'bash']:
                        tools_to_remove.append(tool_dict)
            
            # Remove the tools from available_tools
            for tool_dict in tools_to_remove:
                self.available_tools.remove(tool_dict)
        
        if self._python_tool_enabled:
            @tool(name="run_python", description=dedent("""
            This tool receives Python code and executes it in a sandboxed environment.
            During each intermediate step, you can use 'print()' to save important information.
            These print outputs will appear in the 'Observation:' field for the next step.

            Args:
                code_lines: list[str]: The Python code to execute as a list of strings.
                    Your code should include all necessary steps for successful execution,
                    cover edge cases, and include error handling.
                    Each line should be an independent line of code.

            Returns:
                Status of code execution or error message.
            """))
            async def run_python(code_lines: List[str], timeout: int = 120) -> str:
                """Execute Python code using the configured provider."""
                try:
                    # Before execution, ensure provider has the latest user variables
                    if self.user_variables:
                        self.code_provider.set_user_variables(self.user_variables)
                        
                    result = await self.code_provider.execute_python(code_lines, timeout, debug_mode=self._debug_mode)
                    
                    # After execution, update TinyCodeAgent's user_variables from the provider
                    # This ensures they stay in sync
                    self.user_variables = self.code_provider.get_user_variables()
                    
                    # Apply truncation if enabled
                    if self.truncation_config["enabled"] and "printed_output" in result:
                        truncated_output, is_truncated, original_tokens, original_lines = truncate_output(
                            result["printed_output"],
                            max_tokens=self.truncation_config["max_tokens"],
                            max_lines=self.truncation_config["max_lines"]
                        )
                        
                        if is_truncated:
                            result["printed_output"] = format_truncation_message(
                                truncated_output,
                                is_truncated,
                                original_tokens,
                                original_lines,
                                self.truncation_config["max_lines"],
                                "python_output"
                            )
                    
                    return json.dumps(result)
                except Exception as e:
                    print("!"*100)
                    COLOR = {
                            "RED": "\033[91m",
                            "ENDC": "\033[0m",
                        }
                    print(f"{COLOR['RED']}{str(e)}{COLOR['ENDC']}")
                    print(f"{COLOR['RED']}{traceback.format_exc()}{COLOR['ENDC']}")
                    print("!"*100)
                    
                    # Even after an exception, update user_variables from the provider
                    # This ensures any variables that were successfully created/modified are preserved
                    self.user_variables = self.code_provider.get_user_variables()
                    
                    return json.dumps({"error": f"Error executing code: {str(e)}"})
            
            self.add_tool(run_python)
        
        if self._shell_tool_enabled:
            # Generate dynamic bash tool description based on detected capabilities
            bash_description = generate_dynamic_bash_description(self.system_capabilities)
            
            @tool(name="bash", description=bash_description)
            async def bash(command: str, absolute_workdir: Optional[str] = None, timeout: int = 60) -> str:
                """Execute shell commands via provider with minimal mediation."""
                try:
                    effective_workdir = absolute_workdir or self.default_workdir

                    # Provider enforces safety. Run as bash -c "<command>" to preserve quoting/pipes.
                    final_command: List[str] = ["bash", "-c", command]

                    # Optional lightweight workdir checks
                    if effective_workdir and not os.path.exists(effective_workdir):
                        return json.dumps({
                            "stdout": "",
                            "stderr": f"Working directory does not exist: {effective_workdir}",
                            "exit_code": 1
                        })
                    if effective_workdir and not os.path.isdir(effective_workdir):
                        return json.dumps({
                            "stdout": "",
                            "stderr": f"Path is not a directory: {effective_workdir}",
                            "exit_code": 1
                        })

                    result = await self.code_provider.execute_shell(final_command, timeout, effective_workdir)

                    # If provider reports an error or any stderr output, append helpful tip
                    if result and (
                        result.get("exit_code", 0) != 0 or (result.get("stderr") and result["stderr"].strip())
                    ):
                        try:
                            helpful_tip = get_helpful_error_tip(command, result.get("stderr", ""), self.system_capabilities)
                            result["stderr"] = (result.get("stderr", "") or "") + f"\nTip: {helpful_tip}"
                        except Exception as e:
                            if self.log_manager:
                                self.log_manager.get_logger(__name__).debug(f"Error getting helpful tip: {e}")

                    # Apply truncation if enabled
                    if self.truncation_config["enabled"] and result.get("stdout"):
                        truncated_output, is_truncated, original_tokens, original_lines = truncate_output(
                            result["stdout"],
                            max_tokens=self.truncation_config["max_tokens"],
                            max_lines=self.truncation_config["max_lines"]
                        )
                        if is_truncated:
                            result["stdout"] = format_truncation_message(
                                truncated_output,
                                is_truncated,
                                original_tokens,
                                original_lines,
                                self.truncation_config["max_lines"],
                                "bash_output"
                            )

                    # Auto git checkpoint with a succinct description derived from the command
                    if self.auto_git_checkpoint and result.get("exit_code", 1) == 0:
                        desc = (command[:80] + "…") if len(command) > 80 else command
                        checkpoint_result = await self._create_git_checkpoint(final_command, desc, effective_workdir)
                        if self.log_manager:
                            self.log_manager.get_logger(__name__).info(
                                f"Git checkpoint {effective_workdir} result: {checkpoint_result}"
                            )

                    return json.dumps(result)
                except Exception as e:
                    COLOR = {"RED": "\033[91m", "ENDC": "\033[0m"}
                    print(f"{COLOR['RED']}{str(e)}{COLOR['ENDC']}")
                    print(f"{COLOR['RED']}{traceback.format_exc()}{COLOR['ENDC']}")
                    try:
                        helpful_tip = get_helpful_error_tip(command, str(e), self.system_capabilities)
                    except Exception:
                        helpful_tip = get_system_info()
                    return json.dumps({
                        "stdout": "",
                        "stderr": (f"Error executing shell command: {str(e)}" + (f"\nTip: {helpful_tip}" if helpful_tip else "")),
                        "exit_code": 1
                    })

            self.add_tool(bash)
        
        # Add file tools if enabled
        if self._file_tools_enabled:
            self.add_tool(read_file)
            self.add_tool(write_file)
            self.add_tool(update_file)
            self.add_tool(glob_tool)
            self.add_tool(grep_tool)
    
    async def _create_git_checkpoint(self, command: List[str], description: str, workdir: str) -> Dict[str, Any]:
        """
        Create a git checkpoint after command execution.
        
        Args:
            command: The command that was executed
            description: Description of the command
            workdir: Working directory where the command was executed
            
        Returns:
            Dictionary with stdout and stderr from the git operations
        """
        try:
            # Format the command for the commit message
            cmd_str = " ".join(command)
            
            # Check if there are changes to commit
            git_check_cmd = ["bash", "-c", "if ! git diff-index --quiet HEAD --; then echo 'changes_exist'; else echo 'no_changes'; fi"]
            check_result = await self.code_provider.execute_shell(git_check_cmd, 10, workdir)
            
            # If no changes or check failed, return early
            if check_result.get("exit_code", 1) != 0 or "no_changes" in check_result.get("stdout", ""):
                return {"stdout": "No changes detected, skipping git checkpoint", "stderr": ""}
            
            # Stage all changes
            git_add_cmd = ["git", "add", "-A"]
            add_result = await self.code_provider.execute_shell(git_add_cmd, 30, workdir)
            
            if add_result.get("exit_code", 1) != 0:
                return {
                    "stdout": "",
                    "stderr": f"Failed to stage changes: {add_result.get('stderr', '')}"
                }
            
            # Create commit with command description and timestamp
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            commit_msg = f"Checkpoint: {description} @ {timestamp}\n\nCommand: {cmd_str}"
            git_commit_cmd = ["git", "commit", "-m", commit_msg, "--no-gpg-sign"]
            commit_result = await self.code_provider.execute_shell(git_commit_cmd, 30, workdir)
            
            if commit_result.get("exit_code", 1) != 0:
                return {
                    "stdout": "",
                    "stderr": f"Failed to create commit: {commit_result.get('stderr', '')}"
                }
            
            # Get the first line of the commit message without using split with \n in f-string
            first_line = commit_msg.split("\n")[0]
            return {
                "stdout": f"✓ Git checkpoint created: {first_line}",
                "stderr": ""
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Error creating git checkpoint: {str(e)}"
            }
    
    def set_default_workdir(self, workdir: str, create_if_not_exists: bool = False):
        """
        Set the default working directory for shell commands.
        
        Args:
            workdir: The path to use as the default working directory
            create_if_not_exists: If True, create the directory if it doesn't exist
        
        Raises:
            ValueError: If the directory doesn't exist and create_if_not_exists is False
            OSError: If there's an error creating the directory
        """
        workdir = os.path.expanduser(workdir)  # Expand user directory if needed
        
        if not os.path.exists(workdir):
            if create_if_not_exists:
                try:
                    os.makedirs(workdir, exist_ok=True)
                    print(f"Created directory: {workdir}")
                except OSError as e:
                    raise OSError(f"Failed to create directory {workdir}: {str(e)}")
            else:
                raise ValueError(f"Directory does not exist: {workdir}")
        
        if not os.path.isdir(workdir):
            raise ValueError(f"Path is not a directory: {workdir}")
            
        self.default_workdir = workdir
    
    def get_default_workdir(self) -> str:
        """
        Get the current default working directory for shell commands.
        
        Returns:
            The current default working directory path
        """
        return self.default_workdir
    

    

    

    

    

    

    
    def add_code_tool(self, tool):
        """
        Add a code tool that will be available in the Python execution environment.
        
        Args:
            tool: The tool to add to the code execution environment
        """
        self.code_tools.append(tool)
        # Update the provider with the new code tools
        self.code_provider.set_code_tools(self.code_tools)
        # Rebuild system prompt to include new code tools info
        self.system_prompt = self._build_system_prompt()
        # Update the system prompt in messages
        self._update_system_prompt()
    
    def add_code_tools(self, tools: List[Any]):
        """
        Add multiple code tools that will be available in the Python execution environment.
        
        Args:
            tools: List of tools to add to the code execution environment
        """
        self.code_tools.extend(tools)
        # Update the provider with the new code tools
        self.code_provider.set_code_tools(self.code_tools)
        # Rebuild system prompt to include new code tools info
        self.system_prompt = self._build_system_prompt()
        # Update the system prompt in messages
        self._update_system_prompt()
    
    def remove_code_tool(self, tool_name: str):
        """
        Remove a code tool by name.
        
        Args:
            tool_name: Name of the tool to remove
        """
        self.code_tools = [tool for tool in self.code_tools 
                          if not (hasattr(tool, '_tool_metadata') and 
                                tool._tool_metadata.get('name') == tool_name)]
        # Update the provider
        self.code_provider.set_code_tools(self.code_tools)
        # Rebuild system prompt
        self.system_prompt = self._build_system_prompt()
        # Update the system prompt in messages
        self._update_system_prompt()
    
    def get_code_tools(self) -> List[Any]:
        """
        Get a copy of current code tools.
        
        Returns:
            List of current code tools
        """
        return self.code_tools.copy()
    
    def get_llm_tools(self) -> List[Any]:
        """
        Get a copy of current LLM tools.
        
        Returns:
            List of current LLM tools
        """
        return self.tools.copy()
    
    def set_user_variables(self, variables: Dict[str, Any]):
        """
        Set user variables that will be available in the Python environment.
        
        Args:
            variables: Dictionary of variable name -> value pairs
        """
        self.user_variables = variables.copy()
        self.code_provider.set_user_variables(self.user_variables)
        # Rebuild system prompt to include new variables info
        self.system_prompt = self._build_system_prompt()
        # Update the system prompt in messages
        self._update_system_prompt()
    
    def add_user_variable(self, name: str, value: Any):
        """
        Add a single user variable.
        
        Args:
            name: Variable name
            value: Variable value
        """
        self.user_variables[name] = value
        self.code_provider.set_user_variables(self.user_variables)
        # Rebuild system prompt to include new variables info
        self.system_prompt = self._build_system_prompt()
        # Update the agent's system prompt
        self._update_system_prompt()
    
    def remove_user_variable(self, name: str):
        """
        Remove a user variable.
        
        Args:
            name: Variable name to remove
        """
        if name in self.user_variables:
            del self.user_variables[name]
            self.code_provider.set_user_variables(self.user_variables)
            # Rebuild system prompt
            self.system_prompt = self._build_system_prompt()
            # Update the agent's system prompt
            self._update_system_prompt()
    
    def get_user_variables(self) -> Dict[str, Any]:
        """
        Get a copy of current user variables.
        
        Returns:
            Dictionary of current user variables
        """
        return self.user_variables.copy()
    
    def add_pip_packages(self, packages: List[str]):
        """
        Add additional pip packages to the Modal environment.
        Note: This requires recreating the provider, so it's best to set packages during initialization.
        
        Args:
            packages: List of package names to install
        """
        self.pip_packages.extend(packages)
        self.pip_packages = list(set(self.pip_packages))  # Remove duplicates
        
        # Note: Adding packages after initialization requires recreating the provider
        # This is expensive, so it's better to set packages during initialization
        print("⚠️  Warning: Adding packages after initialization requires recreating the Modal environment.")
        print("   For better performance, set pip_packages during TinyCodeAgent initialization.")
        
        # Recreate the provider with new packages
        self.code_provider = self._create_provider(self.provider, self.provider_config)
        
        # Re-set user variables if they exist
        if self.user_variables:
            self.code_provider.set_user_variables(self.user_variables)
    
    def get_pip_packages(self) -> List[str]:
        """
        Get a copy of current pip packages.
        
        Returns:
            List of pip packages that will be installed in Modal
        """
        return self.pip_packages.copy()
    
    def add_authorized_imports(self, imports: List[str]):
        """
        Add additional authorized imports to the execution environment.
        
        Args:
            imports: List of import names to authorize
        """
        self.authorized_imports.extend(imports)
        self.authorized_imports = list(set(self.authorized_imports))  # Remove duplicates
        
        # Update the provider with the new authorized imports
        # This requires recreating the provider
        print("⚠️  Warning: Adding authorized imports after initialization requires recreating the Modal environment.")
        print("   For better performance, set authorized_imports during TinyCodeAgent initialization.")
        
        # Recreate the provider with new authorized imports
        self.code_provider = self._create_provider(self.provider, self.provider_config)
        
        # Re-set user variables if they exist
        if self.user_variables:
            self.code_provider.set_user_variables(self.user_variables)
        
        # Rebuild system prompt to include new authorized imports
        self.system_prompt = self._build_system_prompt()
        # Update the agent's system prompt
        self._update_system_prompt()
    
    def get_authorized_imports(self) -> List[str]:
        """
        Get a copy of current authorized imports.
        
        Returns:
            List of authorized imports
        """
        return self.authorized_imports.copy()
    
    @classmethod
    def is_seatbelt_supported(cls) -> bool:
        """
        Check if the seatbelt provider is supported on this system.
        
        Returns:
            True if seatbelt is supported (macOS with sandbox-exec), False otherwise
        """
        from .providers.seatbelt_provider import SeatbeltProvider
        return SeatbeltProvider.is_supported()
    
    @classmethod
    def is_bubblewrap_supported(cls) -> bool:
        """
        Check if the bubblewrap provider is supported on this system.
        
        Returns:
            True if bubblewrap is supported (Linux with bubblewrap), False otherwise
        """
        from .providers.bubblewrap_provider import BubblewrapProvider
        return BubblewrapProvider.is_supported()
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        Get a list of all available providers on the current system.
        
        Returns:
            List of available provider names
        """
        providers = ["modal"]  # Modal is always available
        
        if cls.is_seatbelt_supported():
            providers.append("seatbelt")
        
        if cls.is_bubblewrap_supported():
            providers.append("bubblewrap")
        
        return providers
    
    @classmethod
    def get_best_local_provider(cls) -> Optional[str]:
        """
        Get the best available local sandboxing provider for the current platform.
        
        Returns:
            Provider name or None if no local provider is available
        """
        if cls.is_seatbelt_supported():
            return "seatbelt"
        elif cls.is_bubblewrap_supported():
            return "bubblewrap"
        else:
            return None
    
    def remove_authorized_import(self, import_name: str):
        """
        Remove an authorized import.
        
        Args:
            import_name: Import name to remove
        """
        if import_name in self.authorized_imports:
            self.authorized_imports.remove(import_name)
            
            # Update the provider with the new authorized imports
            # This requires recreating the provider
            print("⚠️  Warning: Removing authorized imports after initialization requires recreating the Modal environment.")
            print("   For better performance, set authorized_imports during TinyCodeAgent initialization.")
            
            # Recreate the provider with updated authorized imports
            self.code_provider = self._create_provider(self.provider, self.provider_config)
            
            # Re-set user variables if they exist
            if self.user_variables:
                self.code_provider.set_user_variables(self.user_variables)
            
            # Rebuild system prompt to reflect updated authorized imports
            self.system_prompt = self._build_system_prompt()
            # Update the agent's system prompt
            self._update_system_prompt()
    
    async def close(self):
        """Clean up resources."""
        await self.code_provider.cleanup()
        await super().close()
    

    
 

    def _update_system_prompt(self):
        """Update the system prompt in the messages array."""
        if self.messages and len(self.messages) > 0:
            self.messages[0]["content"] = self.system_prompt
    
    def set_check_string_obfuscation(self, enabled: bool):
        """
        Enable or disable string obfuscation detection.
        
        Args:
            enabled: If True, check for string obfuscation techniques. If False, allow
                    legitimate use of base64 encoding and other string manipulations.
        """
        self.check_string_obfuscation = enabled
        
        # Update the provider with the new setting
        if hasattr(self.code_provider, 'check_string_obfuscation'):
            self.code_provider.check_string_obfuscation = enabled


        


    def add_ui_callback(self, ui_type: str, optimized: bool = True):
        """
        Adds a UI callback to the agent based on the type.
        
        Args:
            ui_type: The type of UI callback ('rich' or 'jupyter')
            optimized: Whether to use the optimized version (default: True for better performance)
        """
        if ui_type == 'rich':
            ui_callback = RichCodeUICallback(
                logger=self.log_manager.get_logger('tinyagent.hooks.rich_code_ui_callback') if self.log_manager else None
            )
            self.add_callback(ui_callback)
        elif ui_type == 'jupyter':
            if not JUPYTER_CALLBACKS_AVAILABLE:
                raise ImportError(
                    "Jupyter notebook callbacks are not available. "
                    "Install the required dependencies with: pip install ipython ipywidgets"
                )
            
            if optimized:
                ui_callback = OptimizedJupyterNotebookCallback(
                    logger=self.log_manager.get_logger('tinyagent.hooks.jupyter_notebook_callback') if self.log_manager else None,
                    max_visible_turns=20,    # Limit visible turns for performance
                    max_content_length=100000,  # Limit total content
                    enable_markdown=True,    # Keep markdown but optimized
                    show_raw_responses=False # Show formatted responses
                )
            else:
                ui_callback = JupyterNotebookCallback(
                    logger=self.log_manager.get_logger('tinyagent.hooks.jupyter_notebook_callback') if self.log_manager else None
                )
            self.add_callback(ui_callback)
        else:
            if self.log_manager:
                self.log_manager.get_logger(__name__).warning(f"Unknown UI type: {ui_type}. No UI callback will be added.")
            else:
                print(f"Warning: Unknown UI type: {ui_type}. No UI callback will be added.")

    def set_truncation_config(self, config: Dict[str, Any]):
        """
        Set the truncation configuration.
        
        Args:
            config: Dictionary containing truncation configuration options:
                - max_tokens: Maximum number of tokens to keep in output
                - max_lines: Maximum number of lines to keep in output
                - enabled: Whether truncation is enabled
        """
        self.truncation_config.update(config)
    
    def get_truncation_config(self) -> Dict[str, Any]:
        """
        Get the current truncation configuration.
        
        Returns:
            Dictionary containing truncation configuration
        """
        return self.truncation_config.copy()
    
    def enable_truncation(self, enabled: bool = True):
        """
        Enable or disable output truncation.
        
        Args:
            enabled: Whether to enable truncation
        """
        self.truncation_config["enabled"] = enabled

    def enable_auto_git_checkpoint(self, enabled: bool = True):
        """
        Enable or disable automatic git checkpoint creation after successful shell commands.
        
        Args:
            enabled: If True, automatically create git checkpoints. If False, do not create them.
        """
        self.auto_git_checkpoint = enabled

    def get_auto_git_checkpoint_status(self) -> bool:
        """
        Get the current status of auto_git_checkpoint.
        
        Returns:
            True if auto_git_checkpoint is enabled, False otherwise.
        """
        return self.auto_git_checkpoint
    
    def enable_python_tool(self, enabled: bool = True):
        """
        Enable or disable the Python code execution tool.
        
        Args:
            enabled: If True, enable the run_python tool. If False, disable it.
        """
        if enabled != self._python_tool_enabled:
            self._python_tool_enabled = enabled
            # Re-setup tools to reflect the change
            self._setup_code_execution_tools()
    
    def enable_shell_tool(self, enabled: bool = True):
        """
        Enable or disable the shell command execution tool.
        
        Args:
            enabled: If True, enable the bash tool. If False, disable it.
        """
        if enabled != self._shell_tool_enabled:
            self._shell_tool_enabled = enabled
            # Re-setup tools to reflect the change
            self._setup_code_execution_tools()
    
    def get_python_tool_status(self) -> bool:
        """
        Get the current status of the Python tool.
        
        Returns:
            True if the run_python tool is enabled, False otherwise.
        """
        return self._python_tool_enabled
    
    def get_shell_tool_status(self) -> bool:
        """
        Get the current status of the shell tool.
        
        Returns:
            True if the bash tool is enabled, False otherwise.
        """
        return self._shell_tool_enabled
    
    def set_environment_variables(self, env_vars: Dict[str, str]):
        """
        Set environment variables for the code execution provider.
        Currently only supported for SeatbeltProvider.
        
        Args:
            env_vars: Dictionary of environment variable name -> value pairs
            
        Raises:
            AttributeError: If the provider doesn't support environment variables
        """
        if hasattr(self.code_provider, 'set_environment_variables'):
            self.code_provider.set_environment_variables(env_vars)
        else:
            raise AttributeError(f"Provider {self.provider} does not support environment variables")
    
    def add_environment_variable(self, name: str, value: str):
        """
        Add a single environment variable for the code execution provider.
        Currently only supported for SeatbeltProvider.
        
        Args:
            name: Environment variable name
            value: Environment variable value
            
        Raises:
            AttributeError: If the provider doesn't support environment variables
        """
        if hasattr(self.code_provider, 'add_environment_variable'):
            self.code_provider.add_environment_variable(name, value)
        else:
            raise AttributeError(f"Provider {self.provider} does not support environment variables")
    
    def remove_environment_variable(self, name: str):
        """
        Remove an environment variable from the code execution provider.
        Currently only supported for SeatbeltProvider.
        
        Args:
            name: Environment variable name to remove
            
        Raises:
            AttributeError: If the provider doesn't support environment variables
        """
        if hasattr(self.code_provider, 'remove_environment_variable'):
            self.code_provider.remove_environment_variable(name)
        else:
            raise AttributeError(f"Provider {self.provider} does not support environment variables")
    
    def get_environment_variables(self) -> Dict[str, str]:
        """
        Get a copy of current environment variables from the code execution provider.
        Currently only supported for SeatbeltProvider.
        
        Returns:
            Dictionary of current environment variables
            
        Raises:
            AttributeError: If the provider doesn't support environment variables
        """
        if hasattr(self.code_provider, 'get_environment_variables'):
            return self.code_provider.get_environment_variables()
        else:
            raise AttributeError(f"Provider {self.provider} does not support environment variables")


# Example usage demonstrating both LLM tools and code tools
async def run_example():
    """
    Example demonstrating TinyCodeAgent with both LLM tools and code tools.
    Also shows how to use local vs remote execution.
    
    LLM tools: Available to the LLM for direct calling
    Code tools: Available in the Python execution environment
    """
    from tinyagent import tool
    import os
    
    # Example LLM tool - available to the LLM for direct calling
    @tool(name="search_web", description="Search the web for information")
    async def search_web(query: str) -> str:
        """Search the web for information."""
        return f"Search results for: {query}"
    
    # Example code tool - available in Python environment
    @tool(name="data_processor", description="Process data arrays")
    def data_processor(data: List[float]) -> Dict[str, Any]:
        """Process a list of numbers and return statistics."""
        return {
            "mean": sum(data) / len(data),
            "max": max(data),
            "min": min(data),
            "count": len(data)
        }
    
    print("🚀 Testing TinyCodeAgent with REMOTE execution (Modal)")
    # Create TinyCodeAgent with remote execution (default)
    agent_remote = TinyCodeAgent(
        model="gpt-5-mini",
        tools=[search_web],  # LLM tools
        code_tools=[data_processor],  # Code tools
        user_variables={
            "sample_data": [1, 2, 3, 4, 5, 10, 15, 20]
        },
        authorized_imports=["tinyagent", "gradio", "requests", "numpy", "pandas"],  # Explicitly specify authorized imports
        local_execution=False,  # Remote execution via Modal (default)
        check_string_obfuscation=True,
        default_workdir=os.path.join(os.getcwd(), "examples"),  # Set a default working directory for shell commands
        truncation_config={
            "max_tokens": 3000,
            "max_lines": 250,
            "enabled": True
        }
    )
    
    # Connect to MCP servers
    await agent_remote.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent_remote.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    # Test the remote agent
    response_remote = await agent_remote.run("""
    I have some sample data. Please use the data_processor tool in Python to analyze my sample_data
    and show me the results.
    """)
    
    print("Remote Agent Response:")
    print(response_remote)
    print("\n" + "="*80 + "\n")
    
    # Test the resume functionality
    print("🔄 Testing resume functionality (continuing without new user input)")
    resume_response = await agent_remote.resume(max_turns=3)
    print("Resume Response:")
    print(resume_response)
    print("\n" + "="*80 + "\n")
    
    # Now test with local execution
    print("🏠 Testing TinyCodeAgent with LOCAL execution")
    agent_local = TinyCodeAgent(
        model="gpt-5-mini",
        tools=[search_web],  # LLM tools
        code_tools=[data_processor],  # Code tools
        user_variables={
            "sample_data": [1, 2, 3, 4, 5, 10, 15, 20]
        },
        authorized_imports=["tinyagent", "gradio", "requests"],  # More restricted imports for local execution
        local_execution=True,  # Local execution
        check_string_obfuscation=True
    )
    
    # Connect to MCP servers
    await agent_local.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent_local.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    # Test the local agent
    response_local = await agent_local.run("""
    I have some sample data. Please use the data_processor tool in Python to analyze my sample_data
    and show me the results.
    """)
    
    print("Local Agent Response:")
    print(response_local)
    
    # Demonstrate adding tools dynamically
    @tool(name="validator", description="Validate processed results")
    def validator(results: Dict[str, Any]) -> bool:
        """Validate that results make sense."""
        return all(key in results for key in ["mean", "max", "min", "count"])
    
    # Add a new code tool to both agents
    agent_remote.add_code_tool(validator)
    agent_local.add_code_tool(validator)
    
    # Demonstrate adding authorized imports dynamically
    print("\n" + "="*80)
    print("🔧 Testing with dynamically added authorized imports")
    agent_remote.add_authorized_imports(["matplotlib", "seaborn"])
    
    # Test with visualization libraries
    viz_prompt = "Create a simple plot of the sample_data and save it as a base64 encoded image string."
    
    response_viz = await agent_remote.run(viz_prompt)
    print("Remote Agent Visualization Response:")
    print(response_viz)
    
    print("\n" + "="*80)
    print("🔧 Testing with dynamically added tools")
    
    # Test both agents with the new tool
    validation_prompt = "Now validate the previous analysis results using the validator tool."
    
    response2_remote = await agent_remote.run(validation_prompt)
    print("Remote Agent Validation Response:")
    print(response2_remote)
    
    response2_local = await agent_local.run(validation_prompt)
    print("Local Agent Validation Response:")
    print(response2_local)
    
    # Test shell execution
    print("\n" + "="*80)
    print("🐚 Testing shell execution")
    
    shell_prompt = "Run 'ls -la' to list files in the current directory."
    
    response_shell = await agent_remote.run(shell_prompt)
    print("Shell Execution Response:")
    print(response_shell)
    
    # Test default working directory functionality
    print("\n" + "="*80)
    print("🏠 Testing default working directory functionality")
    
    # Set a custom default working directory
    custom_dir = os.path.expanduser("~")  # Use home directory as an example
    agent_remote.set_default_workdir(custom_dir)
    print(f"Set default working directory to: {custom_dir}")
    
    # Create a new directory for testing
    test_dir = os.path.join(os.getcwd(), "test_workdir")
    print(f"Setting default working directory with auto-creation: {test_dir}")
    agent_remote.set_default_workdir(test_dir, create_if_not_exists=True)
    
    # Run shell command without specifying workdir - should use the default
    shell_prompt_default_dir = "Run 'pwd' to show the current working directory."
    
    response_shell_default = await agent_remote.run(shell_prompt_default_dir)
    print("Shell Execution with Default Working Directory:")
    print(response_shell_default)
    
    # Run shell command with explicit workdir - should override the default
    shell_prompt_explicit_dir = "Run 'pwd' in the /tmp directory."
    
    response_shell_explicit = await agent_remote.run(shell_prompt_explicit_dir)
    print("Shell Execution with Explicit Working Directory:")
    print(response_shell_explicit)
    
    # Test truncation functionality
    print("\n" + "="*80)
    print("✂️ Testing output truncation")
    
    # Configure truncation with smaller limits for testing
    agent_remote.set_truncation_config({
        "max_tokens": 100,  # Very small limit for testing
        "max_lines": 5      # Very small limit for testing
    })
    
    # Generate a large output to test truncation
    large_output_prompt = """
    Generate a large output by printing a lot of text. Create a Python script that:
    1. Prints numbers from 1 to 1000
    2. For each number, also print its square and cube
    3. Add random text for each line to make it longer
    """
    
    response_truncated = await agent_remote.run(large_output_prompt)
    print("Truncated Output Response:")
    print(response_truncated)
    
    # Test disabling truncation
    print("\n" + "="*80)
    print("🔄 Testing with truncation disabled")
    
    agent_remote.enable_truncation(False)
    response_untruncated = await agent_remote.run("Run the same script again but limit to 20 numbers")
    print("Untruncated Output Response:")
    print(response_untruncated)
    
    # Test git checkpoint functionality
    print("\n" + "="*80)
    print("🔄 Testing git checkpoint functionality")
    
    # Enable git checkpoints
    agent_remote.enable_auto_git_checkpoint(True)
    print(f"Auto Git Checkpoint enabled: {agent_remote.get_auto_git_checkpoint_status()}")
    
    # Create a test file to demonstrate git checkpoint
    git_test_prompt = """
    Create a new file called test_file.txt with some content, then modify it, and observe
    that git checkpoints are created automatically after each change.
    """
    
    git_response = await agent_remote.run(git_test_prompt)
    print("Git Checkpoint Response:")
    print(git_response)
    
    # Disable git checkpoints
    agent_remote.enable_auto_git_checkpoint(False)
    print(f"Auto Git Checkpoint disabled: {agent_remote.get_auto_git_checkpoint_status()}")
    
    # Test seatbelt provider if supported
    if TinyCodeAgent.is_seatbelt_supported():
        print("\n" + "="*80)
        print("🔒 Testing TinyCodeAgent with SEATBELT provider (sandboxed execution)")
        
        # Create a test directory for read/write access
        test_read_dir = os.path.join(os.getcwd(), "test_read_dir")
        test_write_dir = os.path.join(os.getcwd(), "test_write_dir")
        
        # Create directories if they don't exist
        os.makedirs(test_read_dir, exist_ok=True)
        os.makedirs(test_write_dir, exist_ok=True)
        
        # Create a test file in the read directory
        with open(os.path.join(test_read_dir, "test.txt"), "w") as f:
            f.write("This is a test file for reading")
        
        # Create a simple seatbelt profile
        seatbelt_profile = """(version 1)
        
        ; Default to deny everything
        (deny default)
        
        ; Allow network connections with proper DNS resolution
        (allow network*)
        (allow network-outbound)
        (allow mach-lookup)
        
        ; Allow process execution
        (allow process-exec)
        (allow process-fork)
        (allow signal (target self))
        
        ; Restrict file read to current path and system files
        (deny file-read* (subpath "/Users"))
        (allow file-read*
          (subpath "{os.getcwd()}")
          (subpath "/usr")
          (subpath "/System")
          (subpath "/Library")
          (subpath "/bin")
          (subpath "/sbin")
          (subpath "/opt")
          (subpath "/private/tmp")
          (subpath "/private/var/tmp")
          (subpath "/dev")
          (subpath "/etc")
          (literal "/")
          (literal "/."))
        
        ; Allow write access to specified folder and temp directories
        (deny file-write* (subpath "/"))
        (allow file-write*
          (subpath "{os.getcwd()}")
          (subpath "/private/tmp")
          (subpath "/private/var/tmp")
          (subpath "/dev"))
        
        ; Allow standard device operations
        (allow file-write-data
          (literal "/dev/null")
          (literal "/dev/dtracehelper")
          (literal "/dev/tty")
          (literal "/dev/stdout")
          (literal "/dev/stderr"))
        
        ; Allow iokit operations needed for system functions
        (allow iokit-open)
        
        ; Allow shared memory operations
        (allow ipc-posix-shm)
        
        ; Allow basic system operations
        (allow file-read-metadata)
        (allow process-info-pidinfo)
        (allow process-info-setcontrol)
        """
        
        # Create TinyCodeAgent with seatbelt provider
        agent_seatbelt = TinyCodeAgent(
            model="gpt-5-mini",
            tools=[search_web],  # LLM tools
            code_tools=[data_processor],  # Code tools
            user_variables={
                "sample_data": [1, 2, 3, 4, 5, 10, 15, 20]
            },
            provider="seatbelt",  # Use seatbelt provider
            provider_config={
                "seatbelt_profile": seatbelt_profile,
                # Alternatively, you can specify a path to a seatbelt profile file:
                # "seatbelt_profile_path": "/path/to/seatbelt.sb",
                # "python_env_path": "/path/to/python/env",  # Optional path to Python environment
                
                # Specify additional directories for read/write access
                "additional_read_dirs": [test_read_dir],
                "additional_write_dirs": [test_write_dir],
                
                # Allow git commands
                "bypass_shell_safety": True,
                "additional_safe_shell_commands": ["git"],
                
                # Environment variables to make available in the sandbox
                "environment_variables": {
                    "TEST_READ_DIR": test_read_dir,
                    "TEST_WRITE_DIR": test_write_dir,
                    "PROJECT_NAME": "TinyAgent Seatbelt Demo",
                    "BUILD_VERSION": "1.0.0"
                }
            },
            local_execution=True,  # Required for seatbelt
            check_string_obfuscation=True,
            truncation_config={
                "max_tokens": 500,
                "max_lines": 20,
                "enabled": True
            }
        )
        
        # Connect to MCP servers
        await agent_seatbelt.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
        await agent_seatbelt.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
        
        # Example: connecting with environment variables
        env_vars = {
            "MCP_DEBUG": "true",
            "RATE_LIMIT": "100",
            "CUSTOM_CONFIG": "seatbelt_mode"
        }
        
        # Create a simple Modal agent to demonstrate environment variable usage
        agent_modal = TinyCodeAgent(
            model="gpt-5-mini",
            tools=[search_web],
            code_tools=[data_processor],
            provider="modal",
            local_execution=False,
            api_key=api_key
        )
        
        try:
            await agent_modal.connect_to_server(
                "npx", 
                ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
                env=env_vars
            )
            logger.info("Successfully connected Modal agent with environment variables")
        except Exception as e:
            logger.warning(f"Environment variable example failed: {e}")
        finally:
            await agent_modal.close()
        
        # Test the seatbelt agent
        response_seatbelt = await agent_seatbelt.run("""
        I have some sample data. Please use the data_processor tool in Python to analyze my sample_data
        and show me the results.
        """)
        
        print("Seatbelt Agent Response:")
        print(response_seatbelt)
        
        # Test shell execution in sandbox
        shell_prompt_sandbox = "Run 'ls -la' to list files in the current directory."
        
        response_shell_sandbox = await agent_seatbelt.run(shell_prompt_sandbox)
        print("Shell Execution in Sandbox:")
        print(response_shell_sandbox)
        
        # Test reading from the additional read directory
        read_prompt = f"Read the contents of the file in the test_read_dir directory."
        
        response_read = await agent_seatbelt.run(read_prompt)
        print("Reading from Additional Read Directory:")
        print(response_read)
        
        # Test writing to the additional write directory
        write_prompt = f"Write a file called 'output.txt' with the text 'Hello from sandbox!' in the test_write_dir directory."
        
        response_write = await agent_seatbelt.run(write_prompt)
        print("Writing to Additional Write Directory:")
        print(response_write)
        
        # Test environment variables
        print("\n" + "="*80)
        print("🔧 Testing environment variables functionality")
        
        # Add additional environment variables dynamically
        agent_seatbelt.add_environment_variable("CUSTOM_VAR", "custom_value")
        agent_seatbelt.add_environment_variable("DEBUG_MODE", "true")
        
        # Get and display current environment variables
        current_env_vars = agent_seatbelt.get_environment_variables()
        print(f"Current environment variables: {list(current_env_vars.keys())}")
        
        # Test accessing environment variables in Python and shell
        env_test_prompt = """
        Test the environment variables we set:
        1. In Python, use os.environ to check for CUSTOM_VAR and DEBUG_MODE
        2. In a shell command, use 'echo $CUSTOM_VAR' and 'echo $DEBUG_MODE'
        3. Also check the TEST_READ_DIR and TEST_WRITE_DIR variables that were set during initialization
        4. Show all environment variables that start with 'TEST_' or 'CUSTOM_' or 'DEBUG_'
        """
        
        response_env_test = await agent_seatbelt.run(env_test_prompt)
        print("Environment Variables Test:")
        print(response_env_test)
        
        # Update environment variables
        agent_seatbelt.set_environment_variables({
            "CUSTOM_VAR": "updated_value",
            "NEW_VAR": "new_value",
            "API_KEY": "test_api_key_123"
        })
        
        # Test updated environment variables
        updated_env_test_prompt = """
        Test the updated environment variables:
        1. Check that CUSTOM_VAR now has the value 'updated_value'
        2. Check that NEW_VAR is available with value 'new_value'
        3. Check that API_KEY is available with value 'test_api_key_123'
        4. Verify that DEBUG_MODE is no longer available (should have been removed by set operation)
        """
        
        response_updated_env = await agent_seatbelt.run(updated_env_test_prompt)
        print("Updated Environment Variables Test:")
        print(response_updated_env)
        
        # Remove a specific environment variable
        agent_seatbelt.remove_environment_variable("API_KEY")
        
        # Test that the removed variable is no longer available
        removed_env_test_prompt = """
        Test that API_KEY environment variable has been removed:
        1. Try to access API_KEY in Python - it should not be available
        2. Use shell command 'echo $API_KEY' - it should be empty
        3. List all current environment variables that start with 'CUSTOM_' or 'NEW_'
        """
        
        response_removed_env = await agent_seatbelt.run(removed_env_test_prompt)
        print("Removed Environment Variable Test:")
        print(response_removed_env)
        
        # Test git commands with the custom configuration
        git_prompt = "Run 'git status' to show the current git status."
        
        response_git = await agent_seatbelt.run(git_prompt)
        print("Git Command Execution:")
        print(response_git)
        
        # Clean up test directories
        import shutil
        try:
            shutil.rmtree(test_read_dir)
            shutil.rmtree(test_write_dir)
            print("Cleaned up test directories")
        except Exception as e:
            print(f"Error cleaning up test directories: {str(e)}")
        
        await agent_seatbelt.close()
    else:
        print("\n" + "="*80)
        print("⚠️  Seatbelt provider is not supported on this system. Skipping seatbelt tests.")
    
    # Test optional tool functionality
    print("\n" + "="*80)
    print("🔧 Testing optional tool functionality")
    
    # Create an agent with only Python tool enabled (no shell tool)
    print("Creating agent with only Python tool enabled...")
    agent_python_only = TinyCodeAgent(
        model="gpt-5-mini",
        tools=[search_web],
        code_tools=[data_processor],
        user_variables={"test_data": [1, 2, 3, 4, 5]},
        enable_python_tool=True,
        enable_shell_tool=False,  # Disable shell tool
        local_execution=True
    )
    
    # Connect to MCP servers
    await agent_python_only.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent_python_only.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    # Check tool status
    print(f"Python tool enabled: {agent_python_only.get_python_tool_status()}")
    print(f"Shell tool enabled: {agent_python_only.get_shell_tool_status()}")
    
    # Test Python execution (should work)
    python_response = await agent_python_only.run("""
    Use the data_processor tool to analyze the test_data and show me the results.
    """)
    print("Python Tool Test (should work):")
    print(python_response)
    
    # Test shell execution (should not work - tool disabled)
    shell_response = await agent_python_only.run("""
    Run 'ls -la' to list files in the current directory.
    """)
    print("Shell Tool Test (should not work - tool disabled):")
    print(shell_response)
    
    # Now enable the shell tool dynamically
    print("\nEnabling shell tool dynamically...")
    agent_python_only.enable_shell_tool(True)
    print(f"Shell tool enabled: {agent_python_only.get_shell_tool_status()}")
    
    # Test shell execution again (should work now)
    shell_response2 = await agent_python_only.run("""
    Run 'ls -la' to list files in the current directory.
    """)
    print("Shell Tool Test (should work now - tool enabled):")
    print(shell_response2)
    
    # Create an agent with only shell tool enabled (no Python tool)
    print("\nCreating agent with only shell tool enabled...")
    agent_shell_only = TinyCodeAgent(
        model="gpt-5-mini",
        tools=[search_web],
        code_tools=[data_processor],
        user_variables={"test_data": [1, 2, 3, 4, 5]},
        enable_python_tool=False,  # Disable Python tool
        enable_shell_tool=True,
        local_execution=True
    )
    
    # Connect to MCP servers
    await agent_shell_only.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent_shell_only.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    # Check tool status
    print(f"Python tool enabled: {agent_shell_only.get_python_tool_status()}")
    print(f"Shell tool enabled: {agent_shell_only.get_shell_tool_status()}")
    
    # Test shell execution (should work)
    shell_response3 = await agent_shell_only.run("""
    Run 'pwd' to show the current working directory.
    """)
    print("Shell Tool Test (should work):")
    print(shell_response3)
    
    # Test Python execution (should not work - tool disabled)
    python_response2 = await agent_shell_only.run("""
    Use the data_processor tool to analyze the test_data and show me the results.
    """)
    print("Python Tool Test (should not work - tool disabled):")
    print(python_response2)
    
    # Now enable the Python tool dynamically
    print("\nEnabling Python tool dynamically...")
    agent_shell_only.enable_python_tool(True)
    print(f"Python tool enabled: {agent_shell_only.get_python_tool_status()}")
    
    # Test Python execution again (should work now)
    python_response3 = await agent_shell_only.run("""
    Use the data_processor tool to analyze the test_data and show me the results.
    """)
    print("Python Tool Test (should work now - tool enabled):")
    print(python_response3)
    
    # Create an agent with both tools disabled
    print("\nCreating agent with both tools disabled...")
    agent_no_tools = TinyCodeAgent(
        model="gpt-5-mini",
        tools=[search_web],
        code_tools=[data_processor],
        user_variables={"test_data": [1, 2, 3, 4, 5]},
        enable_python_tool=False,  # Disable Python tool
        enable_shell_tool=False,   # Disable shell tool
        local_execution=True
    )
    
    # Connect to MCP servers
    await agent_no_tools.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent_no_tools.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    # Check tool status
    print(f"Python tool enabled: {agent_no_tools.get_python_tool_status()}")
    print(f"Shell tool enabled: {agent_no_tools.get_shell_tool_status()}")
    
    # Test both tools (should not work - both disabled)
    no_tools_response = await agent_no_tools.run("""
    Try to use both Python and shell tools to analyze the test_data and list files.
    """)
    print("Both Tools Test (should not work - both disabled):")
    print(no_tools_response)
    
    # Enable both tools dynamically
    print("\nEnabling both tools dynamically...")
    agent_no_tools.enable_python_tool(True)
    agent_no_tools.enable_shell_tool(True)
    print(f"Python tool enabled: {agent_no_tools.get_python_tool_status()}")
    print(f"Shell tool enabled: {agent_no_tools.get_shell_tool_status()}")
    
    # Test both tools again (should work now)
    both_tools_response = await agent_no_tools.run("""
    Use both Python and shell tools: first analyze the test_data with data_processor, then list files with ls.
    """)
    print("Both Tools Test (should work now - both enabled):")
    print(both_tools_response)
    
    # Clean up
    await agent_python_only.close()
    await agent_shell_only.close()
    await agent_no_tools.close()
    
    await agent_remote.close()
    await agent_local.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_example()) 