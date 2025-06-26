from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
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