from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Set
from tinyagent.hooks.logging_manager import LoggingManager
import cloudpickle


class CodeExecutionProvider(ABC):
    """
    Abstract base class for code execution providers.
    
    This class defines the interface that all code execution providers must implement.
    It allows for easy extension to support different execution environments
    (Modal, Docker, local execution, cloud functions, etc.) with minimal code changes.
    """
    
    def __init__(
        self,
        log_manager: LoggingManager,
        default_python_codes: Optional[List[str]] = None,
        code_tools: List[Dict[str, Any]] = None,
        pip_packages: List[str] = None,
        secrets: Dict[str, Any] = None,
        lazy_init: bool = True,
        bypass_shell_safety: bool = False,
        additional_safe_shell_commands: Optional[List[str]] = None,
        additional_safe_control_operators: Optional[List[str]] = None,
        **kwargs
    ):
        self.log_manager = log_manager
        self.default_python_codes = default_python_codes or []
        self.code_tools = code_tools or []
        self.pip_packages = pip_packages or []
        self.secrets = secrets or {}
        self.lazy_init = lazy_init
        self.kwargs = kwargs
        self.executed_default_codes = False
        self._globals_dict = kwargs.get("globals_dict", {})
        self._locals_dict = kwargs.get("locals_dict", {})
        self._user_variables = {}
        self.code_tools_definitions = []
        
        # Shell safety configuration
        self.bypass_shell_safety = bypass_shell_safety
        
        # Safe shell commands that don't modify the system or access sensitive data
        self.safe_shell_commands: Set[str] = {
            "ls", "cat", "grep", "find", "echo", "pwd", "whoami", "date", 
            "head", "tail", "wc", "sort", "uniq", "tr", "cut", "sed", "awk",
            "ps", "df", "du", "uname", "which", "type", "file", "stat", "rg", "if",
            "tree"
        }
        
        # Add additional safe shell commands if provided
        if additional_safe_shell_commands:
            if "*" in additional_safe_shell_commands:
                # If wildcard is provided, allow all commands (effectively bypassing the check)
                self.bypass_shell_safety = True
            else:
                self.safe_shell_commands.update(additional_safe_shell_commands)
        
        # Safe control operators for shell commands
        self.safe_control_operators: Set[str] = {"&&", "||", ";", "|"}
        
        # Add additional safe control operators if provided
        if additional_safe_control_operators:
            if "*" in additional_safe_control_operators:
                # If wildcard is provided, allow all operators
                self.safe_control_operators = set("*")
            else:
                self.safe_control_operators.update(additional_safe_control_operators)
    
    @abstractmethod
    async def execute_python(
        self, 
        code_lines: List[str], 
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Execute Python code and return the result.
        
        Args:
            code_lines: List of Python code lines to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            Dictionary containing execution results with keys:
            - printed_output: stdout from the execution
            - return_value: the return value if any
            - stderr: stderr from the execution
            - error_traceback: exception traceback if any error occurred
        """
        pass
    
    @abstractmethod
    async def execute_shell(
        self,
        command: List[str],
        timeout: int = 10,
        workdir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a shell command securely and return the result.
        
        Args:
            command: List of command parts to execute
            timeout: Maximum execution time in seconds
            workdir: Working directory for command execution
            
        Returns:
            Dictionary containing execution results with keys:
            - stdout: stdout from the execution
            - stderr: stderr from the execution
            - exit_code: exit code from the command
        """
        pass
    
    def is_safe_command(self, command: List[str]) -> Dict[str, Any]:
        """
        Check if a shell command is safe to execute.
        
        Args:
            command: List of command parts to check
            
        Returns:
            Dictionary with:
            - safe: Boolean indicating if command is safe
            - reason: Reason why command is not safe (if applicable)
        """
        # If shell safety checks are bypassed, consider all commands safe
        if self.bypass_shell_safety:
            return {"safe": True}
            
        if type(command) == str:
            command = command.split(" ")
        if not command or not isinstance(command, list) or len(command) == 0:
            return {"safe": False, "reason": "Empty or invalid command"}
        
        # Special handling for bash -c or bash -lc commands
        if len(command) >= 3 and command[0] == "bash" and command[1] in ["-c", "-lc"]:
            # For bash -c or bash -lc, we need to parse the command string that follows
            # We'll extract commands from the bash command string and check them
            bash_cmd_str = command[2]
            
            # Simple parsing of the bash command to extract command names
            # This is a basic implementation and might not cover all edge cases
            import shlex
            import re
            
            try:
                # Shell script keywords that should be allowed
                shell_keywords = {
                    "if", "then", "else", "elif", "fi", "for", "do", "done", 
                    "while", "until", "case", "esac", "in", "function", "select",
                    "time", "coproc", "true", "false"
                }
                
                # Split the command by common shell operators
                cmd_parts = re.split(r'(\||;|&&|\|\||>|>>|<|<<)', bash_cmd_str)
                commands_to_check = []
                
                for part in cmd_parts:
                    part = part.strip()
                    if part and part not in ['|', ';', '&&', '||', '>', '>>', '<', '<<']:
                        # Get the first word which is typically the command
                        try:
                            words = shlex.split(part)
                            if words:
                                cmd_name = words[0].split('/')[-1]  # Extract binary name
                                
                                # Skip shell keywords
                                if cmd_name in shell_keywords:
                                    continue
                                    
                                # Skip variable assignments (e.g., VAR=value)
                                if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', cmd_name):
                                    continue
                                
                                if cmd_name not in self.safe_shell_commands and '*' not in cmd_name and '?' not in cmd_name:
                                    return {"safe": False, "reason": f"Unsafe command in bash script: {cmd_name}"}
                        except Exception:
                            # If parsing fails, be cautious and reject
                            return {"safe": False, "reason": "Could not parse bash command safely"}
                
                # All commands in the bash script are safe
                return {"safe": True}
            except Exception as e:
                return {"safe": False, "reason": f"Error parsing bash command: {str(e)}"}
        
        # Normal command processing for non-bash -c commands
        # Shell operators that might be passed as separate arguments
        shell_operators = ['|', '>', '<', '>>', '<<', '&&', '||', ';']
        
        # Extract actual commands from the command list, ignoring shell operators
        commands_to_check = []
        i = 0
        while i < len(command):
            if command[i] in shell_operators:
                i += 1
                continue
            
            # Extract the binary name
            bin_name = command[i].split("/")[-1]
            commands_to_check.append(bin_name)
            
            # Skip to next command after an operator
            i += 1
            while i < len(command) and command[i] not in shell_operators:
                i += 1
        
        # Check if all commands are in the safe list
        for cmd in commands_to_check:
            # Handle wildcards in command names (e.g., *.py)
            if '*' in cmd or '?' in cmd:
                continue
                
            if cmd not in self.safe_shell_commands:
                return {"safe": False, "reason": f"Unsafe command: {cmd}"}
        
        return {"safe": True}
    
    @abstractmethod
    async def cleanup(self):
        """Clean up any resources used by the provider."""
        pass
    
    def add_tools(self, tools: List[Any]) -> None:
        """
        Add tools to the execution environment.
        
        Args:
            tools: List of tool objects to add
        """
        tools_str_list = ["import cloudpickle"]
        tools_str_list.append("###########<tools>###########\n")
        for tool in tools:
            tools_str_list.append(
                f"globals()['{tool._tool_metadata['name']}'] = cloudpickle.loads({cloudpickle.dumps(tool)})"
            )
        tools_str_list.append("\n\n")
        tools_str_list.append("###########</tools>###########\n")
        tools_str_list.append("\n\n")
        self.code_tools_definitions.extend(tools_str_list)
    
    def set_code_tools(self, tools: List[Any]) -> None:
        """
        Set the code tools available in the execution environment.
        Replaces any existing tools with the new list.
        
        Args:
            tools: List of tool objects to set
        """
        # Clear existing tools
        self.code_tools = tools.copy()
        self.code_tools_definitions = []
        
        # Add the new tools
        if tools:
            self.add_tools(tools)
    
    def set_user_variables(self, variables: Dict[str, Any]) -> None:
        """
        Set user variables that will be available in the Python environment.
        
        Args:
            variables: Dictionary of variable name -> value pairs
        """
        self._user_variables = variables.copy()
        
        # Add variables to the execution environment by serializing them
        # This ensures they are available when code is executed
        variables_str_list = ["import cloudpickle"]
        variables_str_list.append("###########<user_variables>###########\n")
        
        for var_name, var_value in variables.items():
            # Serialize the variable and add it to globals
            serialized_var = cloudpickle.dumps(var_value)
            variables_str_list.append(
                f"globals()['{var_name}'] = cloudpickle.loads({serialized_var})"
            )
        
        variables_str_list.append("\n###########</user_variables>###########\n")
        variables_str_list.append("\n")
        
        # Remove any existing user variables from default codes
        self._remove_existing_user_variables()
        
        # Add new variables to default codes at the beginning (after tools if any)
        # This ensures variables are available from the start
        if variables_str_list:
            # Find where to insert (after tools section if it exists)
            insert_index = 0
            for i, code in enumerate(self.code_tools_definitions):
                if "###########</tools>###########" in code:
                    insert_index = i + 1
                    break
            
            # Insert the variables code
            for j, var_code in enumerate(variables_str_list):
                self.code_tools_definitions.insert(insert_index + j, var_code)
    
    def _remove_existing_user_variables(self) -> None:
        """Remove existing user variables from default python codes."""
        # Find and remove the user variables section
        start_index = None
        end_index = None
        
        for i, code in enumerate(self.code_tools_definitions):
            if "###########<user_variables>###########" in code:
                start_index = i - 1 if i > 0 and "import cloudpickle" in self.code_tools_definitions[i-1] else i
            elif "###########</user_variables>###########" in code:
                end_index = i + 2  # Include the newline after
                break
        
        if start_index is not None and end_index is not None:
            # Remove the old variables section
            del self.code_tools_definitions[start_index:end_index]
    
    def get_user_variables(self) -> Dict[str, Any]:
        """
        Get a copy of current user variables.
        
        Returns:
            Dictionary of current user variables
        """
        return self._user_variables.copy()
    
    def update_user_variables_from_globals(self, globals_dict: Dict[str, Any]) -> None:
        """
        Extract and update user variables from the globals dictionary after code execution.
        This ensures that any modifications to user variables during code execution are preserved.
        
        Args:
            globals_dict: The globals dictionary after code execution
        """
        if not globals_dict or not self._user_variables:
            return
            
        # Update user variables with values from globals
        for var_name in list(self._user_variables.keys()):
            if var_name in globals_dict:
                try:
                    # Try to serialize the value to ensure it's valid
                    cloudpickle.dumps(globals_dict[var_name])
                    # Update the user variable with the new value
                    self._user_variables[var_name] = globals_dict[var_name]
                except Exception:
                    # If serialization fails, keep the old value
                    pass
                    
        # Check for new variables that might have been created
        # This handles cases where LLM creates new variables that should be preserved
        for var_name, var_value in globals_dict.items():
            # Skip special variables, modules, and functions
            if (var_name.startswith('__') or 
                var_name in ['builtins', 'cloudpickle'] or
                callable(var_value) or
                var_name in self._user_variables):
                continue
                
            try:
                # Try to serialize the value to ensure it's valid
                cloudpickle.dumps(var_value)
                # Add the new variable to user variables
                self._user_variables[var_name] = var_value
            except Exception:
                # If serialization fails, skip this variable
                pass 
    
    def shell_response_to_llm_understandable(self, response: Dict[str, Any]) -> str:
        """
        Convert a shell command response to a format that is understandable by the LLM.
        """
        if response.get('stderr',None) not in [None,""]:
            error_message = "Bash Error: " + response['stderr']
            if "No such file or directory" in response['stderr']:
                error_message.replace("No such file or directory", "No such file or directory, Have you provided the correct absolute path? If you are unsure use ls first to make sure the path exists")
            if "Command timed out after" in response['stderr']:
                error_message += ", Make sure your command is specific enough. And only if it is the most specific and optimized command then try to increase the timeout parameter if you need to more time for this command."
            return error_message
        else:
            return response['stdout']
    
    # File operation methods for sandbox-constrained file manipulation
    @abstractmethod
    async def read_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        Read file within sandbox boundaries.
        
        Args:
            file_path: Path to the file
            start_line: Starting line number (1-based)
            max_lines: Maximum lines to read
            encoding: File encoding
            
        Returns:
            {
                "success": bool,
                "content": str | None,
                "path": str,
                "size": int,
                "error": str | None
            }
        """
        pass
    
    @abstractmethod 
    async def write_file(self, file_path: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Write file within sandbox boundaries.
        
        Args:
            file_path: Path to the target file
            content: Content to write
            create_dirs: Create parent directories if needed
            encoding: File encoding
            
        Returns:
            {
                "success": bool,
                "path": str,
                "bytes_written": int,
                "operation": str,
                "error": str | None
            }
        """
        pass
    
    @abstractmethod
    async def update_file(self, file_path: str, old_content: str, new_content: str, **kwargs) -> Dict[str, Any]:
        """
        Update file content with exact string replacement.
        
        Args:
            file_path: Path to the file
            old_content: Exact content to replace
            new_content: Replacement content
            expected_matches: Expected number of matches
            
        Returns:
            {
                "success": bool,
                "path": str,
                "changes_made": bool,
                "old_content": str,
                "new_content": str,
                "bytes_written": int,
                "error": str | None
            }
        """
        pass
    

        """
        Search files within sandbox boundaries.
        
        Args:
            pattern: Search pattern
            directory: Directory to search
            file_types: File extensions to include
            case_sensitive: Case-sensitive search
            regex: Treat pattern as regex
            
        Returns:
            {
                "success": bool,
                "matches": List[Dict[str, Any]],
                "pattern": str,
                "directory": str,
                "error": str | None
            }
        """
        pass