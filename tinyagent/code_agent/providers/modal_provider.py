import sys
import modal
import cloudpickle
from pprint import pprint
from typing import Dict, List, Any, Optional, Union
from .base import CodeExecutionProvider
from ..utils import clean_response, make_session_blob, _run_python, _run_shell
try:
    from ..modal_sandbox import COLOR
except ImportError:
    # Fallback colors if modal_sandbox is not available
    COLOR = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "ENDC": "\033[0m",
}



class ModalProvider(CodeExecutionProvider):
    """
    Modal-based code execution provider.
    
    This provider uses Modal.com to execute Python code in a remote, sandboxed environment.
    It provides scalable, secure code execution with automatic dependency management.
    Can also run locally for development/testing purposes using Modal's native .local() method.
    """
    
    PYTHON_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}"
    TIMEOUT_MAX = 120
    
    def __init__(
        self,
        log_manager,
        default_python_codes: Optional[List[str]] = None,
        code_tools: List[Dict[str, Any]] = None,
        pip_packages: List[str] | None = None,
        default_packages: Optional[List[str]] = None,
        apt_packages: Optional[List[str]] = None,
        python_version: Optional[str] = None,
        authorized_imports: list[str] | None = None,
        authorized_functions: list[str] | None = None,
        modal_secrets: Dict[str, Union[str, None]] | None = None,
        lazy_init: bool = True,
        sandbox_name: str = "tinycodeagent-sandbox",
        local_execution: bool = False,
        check_string_obfuscation: bool = True,
        bypass_shell_safety: bool = False,  # Default to False for ModalProvider
        additional_safe_shell_commands: Optional[List[str]] = None,
        additional_safe_control_operators: Optional[List[str]] = None,
        **kwargs
    ):
        """
        Initialize Modal-based code execution provider.
        
        Args:
            log_manager: Log manager instance
            default_python_codes: List of Python code snippets to execute before user code
            code_tools: List of code tools to make available
            pip_packages: List of pip packages to install in the sandbox
            default_packages: List of default pip packages to install in the sandbox
            apt_packages: List of apt packages to install in the sandbox
            python_version: Python version to use in the sandbox
            authorized_imports: Optional allow-list of modules the user code is permitted to import
            authorized_functions: Optional allow-list of dangerous functions the user code is permitted to use
            modal_secrets: Dictionary of secrets to make available to the sandbox
            lazy_init: Whether to initialize Modal app lazily
            sandbox_name: Name of the Modal sandbox
            local_execution: Whether to execute code locally
            check_string_obfuscation: If True (default), check for string obfuscation techniques. Set to False to allow legitimate use of base64 encoding and other string manipulations.
            bypass_shell_safety: If True, bypass shell command safety checks (default: False for modal)
            additional_safe_shell_commands: Additional shell commands to consider safe
            additional_safe_control_operators: Additional shell control operators to consider safe
            **kwargs: Additional keyword arguments
        
        Note:
            The Modal sandbox is a secure environment for executing untrusted code.
            It provides isolation from the host system and other sandboxes.
            
            Default packages are always installed, while pip_packages are added to
                (git, curl, …) so you only need to specify the extras.
            python_version: Python version used for the sandbox image. If
                ``None`` the current interpreter version is used.
            authorized_imports: Optional allow-list of modules the user code is permitted to import. Supports wildcard patterns (e.g. "pandas.*"). If ``None`` the safety layer blocks only the predefined dangerous modules.
        """

        # Resolve default values ------------------------------------------------
        if default_packages is None:
            default_packages = [
                "cloudpickle",
                "requests",
                "tinyagent-py[all]",
                "gradio",
                "arize-phoenix-otel",
            ]

        if apt_packages is None:
            apt_packages = ["git", "curl", "nodejs", "npm","ripgrep"]

        if python_version is None:
            python_version = self.PYTHON_VERSION

        # Keep references so callers can introspect / mutate later -------------
        self.default_packages: List[str] = default_packages
        self.apt_packages: List[str] = apt_packages
        self.python_version: str = python_version
        self.authorized_imports = authorized_imports

        self.authorized_functions = authorized_functions or []
        self.check_string_obfuscation = check_string_obfuscation
        # ----------------------------------------------------------------------
        final_packages = list(set(self.default_packages + (pip_packages or [])))
        
        super().__init__(
            log_manager=log_manager,
            default_python_codes=default_python_codes or [],
            code_tools=code_tools or [],
            pip_packages=final_packages,
            secrets=modal_secrets or {},
            lazy_init=lazy_init,
            bypass_shell_safety=bypass_shell_safety,
            additional_safe_shell_commands=additional_safe_shell_commands,
            additional_safe_control_operators=additional_safe_control_operators,
            **kwargs
        )
        
        self.sandbox_name = sandbox_name
        self.local_execution = local_execution
        self.modal_secrets = modal.Secret.from_dict(self.secrets)
        self.app = None
        self._app_run_python = None
        self._app_run_shell = None
        self.is_trusted_code = kwargs.get("trust_code", False)
        
        self._setup_modal_app()
        
    def _setup_modal_app(self):
        """Set up the Modal application and functions."""
        execution_mode = "🏠 LOCAL" if self.local_execution else "☁️ REMOTE"
        print(f"{execution_mode} ModalProvider setting up Modal app")
        
        agent_image = modal.Image.debian_slim(python_version=self.python_version)

        # Install APT packages first (if any were requested)
        if self.apt_packages:
            agent_image = agent_image.apt_install(*self.apt_packages)

        # Then install pip packages (including the union of default + user)
        agent_image = agent_image.pip_install(*self.pip_packages)
        
        self.app = modal.App(
            name=self.sandbox_name,
            image=agent_image,
            secrets=[self.modal_secrets]
        )
        
        self._app_run_python = self.app.function()(_run_python)
        self._app_run_shell = self.app.function()(_run_shell)
        
        # Add tools if provided
        if self.code_tools:
            self.add_tools(self.code_tools)
    
    async def execute_python(self, code_lines: List[str], timeout: int = 120) -> Dict[str, Any]:
        """
        Execute Python code using Modal's native .local() or .remote() methods.
        
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
        print("##########################################code##########################################")
        print(full_code)
        print("#" * 100)

        
        # Use Modal's native execution methods
        response = self._python_executor(full_code, self._globals_dict, self._locals_dict)
        
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!<response>!!!!!!!!!!!!!!!!!!!!!!!!!")
        
        # Always update globals and locals dictionaries, regardless of whether there was an error
        # This ensures variables are preserved even when code execution fails
        try:
            # Update globals and locals from the response
            if "updated_globals" in response:
                self._globals_dict = cloudpickle.loads(make_session_blob(response["updated_globals"]))
                
            if "updated_locals" in response:
                self._locals_dict = cloudpickle.loads(make_session_blob(response["updated_locals"]))
                
            # Update user variables from the updated globals and locals
            # This preserves any changes made to variables by the LLM
            self.update_user_variables_from_globals(self._globals_dict)
            self.update_user_variables_from_globals(self._locals_dict)
        except Exception as e:
            print(f"Warning: Failed to update globals/locals after execution: {str(e)}")
        
        self._log_response(response)
        
        return clean_response(response)
    
    async def execute_shell(
        self,
        command: List[str],
        timeout: int = 30,
        workdir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a shell command securely using Modal.
        
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
        # First, check if the command is safe to execute
        timeout = min(timeout, self.TIMEOUT_MAX)
        if type(command) == str:
            command = command.split(" ")

        print("#########################<Bash>#########################")
        print(f"{COLOR['BLUE']}>{command}{COLOR['ENDC']}")
        safety_check = self.is_safe_command(command)
        if not safety_check["safe"]:
            
            response = {
                "stdout": "",
                "stderr": f"Command rejected for security reasons: {safety_check.get('reason', 'Unsafe command')}",
                "exit_code": 1
            }
            print(f"{COLOR['RED']}{response['stderr']}{COLOR['ENDC']}")
            return response
        #execution_mode = "🏠 LOCALLY" if self.local_execution else "☁️ REMOTELY"
        #print(f"Executing shell command {execution_mode} via Modal: {' '.join(command)}")
        
        # Show working directory information
        if workdir:
            print(f"Working directory: {workdir}")
        
        # If using Modal for remote execution
        if not self.local_execution:
            try:
                with self.app.run():
                    result = self._app_run_shell.remote(
                        command=command,
                        timeout=timeout,
                        workdir=workdir
                    )
                
                
                print(f"{COLOR['GREEN']}{result}{COLOR['ENDC']}")
                return result
            except Exception as e:
                response = {
                    "stdout": "",
                    "stderr": f"Error executing shell command: {str(e)}",
                    "exit_code": 1
                }
                
                print(f"{COLOR['RED']}{response['stderr']}{COLOR['ENDC']}")
                return response
        # If executing locally
        else:
            try:
                result = self._app_run_shell.local(
                    command=command,
                    timeout=timeout,
                    workdir=workdir
                )
                print(f"{COLOR['GREEN']}{result}{COLOR['ENDC']}")
                return result
            except Exception as e:
                response = {
                    "stdout": "",
                    "stderr": f"Error executing shell command: {str(e)}",
                    "exit_code": 1
                }
                print(f"{COLOR['RED']}{response['stderr']}{COLOR['ENDC']}")
                return response
    
    def _python_executor(self, code: str, globals_dict: Dict[str, Any] = None, locals_dict: Dict[str, Any] = None):
        """Execute Python code using Modal's native .local() or .remote() methods."""
        execution_mode = "🏠 LOCALLY" if self.local_execution else "☁️ REMOTELY"
        print(f"Executing code {execution_mode} via Modal")
        
        # Prepare the full code with default codes if needed
        if self.executed_default_codes:
            print("✔️ default codes already executed")
            full_code = "\n".join(self.code_tools_definitions) +"\n\n"+code
            # Code tools and default code are trusted, user code is not
        else:
            full_code = "\n".join(self.code_tools_definitions) +"\n\n"+ "\n".join(self.default_python_codes) + "\n\n" + code
            self.executed_default_codes = True
            # First execution includes framework code which is trusted
        
        # Use Modal's native execution methods
        if self.local_execution:
            return self._app_run_python.local(
                full_code,
                globals_dict or {},
                locals_dict or {},
                authorized_imports=self.authorized_imports,
                authorized_functions=self.authorized_functions,
                trusted_code=self.is_trusted_code,
                check_string_obfuscation=self.check_string_obfuscation,
            )
        else:
            with self.app.run():
                return self._app_run_python.remote(
                    full_code,
                    globals_dict or {},
                    locals_dict or {},
                    authorized_imports=self.authorized_imports,
                    authorized_functions=self.authorized_functions,
                    trusted_code=self.is_trusted_code,
                    check_string_obfuscation=self.check_string_obfuscation,
                )
    
    def _log_response(self, response: Dict[str, Any]):
        """Log the response from code execution."""
        execution_mode = "🏠 LOCAL" if self.local_execution else "☁️ REMOTE"
        print(f"#########################{execution_mode} EXECUTION#########################")
        print("#########################<printed_output>#########################")
        print(response["printed_output"])
        print("#########################</printed_output>#########################")
        if response.get("return_value",None) not in [None,""]:
            print("#########################<return_value>#########################")
            print(response["return_value"])
            print("#########################</return_value>#########################")
        if response.get("stderr",None) not in [None,""]:
            print("#########################<stderr>#########################")
            print(response["stderr"])
            print("#########################</stderr>#########################")
        if response.get("error_traceback",None) not in [None,""]:
            print("#########################<traceback>#########################")
            # Check if this is a security exception and highlight it in red if so
            error_text = response["error_traceback"]
            if "SECURITY" in error_text:
                
                print(f"{COLOR['RED']}{error_text}{COLOR['ENDC']}")
            else:
                print(error_text)
            print("#########################</traceback>#########################")
    
    async def cleanup(self):
        """Clean up Modal resources."""
        # Modal handles cleanup automatically, but we can reset state
        self.executed_default_codes = False
        self._globals_dict = {}
        self._locals_dict = {}
    
    # File operation methods for sandbox-constrained file manipulation
    async def read_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """Read file within Modal sandbox boundaries."""
        code = f"""
import os
import mimetypes
from pathlib import Path

def read_file_impl(file_path, start_line=1, max_lines=None, encoding='utf-8'):
    try:
        # Basic path validation
        if not file_path or '..' in file_path:
            return {{
                "success": False,
                "error": "Invalid file path",
                "path": file_path,
                "size": 0
            }}
        
        # Check if file exists
        if not os.path.exists(file_path):
            return {{
                "success": False,
                "error": "File not found",
                "path": file_path,
                "size": 0
            }}
        
        # Check if it's a file (not directory)
        if not os.path.isfile(file_path):
            return {{
                "success": False,
                "error": "Path is not a file",
                "path": file_path,
                "size": 0
            }}
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Check for reasonable file size (100MB limit)
        if file_size > 100 * 1024 * 1024:
            return {{
                "success": False,
                "error": f"File too large: {{file_size}} bytes (limit: 100MB)",
                "path": file_path,
                "size": file_size
            }}
        
        # Check if it's a text file
        def is_text_file(path):
            try:
                mime_type, _ = mimetypes.guess_type(path)
                if mime_type and mime_type.startswith('text/'):
                    return True
                
                text_extensions = {{
                    '.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml',
                    '.md', '.rst', '.csv', '.sql', '.sh', '.bash', '.zsh', '.fish',
                    '.c', '.cpp', '.h', '.java', '.go', '.rs', '.php', '.rb', '.pl',
                    '.ts', '.jsx', '.tsx', '.vue', '.svelte', '.ini', '.cfg', '.conf',
                    '.log', '.dockerfile', '.gitignore', '.env'
                }}
                
                if Path(path).suffix.lower() in text_extensions:
                    return True
                
                # Check first few bytes for null bytes
                with open(path, 'rb') as f:
                    sample = f.read(1024)
                    if b'\\0' in sample:
                        return False
                    
                    try:
                        sample.decode('utf-8')
                        return True
                    except UnicodeDecodeError:
                        return False
            except Exception:
                return False
        
        if not is_text_file(file_path):
            return {{
                "success": False,
                "error": "This file appears to be binary. I can only read text-based files like source code, configuration files, and documentation.",
                "path": file_path,
                "size": file_size
            }}
        
        # Read the file
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                if start_line > 1:
                    # Skip lines before start_line
                    for _ in range(start_line - 1):
                        try:
                            next(f)
                        except StopIteration:
                            break
                
                lines = []
                line_count = 0
                for line in f:
                    lines.append(line.rstrip('\\n\\r'))
                    line_count += 1
                    if max_lines and line_count >= max_lines:
                        break
                
                content = '\\n'.join(lines)
                
                return {{
                    "success": True,
                    "content": content,
                    "path": file_path,
                    "size": file_size,
                    "error": None
                }}
        
        except UnicodeDecodeError as e:
            return {{
                "success": False,
                "error": f"Could not decode file with encoding '{{encoding}}': {{str(e)}}",
                "path": file_path,
                "size": file_size
            }}
        except Exception as e:
            return {{
                "success": False,
                "error": f"Error reading file: {{str(e)}}",
                "path": file_path,
                "size": file_size
            }}
    
    except Exception as e:
        return {{
            "success": False,
            "error": f"Unexpected error: {{str(e)}}",
            "path": file_path,
            "size": 0
        }}

# Execute the file read
result = read_file_impl("{file_path}", {kwargs.get('start_line', 1)}, {kwargs.get('max_lines', None)}, "{kwargs.get('encoding', 'utf-8')}")
print(f"FILE_READ_RESULT: {{result}}")
"""
        
        try:
            response = await self.execute_python([code])
            # Extract result from printed output
            import re
            output = response.get("printed_output", "")
            match = re.search(r"FILE_READ_RESULT: (.+)", output)
            if match:
                import ast
                result = ast.literal_eval(match.group(1))
                return result
            else:
                return {
                    "success": False,
                    "error": "Could not parse file read result",
                    "path": file_path,
                    "size": 0
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing file read: {str(e)}",
                "path": file_path,
                "size": 0
            }
    
    async def write_file(self, file_path: str, content: str, **kwargs) -> Dict[str, Any]:
        """Write file within Modal sandbox boundaries."""
        create_dirs = kwargs.get('create_dirs', True)
        encoding = kwargs.get('encoding', 'utf-8')
        
        # Prepare content for safe insertion into Python code
        content_repr = repr(content)
        
        code = f"""
import os
from pathlib import Path

def write_file_impl(file_path, content, create_dirs=True, encoding='utf-8'):
    try:
        # Basic path validation
        if not file_path or '..' in file_path:
            return {{
                "success": False,
                "error": "Invalid file path",
                "path": file_path,
                "bytes_written": 0,
                "operation": "write"
            }}
        
        file_path_obj = Path(file_path)
        
        # Create parent directories if needed
        if create_dirs and not file_path_obj.parent.exists():
            try:
                file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return {{
                    "success": False,
                    "error": f"Could not create parent directories: {{str(e)}}",
                    "path": file_path,
                    "bytes_written": 0,
                    "operation": "write"
                }}
        
        # Determine operation before writing
        existed_before = file_path_obj.exists()

        # Write the file
        try:
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)
            
            bytes_written = len(content.encode(encoding))
            operation = "created" if not existed_before else "overwritten"
            
            return {{
                "success": True,
                "path": file_path,
                "bytes_written": bytes_written,
                "operation": operation,
                "error": None
            }}
        
        except Exception as e:
            return {{
                "success": False,
                "error": f"Error writing file: {{str(e)}}",
                "path": file_path,
                "bytes_written": 0,
                "operation": "write"
            }}
    
    except Exception as e:
        return {{
            "success": False,
            "error": f"Unexpected error: {{str(e)}}",
            "path": file_path,
            "bytes_written": 0,
            "operation": "write"
        }}

# Execute the file write
result = write_file_impl({repr(file_path)}, {content_repr}, {create_dirs}, {repr(encoding)})
print("FILE_WRITE_RESULT:", result)
"""
        
        try:
            response = await self.execute_python([code])
            if self.log_manager:
                self.log_manager.get_logger('tinyagent.code_agent.providers.modal_provider').debug(f"ModalProvider.write_file raw response: {response}")
            
            # Extract result from printed output
            import re
            output = response.get("printed_output", "")
            match = re.search(r"FILE_WRITE_RESULT: (.+)", output)
            if match:
                import ast
                result = ast.literal_eval(match.group(1))
                return result
            else:
                return {
                    "success": False,
                    "error": "Could not parse file write result",
                    "path": file_path,
                    "bytes_written": 0,
                    "operation": "write"
                }
        except Exception as e:
            if self.log_manager:
                self.log_manager.get_logger('tinyagent.code_agent.providers.modal_provider').debug(f"ModalProvider.write_file exception: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Error executing file write: {str(e)}",
                "path": file_path,
                "bytes_written": 0,
                "operation": "write"
            }
    
    async def update_file(self, file_path: str, old_content: str, new_content: str, **kwargs) -> Dict[str, Any]:
        """Update file content with exact string replacement within Modal sandbox."""
        expected_matches = kwargs.get('expected_matches', 1)
        
        code = f"""
import os

def update_file_impl(file_path, old_content, new_content, expected_matches=1):
    try:
        # Basic path validation
        if not file_path or '..' in file_path:
            return {{
                "success": False,
                "error": "Invalid file path",
                "path": file_path,
                "changes_made": False,
                "old_content": old_content,
                "new_content": new_content,
                "bytes_written": 0
            }}
        
        # Check if file exists
        if not os.path.exists(file_path):
            return {{
                "success": False,
                "error": "File not found",
                "path": file_path,
                "changes_made": False,
                "old_content": old_content,
                "new_content": new_content,
                "bytes_written": 0
            }}
        
        # Read current content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        except Exception as e:
            return {{
                "success": False,
                "error": f"Error reading file: {{str(e)}}",
                "path": file_path,
                "changes_made": False,
                "old_content": old_content,
                "new_content": new_content,
                "bytes_written": 0
            }}
        
        # Count occurrences of old_content
        match_count = current_content.count(old_content)
        
        if match_count == 0:
            return {{
                "success": False,
                "error": "Old content not found in file",
                "path": file_path,
                "changes_made": False,
                "old_content": old_content,
                "new_content": new_content,
                "bytes_written": 0
            }}
        
        if match_count != expected_matches:
            return {{
                "success": False,
                "error": f"Expected {{expected_matches}} matches but found {{match_count}}",
                "path": file_path,
                "changes_made": False,
                "old_content": old_content,
                "new_content": new_content,
                "bytes_written": 0
            }}
        
        # Perform replacement
        updated_content = current_content.replace(old_content, new_content)
        
        # Write back to file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            bytes_written = len(updated_content.encode('utf-8'))
            
            return {{
                "success": True,
                "path": file_path,
                "changes_made": True,
                "old_content": old_content,
                "new_content": new_content,
                "bytes_written": bytes_written,
                "error": None
            }}
        
        except Exception as e:
            return {{
                "success": False,
                "error": f"Error writing updated file: {{str(e)}}",
                "path": file_path,
                "changes_made": False,
                "old_content": old_content,
                "new_content": new_content,
                "bytes_written": 0
            }}
    
    except Exception as e:
        return {{
            "success": False,
            "error": f"Unexpected error: {{str(e)}}",
            "path": file_path,
            "changes_made": False,
            "old_content": old_content,
            "new_content": new_content,
            "bytes_written": 0
        }}

# Execute the file update
result = update_file_impl({repr(file_path)}, {repr(old_content)}, {repr(new_content)}, {expected_matches})
print("FILE_UPDATE_RESULT:", result)
"""
        
        try:
            response = await self.execute_python([code])
            # Extract result from printed output
            import re
            output = response.get("printed_output", "")
            match = re.search(r"FILE_UPDATE_RESULT: (.+)", output)
            if match:
                import ast
                result = ast.literal_eval(match.group(1))
                return result
            else:
                return {
                    "success": False,
                    "error": "Could not parse file update result",
                    "path": file_path,
                    "changes_made": False,
                    "old_content": old_content,
                    "new_content": new_content,
                    "bytes_written": 0
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error executing file update: {str(e)}",
                "path": file_path,
                "changes_made": False,
                "old_content": old_content,
                "new_content": new_content,
                "bytes_written": 0
            }
 