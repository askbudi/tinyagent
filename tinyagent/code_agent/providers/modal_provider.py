import sys
import modal
import cloudpickle
from typing import Dict, List, Any, Optional, Union
from .base import CodeExecutionProvider
from ..utils import clean_response, make_session_blob, _run_python


class ModalProvider(CodeExecutionProvider):
    """
    Modal-based code execution provider.
    
    This provider uses Modal.com to execute Python code in a remote, sandboxed environment.
    It provides scalable, secure code execution with automatic dependency management.
    """
    
    PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
    
    def __init__(
        self,
        log_manager,
        default_python_codes: Optional[List[str]] = None,
        code_tools: List[Dict[str, Any]] = None,
        pip_packages: List[str] = None,
        modal_secrets: Dict[str, Union[str, None]] = None,
        lazy_init: bool = True,
        sandbox_name: str = "tinycodeagent-sandbox",
        **kwargs
    ):
        # Set up default packages
        default_packages = [
            "cloudpickle",
            "requests", 
            "tinyagent-py[all]",
            "gradio",
            "arize-phoenix-otel"
        ]
        final_packages = list(set(default_packages + (pip_packages or [])))
        
        super().__init__(
            log_manager=log_manager,
            default_python_codes=default_python_codes or [],
            code_tools=code_tools or [],
            pip_packages=final_packages,
            secrets=modal_secrets or {},
            lazy_init=lazy_init,
            **kwargs
        )
        
        self.sandbox_name = sandbox_name
        self.modal_secrets = modal.Secret.from_dict(self.secrets)
        self.app = None
        self._app_run_python = None
        
        self._setup_modal_app()
        
    def _setup_modal_app(self):
        """Set up the Modal application and functions."""
        agent_image = modal.Image.debian_slim(python_version=self.PYTHON_VERSION).pip_install(
            *self.pip_packages
        )
        
        self.app = modal.App(
            name=self.sandbox_name,
            image=agent_image,
            secrets=[self.modal_secrets]
        )
        
        self._app_run_python = self.app.function()(_run_python)
        
        # Add tools if provided
        if self.code_tools:
            self.add_tools(self.code_tools)
    
    async def execute_python(self, code_lines: List[str], timeout: int = 120) -> Dict[str, Any]:
        """
        Execute Python code using Modal.
        
        Args:
            code_lines: List of Python code lines to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            Dictionary containing execution results
        """
        if isinstance(code_lines, str):
            code_lines = [code_lines]
        
        full_code = "\n".join(code_lines)
        
        print("#" * 100)
        print("#########################code#########################")
        print(full_code)
        print("#" * 100)
        
        # Execute the code
        response = self._python_executor(full_code, self._globals_dict, self._locals_dict)
        
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!<response>!!!!!!!!!!!!!!!!!!!!!!!!!")
        
        # Update the instance globals and locals with the execution results
        self._globals_dict = cloudpickle.loads(make_session_blob(response["updated_globals"]))
        self._locals_dict = cloudpickle.loads(make_session_blob(response["updated_locals"]))
        
        self._log_response(response)
        
        return clean_response(response)
    
    def _python_executor(self, code: str, globals_dict: Dict[str, Any] = None, locals_dict: Dict[str, Any] = None):
        """Execute Python code using Modal."""
        with self.app.run():
            if self.executed_default_codes:
                print("✔️ default codes already executed")
                full_code = code
            else:
                full_code = "\n".join(self.default_python_codes) + "\n\n" + code
                self.executed_default_codes = True
            
            return self._app_run_python.remote(full_code, globals_dict or {}, locals_dict or {})
    
    def _log_response(self, response: Dict[str, Any]):
        """Log the response from code execution."""
        print("#########################<printed_output>#########################")
        print(response["printed_output"])
        print("#########################</printed_output>#########################")
        print("#########################<return_value>#########################")
        print(response["return_value"])
        print("#########################</return_value>#########################")
        print("#########################<stderr>#########################")
        print(response["stderr"])
        print("#########################</stderr>#########################")
        print("#########################<traceback>#########################")
        print(response["error_traceback"])
        print("#########################</traceback>#########################")
    
    async def cleanup(self):
        """Clean up Modal resources."""
        # Modal handles cleanup automatically, but we can reset state
        self.executed_default_codes = False
        self._globals_dict = {}
        self._locals_dict = {} 