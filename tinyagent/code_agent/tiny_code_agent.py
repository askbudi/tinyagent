import traceback
import os
from textwrap import dedent
from typing import Optional, List, Dict, Any
from pathlib import Path
from tinyagent import TinyAgent, tool
from tinyagent.hooks.logging_manager import LoggingManager
from .providers.base import CodeExecutionProvider
from .providers.modal_provider import ModalProvider
from .helper import translate_tool_for_code_agent, load_template, render_system_prompt, prompt_code_example, prompt_qwen_helper


DEFAULT_SUMMARY_SYSTEM_PROMPT = (
    "You are an expert coding assistant. Your goal is to generate a concise, structured summary "
    "of the conversation below that captures all essential information needed to continue "
    "development after context replacement. Include tasks performed, code areas modified or "
    "reviewed, key decisions or assumptions, test results or errors, and outstanding tasks or next steps."
    
)

class TinyCodeAgent:
    """
    A TinyAgent specialized for code execution tasks.
    
    This class provides a high-level interface for creating agents that can execute
    Python code using various providers (Modal, Docker, local execution, etc.).
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        log_manager: Optional[LoggingManager] = None,
        provider: str = "modal",
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
        **agent_kwargs
    ):
        """
        Initialize TinyCodeAgent.
        
        Args:
            model: The language model to use
            api_key: API key for the model
            log_manager: Optional logging manager
            provider: Code execution provider ("modal", "local", etc.)
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
            **agent_kwargs: Additional arguments passed to TinyAgent
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
        self.provider = provider  # Store provider type for reuse
        self.check_string_obfuscation = check_string_obfuscation
        self.default_workdir = default_workdir or os.getcwd()  # Default to current working directory if not specified
        
        # Create the code execution provider
        self.code_provider = self._create_provider(provider, self.provider_config)
        
        # Set user variables in the provider
        if self.user_variables:
            self.code_provider.set_user_variables(self.user_variables)
        
        # Build system prompt
        self.static_system_prompt= system_prompt
        self.system_prompt =  self._build_system_prompt(system_prompt_template)
        
        
        self.summary_config = summary_config or {}

        # Create the underlying TinyAgent with summary configuration
        self.agent = TinyAgent(
            model=model,
            api_key=api_key,
            system_prompt=self.system_prompt,
            logger=log_manager.get_logger('tinyagent.tiny_agent') if log_manager else None,
            summary_config=summary_config,
            **agent_kwargs
        )
        
        # Add the code execution tools
        self._setup_code_execution_tools()
        
        # Add LLM tools (not code tools - those go to the provider)
        if self.tools:
            self.agent.add_tools(self.tools)
    
    def _create_provider(self, provider_type: str, config: Dict[str, Any]) -> CodeExecutionProvider:
        """Create a code execution provider based on the specified type."""
        if provider_type.lower() == "modal":
            # Merge pip_packages from both sources (direct parameter and provider_config)
            config_pip_packages = config.get("pip_packages", [])
            final_pip_packages = list(set(self.pip_packages + config_pip_packages))
            
            # Merge authorized_imports from both sources (direct parameter and provider_config)
            config_authorized_imports = config.get("authorized_imports", [])
            final_authorized_imports = list(set(self.authorized_imports + config_authorized_imports))
            
            final_config = config.copy()
            final_config["pip_packages"] = final_pip_packages
            final_config["authorized_imports"] = final_authorized_imports
            final_config["check_string_obfuscation"] = self.check_string_obfuscation
            
            return ModalProvider(
                log_manager=self.log_manager,
                code_tools=self.code_tools,
                local_execution=self.local_execution,
                **final_config
            )
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")
    
    def _build_system_prompt(self, template_path: Optional[str] = None) -> str:
        """Build the system prompt for the code agent."""
        # Use default template if none provided
        if self.static_system_prompt is not None:
            return self.static_system_prompt
        elif template_path is None :
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
        
        # Add user variables information to the prompt
        if self.user_variables:
            variables_info = self._build_variables_prompt()
            base_prompt += "\n\n" + variables_info
        
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
    
    def _setup_code_execution_tools(self):
        """Set up the code execution tools using the code provider."""
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
                    
                result = await self.code_provider.execute_python(code_lines, timeout)
                
                # After execution, update TinyCodeAgent's user_variables from the provider
                # This ensures they stay in sync
                self.user_variables = self.code_provider.get_user_variables()
                
                return str(result)
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
                
                return f"Error executing code: {str(e)}"
        
        @tool(name="bash", description=dedent("""
        This tool executes shell commands securely in a sandboxed environment.
        Only a limited set of safe commands are allowed for security reasons.
        Before executing the command, please follow these steps:
          
          1. Directory Verification:
             - If the command will create new directories or files, first use ls to verify the parent directory exists and is the correct location
             - For example, before running "mkdir foo/bar", first use ls to check that "foo" exists and is the intended parent directory
          
          2. Command Execution:
             - Always quote file paths that contain spaces with double quotes (e.g., cd "path with spaces/file.txt")
             - Examples of proper quoting:
               - cd "/Users/name/My Documents" (correct)
               - cd /Users/name/My Documents (incorrect - will fail)
               - python "/path/with spaces/script.py" (correct)
               - python /path/with spaces/script.py (incorrect - will fail)
             - After ensuring proper quoting, execute the command.
             - Capture the output of the command.
          
          Usage notes:
            - The command argument is required.
            - You have the capability to call multiple tools in a single response. When multiple independent pieces of information are requested, batch your tool calls together for optimal performance.
            - You can specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). If not specified, commands will timeout after 120000ms (2 minutes).
            - It is very helpful if you write a clear, concise description of what this command does in 5-10 words.
            - If the output exceeds 30000 characters, output will be truncated before being returned to you.
            
           - If you _still_ need to run `grep`, STOP. ALWAYS USE ripgrep at `rg` first, which all ${PRODUCT_NAME} users have pre-installed.
          "  - When issuing multiple commands, use the ; or && operator to separate them. DO NOT use newlines (newlines are ok in quoted strings).\n" +
            - Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`. You may use `cd` if the User explicitly requests it.
              <good-example>
              pytest /foo/bar/tests
              </good-example>
              <bad-example>
              cd /foo/bar && pytest tests
              </bad-example>

        Args:
            command: list[str]: The shell command to execute as a list of strings.  Example: ["ls", "-la"] or ["cat", "file.txt"]
                
            absolute_workdir: str: could be presented workdir in the system prompt or one of the subdirectories of the workdir. This is the only allowed path, and accessing else will result in an error.
            description: str: A clear, concise description of what this command does in 5-10 words.
            timeout: int: Maximum execution time in seconds (default: 30).
        Returns:
            Dictionary with stdout, stderr, and exit_code from the command execution.
            If the command is rejected for security reasons, stderr will contain the reason.
            The stdout will include information about which working directory was used.
        """))
        async def run_shell(command: List[str], absolute_workdir: str,  description: str, timeout: int = 30) -> str:
            """Execute shell commands securely using the configured provider."""
            try:
                # Use the default working directory if none is specified
                effective_workdir = absolute_workdir or self.default_workdir
                print(f" {command} to {description}")
                # Verify that the working directory exists
                if effective_workdir and not os.path.exists(effective_workdir):
                    return str({
                        "stdout": "",
                        "stderr": f"Working directory does not exist: {effective_workdir}",
                        "exit_code": 1
                    })
                
                if effective_workdir and not os.path.isdir(effective_workdir):
                    return str({
                        "stdout": "",
                        "stderr": f"Path is not a directory: {effective_workdir}",
                        "exit_code": 1
                    })
                
                result = await self.code_provider.execute_shell(command, timeout, effective_workdir)
                return str(result)
            except Exception as e:
                COLOR = {
                    "RED": "\033[91m",
                    "ENDC": "\033[0m",
                }
                print(f"{COLOR['RED']}{str(e)}{COLOR['ENDC']}")
                print(f"{COLOR['RED']}{traceback.format_exc()}{COLOR['ENDC']}")
                
                return f"Error executing shell command: {str(e)}"
        
        self.agent.add_tool(run_python)
        self.agent.add_tool(run_shell)
    
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
    
    async def run(self, user_input: str, max_turns: int = 10) -> str:
        """
        Run the code agent with the given input.
        
        Args:
            user_input: The user's request or question
            max_turns: Maximum number of conversation turns
            
        Returns:
            The agent's response
        """
        return await self.agent.run(user_input, max_turns)
    
    async def resume(self, max_turns: int = 10) -> str:
        """
        Resume the conversation without adding a new user message.
        
        This method continues the conversation from the current state,
        allowing the agent to process the existing conversation history
        and potentially take additional actions.
        
        Args:
            max_turns: Maximum number of conversation turns
            
        Returns:
            The agent's response
        """
        return await self.agent.resume(max_turns)
    
    async def connect_to_server(self, command: str, args: List[str], **kwargs):
        """Connect to an MCP server."""
        return await self.agent.connect_to_server(command, args, **kwargs)
    
    def add_callback(self, callback):
        """Add a callback to the agent."""
        self.agent.add_callback(callback)
    
    def add_tool(self, tool):
        """Add a tool to the agent (LLM tool)."""
        self.agent.add_tool(tool)
    
    def add_tools(self, tools: List[Any]):
        """Add multiple tools to the agent (LLM tools)."""
        self.agent.add_tools(tools)
    
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
        # Update the agent's system prompt
        self.agent.system_prompt = self.system_prompt
    
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
        # Update the agent's system prompt
        self.agent.system_prompt = self.system_prompt
    
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
        # Update the agent's system prompt
        self.agent.system_prompt = self.system_prompt
    
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
        # Update the agent's system prompt
        self.agent.system_prompt = self.system_prompt
    
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
        self.agent.system_prompt = self.system_prompt
    
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
            self.agent.system_prompt = self.system_prompt
    
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
        self.agent.system_prompt = self.system_prompt
    
    def get_authorized_imports(self) -> List[str]:
        """
        Get a copy of current authorized imports.
        
        Returns:
            List of authorized imports
        """
        return self.authorized_imports.copy()
    
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
            self.agent.system_prompt = self.system_prompt
    
    async def close(self):
        """Clean up resources."""
        await self.code_provider.cleanup()
        await self.agent.close()
    
    def clear_conversation(self):
        """Clear the conversation history."""
        self.agent.clear_conversation()
    
    @property
    def messages(self):
        """Get the conversation messages."""
        return self.agent.messages
    
    @property
    def session_id(self):
        """Get the session ID."""
        return self.agent.session_id 

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

    async def summarize(self) -> str:
        """
        Generate a summary of the current conversation history.
        
        Args:
        Returns:
            A string containing the conversation summary
        """
        # Use the underlying TinyAgent's summarize_conversation method
        return await self.agent.summarize()
        
    async def compact(self) -> bool:
        """
        Compact the conversation history by replacing it with a summary.
        
        This method delegates to the underlying TinyAgent's compact method,
        which:
        1. Generates a summary of the current conversation
        2. If successful, replaces the conversation with just [system, user] messages
           where the user message contains the summary
        3. Returns True if compaction was successful, False otherwise
        
        Returns:
            Boolean indicating whether the compaction was successful
        """
        return await self.agent.compact()


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
        model="gpt-4.1-mini",
        tools=[search_web],  # LLM tools
        code_tools=[data_processor],  # Code tools
        user_variables={
            "sample_data": [1, 2, 3, 4, 5, 10, 15, 20]
        },
        authorized_imports=["tinyagent", "gradio", "requests", "numpy", "pandas"],  # Explicitly specify authorized imports
        local_execution=False,  # Remote execution via Modal (default)
        check_string_obfuscation=True,
        default_workdir=os.path.join(os.getcwd(), "examples")  # Set a default working directory for shell commands
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
        model="gpt-4.1-mini",
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
    
    await agent_remote.close()
    await agent_local.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_example()) 