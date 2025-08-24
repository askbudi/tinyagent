import os
import sys
import asyncio
import tempfile
import platform
import subprocess
import cloudpickle
import json
import re
import shutil
import shlex
from typing import Dict, List, Any, Optional
from pathlib import Path

from tinyagent.hooks.logging_manager import LoggingManager
from .base import CodeExecutionProvider
from ..utils import clean_response, make_session_blob

# Define colors for output formatting
COLOR = {
    "HEADER": "\033[95m",
    "BLUE": "\033[94m",
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "ENDC": "\033[0m",
}

# Regular expression to strip ANSI color codes
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi_codes(text):
    """
    Remove ANSI color and style codes from text.
    
    Args:
        text: Text that may contain ANSI escape sequences
        
    Returns:
        Clean text without ANSI codes
    """
    return ANSI_ESCAPE.sub('', text)


class SeatbeltProvider(CodeExecutionProvider):
    """
    A code execution provider that uses macOS's sandbox-exec (seatbelt) for sandboxed execution.
    
    This provider executes Python code and shell commands within a macOS sandbox for enhanced security.
    It only works on macOS systems and requires local execution.
    """
    
    def __init__(
        self,
        log_manager: Optional[LoggingManager] = None,
        code_tools: List[Any] = None,
        seatbelt_profile: Optional[str] = None,
        seatbelt_profile_path: Optional[str] = None,
        python_env_path: Optional[str] = None,
        authorized_imports: list[str] | None = None,
        authorized_functions: list[str] | None = None,
        check_string_obfuscation: bool = True,
        bypass_shell_safety: bool = True,  # Default to True for SeatbeltProvider
        additional_safe_shell_commands: Optional[List[str]] = None,
        additional_safe_control_operators: Optional[List[str]] = None,
        additional_read_dirs: Optional[List[str]] = None,  # New parameter for additional read directories
        additional_write_dirs: Optional[List[str]] = None,  # New parameter for additional write directories
        environment_variables: Optional[Dict[str, str]] = None,  # New parameter for environment variables
        **kwargs
    ):
        """
        Initialize the SeatbeltProvider.
        
        Args:
            log_manager: Optional logging manager
            code_tools: List of tools available in the Python execution environment
            seatbelt_profile: String containing seatbelt profile rules
            seatbelt_profile_path: Path to a file containing seatbelt profile rules
            python_env_path: Path to the Python environment to use
            authorized_imports: Optional allow-list of modules the user code is permitted to import
            authorized_functions: Optional allow-list of dangerous functions the user code is permitted to use
            check_string_obfuscation: If True, check for string obfuscation techniques
            bypass_shell_safety: If True, bypass shell command safety checks (default: True for seatbelt)
            additional_safe_shell_commands: Additional shell commands to consider safe
            additional_safe_control_operators: Additional shell control operators to consider safe
            additional_read_dirs: List of additional directories to allow read access to
            additional_write_dirs: List of additional directories to allow write access to
            environment_variables: Dictionary of environment variables to make available in the sandbox
            **kwargs: Additional arguments passed to CodeExecutionProvider
        """
        # Initialize logger first to avoid AttributeError
        self.logger = None
        if log_manager:
            self.logger = log_manager.get_logger('tinyagent.code_agent.providers.seatbelt_provider')
        
        super().__init__(
            log_manager=log_manager, 
            code_tools=code_tools,
            bypass_shell_safety=bypass_shell_safety,
            additional_safe_shell_commands=additional_safe_shell_commands,
            additional_safe_control_operators=additional_safe_control_operators,
            **kwargs
        )
        
        # Check if running on macOS
        if platform.system() != "Darwin":
            raise RuntimeError("SeatbeltProvider only works on macOS systems")
        
        # Store additional read/write directories
        self.additional_read_dirs = additional_read_dirs or []
        self.additional_write_dirs = additional_write_dirs or []
        
        # Expand and normalize paths to avoid issues with symlinks and relative paths
        self.additional_read_dirs = [os.path.abspath(os.path.expanduser(path)) for path in self.additional_read_dirs]
        self.additional_write_dirs = [os.path.abspath(os.path.expanduser(path)) for path in self.additional_write_dirs]
        
        # Store environment variables
        self.environment_variables = environment_variables.copy() if environment_variables else {}
        
        # Set up seatbelt profile
        self.seatbelt_profile = seatbelt_profile
        self.seatbelt_profile_path = seatbelt_profile_path
        
        # If neither profile nor path is provided, use a default restrictive profile
        if not self.seatbelt_profile and not self.seatbelt_profile_path:
            self.seatbelt_profile = self._get_default_seatbelt_profile()
        
        # If a profile string is provided but no path, write it to a temporary file
        if self.seatbelt_profile and not self.seatbelt_profile_path:
            self._write_seatbelt_profile_to_temp_file()
        
        # Set Python environment path
        self.python_env_path = python_env_path
        
        # Safety settings - by default, more permissive than Modal/local
        self.authorized_imports = authorized_imports
        self.authorized_functions = authorized_functions or []
        self.check_string_obfuscation = check_string_obfuscation
        self.is_trusted_code = kwargs.get("trust_code", False)

        # Create a sandbox-safe temp directory for all transient files used by the sandboxed process
        # We intentionally choose /private/tmp because the default macOS sandbox profile may not allow
        # the per-user TMPDIR path under /var/folders, and our default profile already allows /private/tmp.
        try:
            self.sandbox_tmp_dir = os.path.join("/private/tmp", f"tinyagent_{os.getpid()}")
            os.makedirs(self.sandbox_tmp_dir, exist_ok=True)
        except Exception as e:
            # Fallback to current working directory if creation fails
            self.sandbox_tmp_dir = os.getcwd()
            if self.logger:
                self.logger.warning("Falling back to CWD for sandbox temp dir due to error: %s", str(e))
        
        # Log initialization
        if self.logger:
            profile_path = self.seatbelt_profile_path or "default profile (not yet written to file)"
            self.logger.info("Initialized SeatbeltProvider with sandbox profile at: %s", profile_path)
            if self.additional_read_dirs:
                self.logger.info("Additional read directories: %s", ", ".join(self.additional_read_dirs))
            if self.additional_write_dirs:
                self.logger.info("Additional write directories: %s", ", ".join(self.additional_write_dirs))
            if self.environment_variables:
                env_keys = list(self.environment_variables.keys())
                self.logger.info("Environment variables: %s", ", ".join(env_keys))
    
    def _ensure_sandbox_tmp_dir(self):
        """
        Ensure that the sandbox temporary directory exists.
        
        This method checks if self.sandbox_tmp_dir exists and recreates it if missing.
        Includes error handling with fallback to current directory.
        """
        try:
            if not os.path.exists(self.sandbox_tmp_dir):
                os.makedirs(self.sandbox_tmp_dir, exist_ok=True)
                if self.logger:
                    self.logger.info("Created sandbox temp directory: %s", self.sandbox_tmp_dir)
        except Exception as e:
            # Fallback to current working directory if creation fails
            old_sandbox_tmp_dir = self.sandbox_tmp_dir
            self.sandbox_tmp_dir = os.getcwd()
            if self.logger:
                self.logger.warning(
                    "Failed to ensure sandbox temp dir '%s', falling back to CWD '%s': %s", 
                    old_sandbox_tmp_dir, self.sandbox_tmp_dir, str(e)
                )
    
    def set_environment_variables(self, env_vars: Dict[str, str]):
        """
        Set environment variables for the sandbox.
        
        Args:
            env_vars: Dictionary of environment variable name -> value pairs
        """
        self.environment_variables = env_vars.copy()
        if self.logger:
            env_keys = list(self.environment_variables.keys())
            self.logger.info("Updated environment variables: %s", ", ".join(env_keys))
    
    def add_environment_variable(self, name: str, value: str):
        """
        Add a single environment variable.
        
        Args:
            name: Environment variable name
            value: Environment variable value
        """
        self.environment_variables[name] = value
        if self.logger:
            self.logger.info("Added environment variable: %s", name)
    
    def remove_environment_variable(self, name: str):
        """
        Remove an environment variable.
        
        Args:
            name: Environment variable name to remove
        """
        if name in self.environment_variables:
            del self.environment_variables[name]
            if self.logger:
                self.logger.info("Removed environment variable: %s", name)
    
    def get_environment_variables(self) -> Dict[str, str]:
        """
        Get a copy of current environment variables.
        
        Returns:
            Dictionary of current environment variables
        """
        return self.environment_variables.copy()
    
    def _get_sandbox_environment(self) -> Dict[str, str]:
        """
        Get the complete environment for sandbox execution.
        
        Returns:
            Dictionary containing all environment variables for the sandbox
        """
        # Start with essential system environment variables
        base_env = {
            'PATH': os.environ.get('PATH', '/usr/bin:/bin:/usr/sbin:/sbin'),
            'HOME': os.environ.get('HOME', '/tmp'),
            'USER': os.environ.get('USER', 'nobody'),
            'TERM': os.environ.get('TERM', 'xterm'),
            'LANG': os.environ.get('LANG', 'en_US.UTF-8'),
            'LC_ALL': os.environ.get('LC_ALL', 'en_US.UTF-8'),
        }

        # Ensure TMPDIR inside the sandbox points to an allowed location
        if getattr(self, 'sandbox_tmp_dir', None):
            base_env['TMPDIR'] = self.sandbox_tmp_dir
        
        # Add Python-specific environment variables if available
        python_vars = ['PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'CONDA_DEFAULT_ENV', 'CONDA_PREFIX']
        for var in python_vars:
            if var in os.environ:
                base_env[var] = os.environ[var]
        
        # Add user-defined environment variables (these can override base ones)
        base_env.update(self.environment_variables)
        
        return base_env
    

    
    def _get_default_seatbelt_profile(self) -> str:
        """
        Get a default restrictive seatbelt profile.
        
        Returns:
            String containing default seatbelt profile rules
        """
        current_dir = os.getcwd()
        home_dir = os.path.expanduser("~")
        temp_dir = tempfile.gettempdir()
        
        # Build additional read directories section
        additional_read_dirs_rules = ""
        for dir_path in self.additional_read_dirs:
            additional_read_dirs_rules += f'  (subpath "{dir_path}")\n'
        
        # Build additional write directories section
        additional_write_dirs_rules = ""
        for dir_path in self.additional_write_dirs:
            additional_write_dirs_rules += f'  (subpath "{dir_path}")\n'
        
        return f"""(version 1)

; Default to deny everything
(deny default)

; Allow network connections with proper DNS resolution
(allow network*)
(allow network-outbound)
(allow mach-lookup)
(allow system-socket)

; Allow process execution
(allow process-exec)
(allow process-fork)
(allow signal (target self))

; Restrict file read to current path and system files
(deny file-read* (subpath "/Users"))
(allow file-read*
  (subpath "{current_dir}")
  (subpath "{home_dir}/.conda")
  (subpath "{home_dir}/.pyenv")
  (subpath "/usr")
  (subpath "/System")
  (subpath "/Library")
  (subpath "/bin")
  (subpath "/sbin")
  (subpath "/opt")
  (subpath "{temp_dir}")
  (subpath "/private/tmp")
  (subpath "/private/var/tmp")
  (subpath "/dev")
  (subpath "/etc")
  (literal "/")
  (literal "/.")
{additional_read_dirs_rules})

; Allow write access to specified folder and temp directories
(deny file-write* (subpath "/"))
(allow file-write*
  (subpath "{current_dir}")
  (subpath "{temp_dir}")
  (subpath "/private/tmp")
  (subpath "/private/var/tmp")
  (subpath "/dev")
{additional_write_dirs_rules})

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

; Allow Git operations
(allow sysctl-read)
(allow file-read-xattr)
(allow file-write-xattr)
(allow file-issue-extension (extension "com.apple.app-sandbox.read"))
(allow file-issue-extension (extension "com.apple.app-sandbox.read-write"))
(allow file-map-executable)
(allow file-read-data)
"""
    
    def _write_seatbelt_profile_to_temp_file(self):
        """
        Write the seatbelt profile to a temporary file.
        """
        try:
            fd, path = tempfile.mkstemp(suffix='.sb', prefix='tinyagent_seatbelt_')
            with os.fdopen(fd, 'w') as f:
                f.write(self.seatbelt_profile)
            self.seatbelt_profile_path = path
            if self.logger:
                self.logger.info("Wrote seatbelt profile to temporary file: %s", path)
        except Exception as e:
            if self.logger:
                self.logger.error("Failed to write seatbelt profile to temporary file: %s", str(e))
            raise RuntimeError(f"Failed to write seatbelt profile: {str(e)}")
    
    async def execute_python(self, code_lines: List[str], timeout: int = 120) -> Dict[str, Any]:
        """
        Execute Python code within a sandbox and return the result.
        
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
        
        # Prepare the full code with tools and default codes if needed
        if self.executed_default_codes:
            print("✔️ default codes already executed")
            complete_code = "\n".join(self.code_tools_definitions) + "\n\n" + full_code
        else:
            complete_code = "\n".join(self.code_tools_definitions) + "\n\n" + "\n".join(self.default_python_codes) + "\n\n" + full_code
            self.executed_default_codes = True
        
        # Ensure sandbox temp directory exists before creating state files
        self._ensure_sandbox_tmp_dir()
        
        # Create a temporary file for the Python state and code
        with tempfile.NamedTemporaryFile(suffix='_state.pkl', prefix='tinyagent_', delete=False, mode='wb', dir=self.sandbox_tmp_dir) as state_file:
            # Serialize the globals and locals dictionaries
            cloudpickle.dump({
                'globals': self._globals_dict,
                'locals': self._locals_dict,
                'authorized_imports': self.authorized_imports,
                'authorized_functions': self.authorized_functions,
                'trusted_code': self.is_trusted_code,
                'check_string_obfuscation': self.check_string_obfuscation
            }, state_file)
            state_file_path = state_file.name
        
        # Create a temporary file for the Python code
        with tempfile.NamedTemporaryFile(suffix='.py', prefix='tinyagent_', delete=False, mode='w', dir=self.sandbox_tmp_dir) as code_file:
            # Write the wrapper script that will execute the code and maintain state
            code_file.write(f"""
import sys
import os
import cloudpickle
import json
import traceback
import io
import contextlib
from pathlib import Path

# Import safety modules if available
try:
    from tinyagent.code_agent.safety import validate_code_safety, function_safety_context
    SAFETY_AVAILABLE = True
except ImportError:
    SAFETY_AVAILABLE = False
    # Define dummy safety functions
    def validate_code_safety(*args, **kwargs):
        pass
    
    def function_safety_context(*args, **kwargs):
        class DummyContext:
            def __enter__(self):
                pass
            def __exit__(self, *args):
                pass
        return DummyContext()

# Load state from the state file
state_path = {repr(state_file_path)}
with open(state_path, 'rb') as f:
    state = cloudpickle.load(f)

globals_dict = state['globals']
locals_dict = state['locals']
authorized_imports = state['authorized_imports']
authorized_functions = state['authorized_functions']
trusted_code = state['trusted_code']
check_string_obfuscation = state['check_string_obfuscation']

# The code to execute
code = r'''
{complete_code}
'''

# Run the code and capture output
def run_code():
    # Static safety analysis if available
    if SAFETY_AVAILABLE:
        validate_code_safety(
            code, 
            authorized_imports=authorized_imports, 
            authorized_functions=authorized_functions, 
            trusted_code=trusted_code,
            check_string_obfuscation=check_string_obfuscation
        )
    
    # Make copies to avoid mutating the original parameters
    updated_globals = globals_dict.copy()
    updated_locals = locals_dict.copy()
    
    # Pre-import essential modules
    essential_modules = ['requests', 'json', 'time', 'datetime', 're', 'random', 'math', 'cloudpickle']
    for module_name in essential_modules:
        try:
            module = __import__(module_name)
            updated_globals[module_name] = module
        except ImportError:
            print(f"⚠️  Warning: {{module_name}} module not available")
    
    # Parse and compile the code
    import ast
    try:
        tree = ast.parse(code, mode="exec")
        compiled = compile(tree, filename="<ast>", mode="exec")
    except SyntaxError as e:
        return {{
            "printed_output": "", 
            "return_value": None, 
            "stderr": "", 
            "error_traceback": f"Syntax error: {{str(e)}}",
            "updated_globals": updated_globals,
            "updated_locals": updated_locals
        }}
    
    # Execute with exception handling
    error_traceback = None
    output = None
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    
    # Merge globals and locals for execution
    merged_globals = updated_globals.copy()
    merged_globals.update(updated_locals)
    
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        try:
            # Add 'exec' to authorized_functions for internal use
            internal_authorized_functions = ['exec', 'eval']
            if authorized_functions is not None and not isinstance(authorized_functions, bool):
                internal_authorized_functions.extend(authorized_functions)
            
            # Execute with safety context if available
            if SAFETY_AVAILABLE:
                with function_safety_context(authorized_functions=internal_authorized_functions, trusted_code=trusted_code):
                    output = exec(compiled, merged_globals)
            else:
                output = exec(compiled, merged_globals)
            
            # Update dictionaries with new variables
            for key, value in merged_globals.items():
                if key not in updated_globals and key not in updated_locals:
                    updated_locals[key] = value
                elif key in updated_locals or key not in updated_globals:
                    updated_locals[key] = value
                updated_globals[key] = value
        except Exception:
            # Capture the full traceback
            error_traceback = traceback.format_exc()
            
            # Update variables even on exception
            for key, value in merged_globals.items():
                if key.startswith('__') or key in ['builtins', 'traceback', 'contextlib', 'io', 'ast', 'sys']:
                    continue
                if key in updated_locals or key not in updated_globals:
                    updated_locals[key] = value
                updated_globals[key] = value
    
    printed_output = stdout_buf.getvalue()
    stderr_output = stderr_buf.getvalue()
    
    return {{
        "printed_output": printed_output, 
        "return_value": output, 
        "stderr": stderr_output, 
        "error_traceback": error_traceback,
        "updated_globals": updated_globals,
        "updated_locals": updated_locals
    }}

# Run the code and get the result
result = run_code()

# Serialize the globals and locals for the next run safely
def _is_picklable(obj):
    try:
        cloudpickle.dumps(obj)
        return True
    except Exception:
        return False

def _sanitize_state_dict(d):
    safe = {{}}
    for k, v in d.items():
        try:
            if k.startswith('__'):
                continue
            if k in ['builtins', 'traceback', 'contextlib', 'io', 'ast', 'sys']:
                continue
            if _is_picklable(v):
                safe[k] = v
        except Exception:
            continue
    return safe

try:
    safe_globals = _sanitize_state_dict(result.get('updated_globals', {{}}))
    safe_locals = _sanitize_state_dict(result.get('updated_locals', {{}}))

    tmp_state_path = state_path + '.tmp'
    with open(tmp_state_path, 'wb') as f:
        cloudpickle.dump({{
            'globals': safe_globals,
            'locals': safe_locals,
            'authorized_imports': authorized_imports,
            'authorized_functions': authorized_functions,
            'trusted_code': trusted_code,
            'check_string_obfuscation': check_string_obfuscation
        }}, f)
    # Atomic replace to avoid truncation on failure
    try:
        os.replace(tmp_state_path, state_path)
    except Exception:
        # Fallback to copy if replace not available
        import shutil as _shutil
        _shutil.copyfile(tmp_state_path, state_path)
        try:
            os.unlink(tmp_state_path)
        except Exception:
            pass
except Exception as _e:
    # If state save fails, continue without blocking result output
    pass

# Clean the result for output
cleaned_result = {{
    "printed_output": result["printed_output"],
    "return_value": result["return_value"],
    "stderr": result["stderr"],
    "error_traceback": result["error_traceback"]
}}

# Print the result as JSON for the parent process to capture
print(json.dumps(cleaned_result))
""")
            code_file_path = code_file.name
        
        try:
            # Prepare the sandbox command
            python_cmd = sys.executable
            if self.python_env_path:
                python_cmd = os.path.join(self.python_env_path, 'bin', 'python')
            
            # Get the complete environment for the sandbox
            sandbox_env = self._get_sandbox_environment()
            
            sandbox_cmd = [
                "sandbox-exec", 
                "-f", self.seatbelt_profile_path, 
                python_cmd, 
                code_file_path
            ]
            
            if self.logger:
                self.logger.debug("Executing Python code in sandbox: %s", " ".join(sandbox_cmd))
            
            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *sandbox_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=sandbox_env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stdout_str = stdout.decode('utf-8', errors='replace')
                stderr_str = stderr.decode('utf-8', errors='replace')
                
                # Try to parse the JSON result from stdout
                try:
                    # The last line should be our JSON result
                    json_result = json.loads(stdout_str.strip())
                    result = json_result
                except json.JSONDecodeError:
                    # If we can't parse JSON, return the raw output
                    result = {
                        "printed_output": stdout_str,
                        "return_value": None,
                        "stderr": stderr_str,
                        "error_traceback": f"Failed to parse result as JSON: {stderr_str}"
                    }
                
                # Load updated state before cleanup
                try:
                    # Check if state file exists before trying to load it
                    if os.path.exists(state_file_path):
                        with open(state_file_path, 'rb') as f:
                            state = cloudpickle.load(f)
                            self._globals_dict = state['globals']
                            self._locals_dict = state['locals']
                            
                        # Update user variables from the updated globals and locals
                        self.update_user_variables_from_globals(self._globals_dict)
                        self.update_user_variables_from_globals(self._locals_dict)
                    else:
                        # State file doesn't exist - this is normal for simple operations
                        if self.logger:
                            self.logger.debug(f"State file not found (normal for simple operations): {state_file_path}")
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Failed to load state from {state_file_path}: {str(e)}")
                    # Don't print warning for file operations as it's not critical
                
                if process.returncode != 0:
                    result["error"] = f"Process exited with code {process.returncode}"
                
                # Log the response
                self._log_response(result)
                
                return clean_response(result)
            
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "printed_output": "",
                    "return_value": None,
                    "stderr": f"Execution timed out after {timeout} seconds",
                    "error_traceback": f"Execution timed out after {timeout} seconds"
                }
        
        except Exception as e:
            if self.logger:
                self.logger.error("Error executing Python in sandbox: %s", str(e))
            return {
                "printed_output": "",
                "return_value": None,
                "stderr": f"Error executing code: {str(e)}",
                "error_traceback": f"Error executing code: {str(e)}"
            }
        
        finally:
            # Clean up the temporary files
            try:
                if os.path.exists(code_file_path):
                    os.unlink(code_file_path)
            except Exception:
                pass
            
            try:
                if os.path.exists(state_file_path):
                    os.unlink(state_file_path)
            except Exception:
                pass
    
    def _log_response(self, response: Dict[str, Any]):
        """Log the response from code execution."""
        print("######################### SEATBELT EXECUTION #########################")
        print("#########################<printed_output>#########################")
        print(response["printed_output"])
        print("#########################</printed_output>#########################")
        if response.get("return_value", None) not in [None, ""]:
            print("#########################<return_value>#########################")
            print(response["return_value"])
            print("#########################</return_value>#########################")
        if response.get("stderr", None) not in [None, ""]:
            print("#########################<stderr>#########################")
            print(response["stderr"])
            print("#########################</stderr>#########################")
        if response.get("error_traceback", None) not in [None, ""]:
            print("#########################<traceback>#########################")
            # Check if this is a security exception and highlight it in red if so
            error_text = response["error_traceback"]
            if "SECURITY" in error_text:
                print(f"{COLOR['RED']}{error_text}{COLOR['ENDC']}")
            else:
                print(error_text)
            print("#########################</traceback>#########################")
    
    
    def _quote_command_for_shell(self, command: List[str]) -> str:
        """
        Properly quote command parts to prevent premature shell expansion of glob patterns.
        
        Args:
            command: List of command parts
            
        Returns:
            Properly quoted command string for shell execution
        """
        quoted_parts = []
        for part in command:
            # Use shlex.quote to properly escape all parts, which will prevent
            # shell expansion of glob patterns until they reach the intended command
            quoted_parts.append(shlex.quote(part))
        
        return ' '.join(quoted_parts)
    
    async def _prepare_git_sandbox_command(self, command: List[str]) -> List[str]:
        """
        Prepare a specialized sandbox command for git operations.
        
        Args:
            command: Git command to execute
            
        Returns:
            List of sandbox command parts
        """
        # Create a temporary directory for git operations
        temp_dir = tempfile.mkdtemp(prefix='tinyagent_git_')
        self._temp_git_dir = temp_dir  # Store for cleanup
        
        # Get GitHub credentials from environment
        github_username = self.environment_variables.get('GITHUB_USERNAME', 'tinyagent')
        github_token = self.environment_variables.get('GITHUB_TOKEN', '')
        git_author_name = self.environment_variables.get('GIT_AUTHOR_NAME', 'TinyAgent')
        git_author_email = self.environment_variables.get('GIT_AUTHOR_EMAIL', 'tinyagent@example.com')
        
        # Create a git config file in the temp directory
        git_config_path = os.path.join(temp_dir, '.gitconfig')
        with open(git_config_path, 'w') as git_config:
            git_config.write(f"""[user]
    name = {git_author_name}
    email = {git_author_email}
[safe]
    directory = *
[http]
    sslVerify = true
[core]
    autocrlf = input
    askpass = /bin/echo
[credential]
    helper = ""
    useHttpPath = false
[credential "https://github.com"]
    helper = ""
[credential "https://api.github.com"]
    helper = ""
[credential "https://gist.github.com"]
    helper = ""
""")
        
        # Create a netrc file for additional authentication bypass
        netrc_path = os.path.join(temp_dir, '.netrc')
        if github_token and github_username:
            with open(netrc_path, 'w') as netrc_file:
                netrc_file.write(f"machine github.com login {github_username} password {github_token}\n")
                netrc_file.write(f"machine api.github.com login {github_username} password {github_token}\n")
            os.chmod(netrc_path, 0o600)  # Secure permissions for .netrc
        
        # Create a modified seatbelt profile that allows access to the temp directory
        temp_profile_path = os.path.join(temp_dir, 'git_seatbelt.sb')
        with open(temp_profile_path, 'w') as profile_file:
            # Get the original profile content
            profile_content = self.seatbelt_profile
            
            # Add temp directory to the profile for git operations
            profile_content = profile_content.replace(
                "; Allow Git operations", 
                f"; Allow Git operations\n(allow file-read* (subpath \"{temp_dir}\"))\n(allow file-write* (subpath \"{temp_dir}\"))"
            )
            
            # Ensure additional directories are included in the modified profile
            if self.additional_read_dirs or self.additional_write_dirs:
                # Build additional read directories section
                additional_read_dirs_rules = ""
                for dir_path in self.additional_read_dirs:
                    if f'(subpath "{dir_path}")' not in profile_content:
                        additional_read_dirs_rules += f'(allow file-read* (subpath "{dir_path}"))\n'
                
                # Build additional write directories section
                additional_write_dirs_rules = ""
                for dir_path in self.additional_write_dirs:
                    if f'(subpath "{dir_path}")' not in profile_content:
                        additional_write_dirs_rules += f'(allow file-write* (subpath "{dir_path}"))\n'
                
                # Add any missing directories to the profile
                if additional_read_dirs_rules or additional_write_dirs_rules:
                    profile_content = profile_content.replace(
                        "; Allow Git operations",
                        f"; Allow Git operations\n{additional_read_dirs_rules}{additional_write_dirs_rules}"
                    )
            
            profile_file.write(profile_content)
        
        # Get the base sandbox environment and add git-specific variables
        sandbox_env = self._get_sandbox_environment()
        
        # Add git-specific environment variables
        git_env = {
            "GIT_CONFIG_GLOBAL": git_config_path,
            "HOME": temp_dir,
            # Completely disable all credential helpers and prompts
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/echo",
            "SSH_ASKPASS": "/bin/echo",
            "DISPLAY": "",
            "GIT_CONFIG_NOSYSTEM": "1",
            # Disable credential storage completely
            "GIT_CREDENTIAL_HELPER": "",
            # Disable macOS keychain specifically
            "GIT_CREDENTIAL_OSXKEYCHAIN": "0",
            # Force use of netrc if available
            "NETRC": netrc_path if github_token and github_username else "",
            # Additional security environment variables
            "GIT_CURL_VERBOSE": "0",
            "GIT_QUIET": "1",
        }
        
        # If this is a push command and we have a token, modify the command to use the token directly
        if github_token and len(command) >= 3 and command[1] == "push":
            # Get the remote name (e.g., "fork" or "origin")
            remote_name = command[2]
            
            # Create a script that will set up the remote URL with the token and then execute the push
            script_path = os.path.join(temp_dir, 'git_push_with_token.sh')
            with open(script_path, 'w') as script_file:
                script_file.write(f"""#!/bin/bash
set -e

# Disable all credential helpers explicitly
export GIT_CREDENTIAL_HELPER=""
export GIT_CREDENTIAL_OSXKEYCHAIN="0"
export GIT_TERMINAL_PROMPT="0"
export GIT_ASKPASS="/bin/echo"

# Get the current remote URL
REMOTE_URL=$(git remote get-url {remote_name} 2>/dev/null || echo "")

# Check if it's a GitHub URL
if [[ "$REMOTE_URL" == *"github.com"* ]]; then
    # Extract the repo path from the URL
    REPO_PATH=$(echo "$REMOTE_URL" | sed -E 's|https://[^/]*github\.com/||' | sed -E 's|git@github\.com:||' | sed 's|\.git$||')
    
    # Set the remote URL with the token
    git remote set-url {remote_name} "https://{github_username}:{github_token}@github.com/$REPO_PATH.git"
fi

# Execute the original git command with credential helpers disabled
exec git -c credential.helper= -c credential.useHttpPath=false {' '.join(command[1:])}
""")
            
            # Make the script executable
            os.chmod(script_path, 0o755)
            
            # Modify the command to use the script
            command = ["bash", script_path]
        
        # Merge git environment with sandbox environment
        final_env = sandbox_env.copy()
        final_env.update(git_env)
        
        # Prepare the sandbox command with git environment
        env_args = [f"{key}={value}" for key, value in final_env.items()]
        
        sandbox_cmd = ["env", "-i"]
        sandbox_cmd.extend(env_args)
        sandbox_cmd.extend([
            "sandbox-exec", 
            "-f", temp_profile_path
        ])
        sandbox_cmd.extend(command)
        
        return sandbox_cmd
    
    async def execute_shell(self, command: List[str], timeout: int = 10, workdir: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a shell command securely within a sandbox and return the result.
        
        Args:
            command: List of command parts to execute
            timeout: Maximum execution time in seconds
            workdir: Working directory for command execution
            
        Returns:
            Dictionary containing execution results
        """
        if self.logger:
            self.logger.debug("Executing shell command in sandbox: %s", " ".join(command))
        
        print("#########################<Bash>#########################")
        print(f"{COLOR['BLUE']}>{command}{COLOR['ENDC']}")
        
        # Check if the command is safe
        safety_check = self.is_safe_command(command)
        if not safety_check["safe"]:
            response = {
                "stdout": "",
                "stderr": f"Command rejected for security reasons: {safety_check['reason']}",
                "exit_code": 1
            }
            print(f"{COLOR['RED']}{response['stderr']}{COLOR['ENDC']}")
            return response
        
        try:
            # Special handling for git commands
            if len(command) > 0 and command[0] == "git":
                sandbox_cmd = await self._prepare_git_sandbox_command(command)
                temp_dir = getattr(self, '_temp_git_dir', None)
            
            # Special handling for bash login shell to avoid profile loading errors
            elif len(command) >= 3 and command[0] == "bash" and command[1] == "-lc":
                # Get sandbox environment and add bash-specific variables
                bash_env = self._get_sandbox_environment()
                bash_env.update({
                    "BASH_ENV": "/dev/null",
                    "ENV": "/dev/null",
                    "BASH_PROFILE": "/dev/null",
                    "PROFILE": "/dev/null",
                })
                
                env_args = [f"{key}={value}" for key, value in bash_env.items()]
                
                sandbox_cmd = ["env", "-i"]
                sandbox_cmd.extend(env_args)
                sandbox_cmd.extend([
                    "sandbox-exec", 
                    "-f", self.seatbelt_profile_path,
                    "bash", "-c", command[2]
                ])
                temp_dir = None
            
            # Use the improved logic from base class
            elif self.should_use_shell_execution(command):
                # Commands that truly need shell interpretation
                quoted_command = self._quote_command_for_shell(command)
                sandbox_cmd = [
                    "sandbox-exec", 
                    "-f", self.seatbelt_profile_path,
                    "bash", "-c", quoted_command
                ]
                temp_dir = None
            else:
                # Commands that can run directly
                sandbox_cmd = [
                    "sandbox-exec", 
                    "-f", self.seatbelt_profile_path
                ]
                sandbox_cmd.extend(command)
                temp_dir = None
            
            # Set working directory
            cwd = workdir if workdir else os.getcwd()
            
            # Get the complete environment for the sandbox
            sandbox_env = self._get_sandbox_environment()
            
            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *sandbox_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=sandbox_env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                
                # Decode and strip ANSI color codes from stdout and stderr
                stdout_text = stdout.decode('utf-8', errors='replace')
                stderr_text = stderr.decode('utf-8', errors='replace')
                
                # Strip ANSI color codes to make output more readable
                clean_stdout = strip_ansi_codes(stdout_text)
                clean_stderr = strip_ansi_codes(stderr_text)
                
                result = {
                    "stdout": clean_stdout,
                    "stderr": clean_stderr,
                    "exit_code": process.returncode
                }
                
                # For display purposes, show the original output with colors
                print(f"{COLOR['GREEN']}{{\"stdout\": \"{stdout_text}\", \"stderr\": \"{stderr_text}\", \"exit_code\": {process.returncode}}}{COLOR['ENDC']}")
                return result
            
            except asyncio.TimeoutError:
                process.kill()
                response = {
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds",
                    "exit_code": 124  # 124 is the exit code for timeout in timeout command
                }
                print(f"{COLOR['RED']}{response['stderr']}{COLOR['ENDC']}")
                return response
            
            finally:
                # Clean up git temporary directory if it was created
                if temp_dir and hasattr(self, '_temp_git_dir'):
                    try:
                        import shutil
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        delattr(self, '_temp_git_dir')
                    except Exception:
                        pass
        
        except Exception as e:
            if self.logger:
                self.logger.error("Error executing shell command in sandbox: %s", str(e))
            response = {
                "stdout": "",
                "stderr": f"Error executing command: {str(e)}",
                "exit_code": 1
            }
            print(f"{COLOR['RED']}{response['stderr']}{COLOR['ENDC']}")
            return response
    
    @classmethod
    def is_supported(cls) -> bool:
        """
        Check if the current system supports seatbelt sandboxing.
        
        Returns:
            True if the system supports seatbelt (macOS), False otherwise
        """
        if platform.system() != "Darwin":
            return False
        
        # Check if sandbox-exec exists
        try:
            subprocess.run(["which", "sandbox-exec"], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False
    
    async def cleanup(self):
        """Clean up any resources used by the provider."""
        # Reset state
        self.executed_default_codes = False
        self._globals_dict = {}
        self._locals_dict = {}
        
        # Remove temporary seatbelt profile file if we created one
        if self.seatbelt_profile and self.seatbelt_profile_path and os.path.exists(self.seatbelt_profile_path):
            try:
                os.unlink(self.seatbelt_profile_path)
                if self.logger:
                    self.logger.debug("Removed temporary seatbelt profile: %s", self.seatbelt_profile_path)
            except Exception as e:
                if self.logger:
                    self.logger.warning("Failed to remove temporary seatbelt profile: %s", str(e))

        # Remove sandbox temp directory
        try:
            if getattr(self, 'sandbox_tmp_dir', None) and os.path.isdir(self.sandbox_tmp_dir):
                shutil.rmtree(self.sandbox_tmp_dir, ignore_errors=True)
        except Exception:
            pass
 