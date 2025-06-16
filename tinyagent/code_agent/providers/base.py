from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from tinyagent.hooks.logging_manager import LoggingManager


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
        import cloudpickle
        
        tools_str_list = ["import cloudpickle"]
        tools_str_list.append("###########<tools>###########\n")
        for tool in tools:
            tools_str_list.append(
                f"globals()['{tool._tool_metadata['name']}'] = cloudpickle.loads({cloudpickle.dumps(tool)})"
            )
        tools_str_list.append("\n\n")
        tools_str_list.append("###########</tools>###########\n")
        tools_str_list.append("\n\n")
        self.default_python_codes.extend(tools_str_list) 