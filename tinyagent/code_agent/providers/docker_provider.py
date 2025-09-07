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
import uuid
import tarfile
import io
from typing import Dict, List, Any, Optional, Set
from pathlib import Path

from tinyagent.hooks.logging_manager import LoggingManager
from .base import CodeExecutionProvider
from ..utils import clean_response, make_session_blob
from .docker_image_builder import DockerImageBuilder, DockerConfigBuilder

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


class DockerProvider(CodeExecutionProvider):
    """
    A code execution provider that uses Docker containers for cross-platform sandboxed execution.
    
    This provider executes Python code and shell commands within Docker containers for enhanced security
    and cross-platform compatibility. It works on any system with Docker installed and provides
    equivalent functionality to SeatbeltProvider and BubblewrapProvider.
    
    Features:
    - Cross-platform compatibility (Windows, macOS, Linux)
    - Container-based isolation with security hardening
    - State persistence between executions using volume mounts
    - Resource limits and timeout handling
    - Network isolation (configurable)
    - Non-root execution for security
    - Automatic cleanup of containers and volumes
    """
    
    def __init__(
        self,
        log_manager: Optional[LoggingManager] = None,
        code_tools: List[Any] = None,
        docker_image: str = "tinyagent-runtime:latest",
        python_env_path: Optional[str] = None,
        authorized_imports: list[str] | None = None,
        authorized_functions: list[str] | None = None,
        check_string_obfuscation: bool = True,
        bypass_shell_safety: bool = True,  # Default to True for DockerProvider
        additional_safe_shell_commands: Optional[List[str]] = None,
        additional_safe_control_operators: Optional[List[str]] = None,
        additional_read_dirs: Optional[List[str]] = None,
        additional_write_dirs: Optional[List[str]] = None,
        environment_variables: Optional[Dict[str, str]] = None,
        container_name_prefix: str = "tinyagent",
        enable_network: bool = False,
        memory_limit: str = "512m",
        cpu_limit: str = "1.0",
        timeout: int = 300,
        auto_pull_image: bool = True,
        volume_mount_path: str = "/workspace",
        **kwargs
    ):
        """
        Initialize the DockerProvider.
        
        Args:
            log_manager: Optional logging manager
            code_tools: List of tools available in the Python execution environment
            docker_image: Docker image to use for execution
            python_env_path: Path to the Python environment to use (not used in Docker, kept for compatibility)
            authorized_imports: Optional allow-list of modules the user code is permitted to import
            authorized_functions: Optional allow-list of dangerous functions the user code is permitted to use
            check_string_obfuscation: If True, check for string obfuscation techniques
            bypass_shell_safety: If True, bypass shell command safety checks
            additional_safe_shell_commands: Additional shell commands to consider safe
            additional_safe_control_operators: Additional shell control operators to consider safe
            additional_read_dirs: List of additional directories to allow read access to
            additional_write_dirs: List of additional directories to allow write access to
            environment_variables: Dictionary of environment variables to make available in the container
            container_name_prefix: Prefix for container names
            enable_network: Whether to enable network access in containers
            memory_limit: Memory limit for containers (e.g., "512m", "1g")
            cpu_limit: CPU limit for containers (e.g., "1.0", "0.5")
            timeout: Default timeout for container operations in seconds
            auto_pull_image: Whether to automatically pull the Docker image if it doesn't exist
            volume_mount_path: Path inside container where workspace is mounted
            **kwargs: Additional arguments passed to CodeExecutionProvider
        """
        # Initialize logger first to avoid AttributeError
        self.logger = None
        if log_manager:
            self.logger = log_manager.get_logger('tinyagent.code_agent.providers.docker_provider')
        
        super().__init__(
            log_manager=log_manager,
            code_tools=code_tools,
            bypass_shell_safety=bypass_shell_safety,
            additional_safe_shell_commands=additional_safe_shell_commands,
            additional_safe_control_operators=additional_safe_control_operators,
            **kwargs
        )
        
        # Check if Docker is available
        if not self._check_docker_availability():
            raise RuntimeError("Docker is not available on this system. Please install Docker.")
        
        # Store configuration
        self.docker_image = docker_image
        self.container_name_prefix = container_name_prefix
        self.enable_network = enable_network
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.default_timeout = timeout
        self.auto_pull_image = auto_pull_image
        self.volume_mount_path = volume_mount_path
        
        # Store additional read/write directories
        self.additional_read_dirs = additional_read_dirs or []
        self.additional_write_dirs = additional_write_dirs or []
        
        # Expand and normalize paths to avoid issues with symlinks and relative paths
        self.additional_read_dirs = [os.path.abspath(os.path.expanduser(path)) for path in self.additional_read_dirs]
        self.additional_write_dirs = [os.path.abspath(os.path.expanduser(path)) for path in self.additional_write_dirs]
        
        # Store environment variables
        self.environment_variables = environment_variables.copy() if environment_variables else {}
        
        # Safety settings
        self.authorized_imports = authorized_imports
        self.authorized_functions = authorized_functions or []
        self.check_string_obfuscation = check_string_obfuscation
        self.is_trusted_code = kwargs.get("trust_code", False)
        
        # Create a persistent workspace directory for state management
        try:
            self.workspace_dir = os.path.join(tempfile.gettempdir(), f"tinyagent_docker_{os.getpid()}")
            os.makedirs(self.workspace_dir, exist_ok=True)
            
            # Create subdirectories for different purposes
            self.state_dir = os.path.join(self.workspace_dir, "state")
            self.scripts_dir = os.path.join(self.workspace_dir, "scripts")
            self.temp_dir = os.path.join(self.workspace_dir, "temp")
            
            for dir_path in [self.state_dir, self.scripts_dir, self.temp_dir]:
                os.makedirs(dir_path, exist_ok=True)
                
        except Exception as e:
            # Fallback to current working directory if creation fails
            self.workspace_dir = os.getcwd()
            self.state_dir = self.workspace_dir
            self.scripts_dir = self.workspace_dir
            self.temp_dir = self.workspace_dir
            if self.logger:
                self.logger.warning("Falling back to CWD for workspace due to error: %s", str(e))
        
        # Container management
        self.active_containers: Set[str] = set()
        self.persistent_volume_name = None
        
        # Ensure Docker image is available (will be done lazily on first execution)
        # Note: Image availability is checked during first execution to avoid
        # blocking the constructor with async operations
        
        # Log initialization
        if self.logger:
            self.logger.info("Initialized DockerProvider with image: %s", self.docker_image)
            self.logger.info("Workspace directory: %s", self.workspace_dir)
            if self.additional_read_dirs:
                self.logger.info("Additional read directories: %s", ", ".join(self.additional_read_dirs))
            if self.additional_write_dirs:
                self.logger.info("Additional write directories: %s", ", ".join(self.additional_write_dirs))
            if self.environment_variables:
                env_keys = list(self.environment_variables.keys())
                self.logger.info("Environment variables: %s", ", ".join(env_keys))
    
    def _check_docker_availability(self) -> bool:
        """
        Check if Docker is available on the system.
        
        Returns:
            True if Docker is available, False otherwise
        """
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                # Also check if Docker daemon is running
                result = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=10)
                return result.returncode == 0
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False
    
    async def _ensure_docker_image(self):
        """
        Ensure the Docker image is available, pull it if necessary.
        """
        try:
            # Check if image exists locally
            result = await asyncio.create_subprocess_exec(
                'docker', 'image', 'inspect', self.docker_image,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await result.wait()
            
            if result.returncode != 0:
                if self.logger:
                    self.logger.info("Docker image %s not found locally, attempting to pull...", self.docker_image)
                
                # Try to pull the image
                result = await asyncio.create_subprocess_exec(
                    'docker', 'pull', self.docker_image,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await result.wait()
                
                if result.returncode != 0:
                    # If pull fails, try to build the image locally
                    if self.logger:
                        self.logger.warning("Failed to pull image %s, attempting to build locally...", self.docker_image)
                    await self._build_default_image()
            else:
                if self.logger:
                    self.logger.debug("Docker image %s is available", self.docker_image)
                    
        except Exception as e:
            if self.logger:
                self.logger.error("Error ensuring Docker image availability: %s", str(e))
    
    async def _build_default_image(self):
        """
        Build the default Docker image if it's not available.
        """
        try:
            # Create a temporary directory for the build context
            with tempfile.TemporaryDirectory() as build_dir:
                dockerfile_path = os.path.join(build_dir, "Dockerfile")
                
                # Write the default Dockerfile
                dockerfile_content = self._get_default_dockerfile()
                with open(dockerfile_path, 'w') as f:
                    f.write(dockerfile_content)
                
                if self.logger:
                    self.logger.info("Building Docker image %s...", self.docker_image)
                
                # Build the image
                result = await asyncio.create_subprocess_exec(
                    'docker', 'build', '-t', self.docker_image, '.',
                    cwd=build_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='replace')
                    if self.logger:
                        self.logger.error("Failed to build Docker image: %s", error_msg)
                    raise RuntimeError(f"Failed to build Docker image: {error_msg}")
                else:
                    if self.logger:
                        self.logger.info("Successfully built Docker image %s", self.docker_image)
                        
        except Exception as e:
            if self.logger:
                self.logger.error("Error building default Docker image: %s", str(e))
            raise RuntimeError(f"Failed to build Docker image: {str(e)}")
    
    def _get_default_dockerfile(self) -> str:
        """
        Get the content for a default Dockerfile optimized for TinyAgent execution.
        
        Returns:
            Dockerfile content as string
        """
        return '''FROM python:3.11-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash tinyagent

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    curl \\
    wget \\
    build-essential \\
    pkg-config \\
    && rm -rf /var/lib/apt/lists/*

# Install common Python packages
RUN pip install --no-cache-dir \\
    cloudpickle \\
    requests \\
    numpy \\
    pandas \\
    matplotlib \\
    seaborn \\
    scipy \\
    scikit-learn \\
    jupyter \\
    ipython \\
    beautifulsoup4 \\
    lxml \\
    openpyxl \\
    python-dateutil \\
    pytz \\
    tqdm \\
    pyyaml \\
    jsonschema

# Create workspace directory with proper permissions
RUN mkdir -p /workspace && chown tinyagent:tinyagent /workspace

# Create a secure temporary directory
RUN mkdir -p /tmp/tinyagent && chown tinyagent:tinyagent /tmp/tinyagent

# Switch to non-root user
USER tinyagent

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]
'''
    
    def _generate_container_name(self) -> str:
        """
        Generate a unique container name.
        
        Returns:
            Unique container name
        """
        return f"{self.container_name_prefix}_{uuid.uuid4().hex[:8]}"
    
    def _get_docker_command(
        self,
        command: List[str],
        container_name: Optional[str] = None,
        volumes: Optional[Dict[str, str]] = None,
        environment: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        detach: bool = False,
        remove: bool = True
    ) -> List[str]:
        """
        Build a Docker command with all necessary options.
        
        Args:
            command: Command to execute in the container
            container_name: Name for the container
            volumes: Volume mounts as {host_path: container_path}
            environment: Environment variables
            working_dir: Working directory inside container
            detach: Whether to run in detached mode
            remove: Whether to remove container after execution
            
        Returns:
            Complete Docker command as list of arguments
        """
        docker_cmd = ['docker', 'run']
        
        # Container management options
        if container_name:
            docker_cmd.extend(['--name', container_name])
        
        if remove:
            docker_cmd.append('--rm')
            
        if detach:
            docker_cmd.append('-d')
        else:
            docker_cmd.append('-i')  # Interactive mode for better output handling
        
        # Security options
        docker_cmd.extend([
            '--user', '1000:1000',  # Run as non-root user
            '--cap-drop', 'ALL',    # Drop all capabilities
            '--security-opt', 'no-new-privileges',  # Prevent privilege escalation
            '--read-only',          # Read-only root filesystem
            '--tmpfs', '/tmp:exec,size=100m',  # Writable tmp with size limit
        ])
        
        # Network isolation
        if not self.enable_network:
            docker_cmd.extend(['--network', 'none'])
        
        # Resource limits
        docker_cmd.extend([
            '--memory', self.memory_limit,
            '--cpus', self.cpu_limit,
            '--pids-limit', '100',  # Limit number of processes
        ])
        
        # Volume mounts
        volumes = volumes or {}
        
        # Always mount the workspace
        volumes[self.workspace_dir] = self.volume_mount_path
        
        # Add additional read/write directories
        for read_dir in self.additional_read_dirs:
            if os.path.exists(read_dir):
                container_path = f"/mnt/read_{os.path.basename(read_dir)}"
                volumes[f"{read_dir}:ro"] = container_path
        
        for write_dir in self.additional_write_dirs:
            if os.path.exists(write_dir):
                container_path = f"/mnt/write_{os.path.basename(write_dir)}"
                volumes[write_dir] = container_path
        
        for host_path, container_path in volumes.items():
            if ':ro' in host_path:
                # Read-only mount
                host_path = host_path.replace(':ro', '')
                docker_cmd.extend(['-v', f"{host_path}:{container_path}:ro"])
            else:
                # Read-write mount
                docker_cmd.extend(['-v', f"{host_path}:{container_path}"])
        
        # Environment variables
        env_vars = self._get_container_environment()
        if environment:
            env_vars.update(environment)
        
        for key, value in env_vars.items():
            docker_cmd.extend(['-e', f"{key}={value}"])
        
        # Working directory
        if working_dir:
            docker_cmd.extend(['-w', working_dir])
        else:
            docker_cmd.extend(['-w', self.volume_mount_path])
        
        # Docker image
        docker_cmd.append(self.docker_image)
        
        # Command to execute
        docker_cmd.extend(command)
        
        return docker_cmd
    
    def _get_container_environment(self) -> Dict[str, str]:
        """
        Get the complete environment for container execution.
        
        Returns:
            Dictionary containing all environment variables for the container
        """
        # Start with essential environment variables
        base_env = {
            'HOME': '/home/tinyagent',
            'USER': 'tinyagent',
            'TERM': 'xterm-256color',
            'LANG': 'C.UTF-8',
            'LC_ALL': 'C.UTF-8',
            'PYTHONPATH': self.volume_mount_path,
            'TMPDIR': '/tmp',
        }
        
        # Add Python-specific environment variables
        python_vars = ['PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV']
        for var in python_vars:
            if var in os.environ and var not in base_env:
                base_env[var] = os.environ[var]
        
        # Add user-defined environment variables (these can override base ones)
        base_env.update(self.environment_variables)
        
        return base_env
    
    def set_environment_variables(self, env_vars: Dict[str, str]):
        """
        Set environment variables for the container.
        
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
    
    async def execute_python(self, code_lines: List[str], timeout: int = 120, debug_mode: bool = False) -> Dict[str, Any]:
        """
        Execute Python code within a Docker container and return the result.
        
        Args:
            code_lines: List of Python code lines to execute
            timeout: Maximum execution time in seconds
            debug_mode: Whether to print the executed code (useful for debugging)
            
        Returns:
            Dictionary containing execution results
        """
        if isinstance(code_lines, str):
            code_lines = [code_lines]
        
        full_code = "\n".join(code_lines)
        
        if debug_mode:
            print("#" * 100)
            print("##########################################code##########################################")
            print(full_code)
            print("#" * 100)
        
        # Prepare the full code with tools and default codes if needed
        if self.executed_default_codes:
            if debug_mode:
                print("✔️ default codes already executed")
            complete_code = "\n".join(self.code_tools_definitions) + "\n\n" + full_code
        else:
            complete_code = "\n".join(self.code_tools_definitions) + "\n\n" + "\n".join(self.default_python_codes) + "\n\n" + full_code
            self.executed_default_codes = True
        
        # Inject container system context at the beginning of code execution
        container_context_code = f"""
# Auto-injected container system context
import os, platform
print(f"🐳 Container Environment: {{os.getcwd()}}")
print(f"🖥️  Platform: {{platform.system()}} {{platform.machine()}}")
print(f"🐍 Python: {{platform.python_version()}}")
print(f"👤 User: {{os.environ.get('USER', 'unknown')}}")

# Set working directory context for user code
import sys
sys.path.insert(0, '{self.volume_mount_path}')
os.chdir('{self.volume_mount_path}')
"""
        
        # Add the context code at the beginning
        complete_code = container_context_code + "\n" + complete_code
        
        # Create state file for persistence
        state_file_path = os.path.join(self.state_dir, 'python_state.pkl')
        
        # Serialize the globals and locals dictionaries
        with open(state_file_path, 'wb') as state_file:
            cloudpickle.dump({
                'globals': self._globals_dict,
                'locals': self._locals_dict,
                'authorized_imports': self.authorized_imports,
                'authorized_functions': self.authorized_functions,
                'trusted_code': self.is_trusted_code,
                'check_string_obfuscation': self.check_string_obfuscation
            }, state_file)
        
        # Create the Python execution script
        script_path = os.path.join(self.scripts_dir, 'execute_python.py')
        script_content = self._generate_python_execution_script(complete_code, state_file_path)
        
        with open(script_path, 'w') as script_file:
            script_file.write(script_content)
        
        try:
            # Ensure Docker image is available before first execution
            if self.auto_pull_image:
                await self._ensure_docker_image()
            
            # Prepare container paths
            container_state_path = os.path.join(self.volume_mount_path, 'state', 'python_state.pkl')
            container_script_path = os.path.join(self.volume_mount_path, 'scripts', 'execute_python.py')
            
            # Generate container name
            container_name = self._generate_container_name()
            
            # Build Docker command
            docker_cmd = self._get_docker_command(
                ['python', container_script_path],
                container_name=container_name
            )
            
            if self.logger:
                self.logger.debug("Executing Python code in Docker container: %s", container_name)
            
            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stdout_str = stdout.decode('utf-8', errors='replace')
                stderr_str = stderr.decode('utf-8', errors='replace')
                
                # Try to parse the JSON result from stdout
                try:
                    # Look for JSON on the last line that contains curly braces
                    lines = stdout_str.strip().split('\n')
                    json_line = None
                    for line in reversed(lines):
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            json_line = line
                            break
                    
                    if json_line:
                        json_result = json.loads(json_line)
                        result = json_result
                    else:
                        raise json.JSONDecodeError("No JSON found", stdout_str, 0)
                        
                except json.JSONDecodeError:
                    # If we can't parse JSON, return the raw output
                    result = {
                        "printed_output": stdout_str,
                        "return_value": None,
                        "stderr": stderr_str,
                        "error_traceback": f"Failed to parse result as JSON: {stderr_str}"
                    }
                
                # Load updated state
                try:
                    if os.path.exists(state_file_path):
                        with open(state_file_path, 'rb') as f:
                            state = cloudpickle.load(f)
                            self._globals_dict = state['globals']
                            self._locals_dict = state['locals']
                            
                        # Update user variables from the updated globals and locals
                        self.update_user_variables_from_globals(self._globals_dict)
                        self.update_user_variables_from_globals(self._locals_dict)
                    else:
                        if self.logger:
                            self.logger.debug("State file not found: %s", state_file_path)
                except Exception as e:
                    if self.logger:
                        self.logger.warning("Failed to load state from %s: %s", state_file_path, str(e))
                
                if process.returncode != 0:
                    result["error"] = f"Process exited with code {process.returncode}"
                
                # Log the response
                self._log_response(result, debug_mode)
                
                return clean_response(result)
            
            except asyncio.TimeoutError:
                # Kill the container if it's still running
                try:
                    await asyncio.create_subprocess_exec('docker', 'kill', container_name)
                except:
                    pass
                
                return {
                    "printed_output": "",
                    "return_value": None,
                    "stderr": f"Execution timed out after {timeout} seconds",
                    "error_traceback": f"Execution timed out after {timeout} seconds"
                }
        
        except Exception as e:
            if self.logger:
                self.logger.error("Error executing Python in Docker: %s", str(e))
            return {
                "printed_output": "",
                "return_value": None,
                "stderr": f"Error executing code: {str(e)}",
                "error_traceback": f"Error executing code: {str(e)}"
            }
        
        finally:
            # Clean up temporary script file
            try:
                if os.path.exists(script_path):
                    os.unlink(script_path)
            except Exception:
                pass
    
    def _generate_python_execution_script(self, complete_code: str, state_file_path: str) -> str:
        """
        Generate the Python execution script that will run inside the container.
        
        Args:
            complete_code: Complete Python code to execute
            state_file_path: Path to the state file (host path)
            
        Returns:
            Python script content as string
        """
        # Convert host path to container path
        container_state_path = state_file_path.replace(self.workspace_dir, self.volume_mount_path)
        
        return f"""
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
state_path = {repr(container_state_path)}
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
    essential_modules = ['requests', 'json', 'time', 'datetime', 're', 'random', 'math', 'cloudpickle', 'numpy', 'pandas']
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
"""
    
    def _log_response(self, response: Dict[str, Any], debug_mode: bool = False):
        """Log the response from code execution."""
        if debug_mode:
            print("######################### DOCKER EXECUTION #########################")
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
    
    async def execute_shell(self, command: List[str], timeout: int = 10, workdir: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a shell command securely within a Docker container and return the result.
        
        Args:
            command: List of command parts to execute
            timeout: Maximum execution time in seconds
            workdir: Working directory for command execution (relative to volume_mount_path)
            
        Returns:
            Dictionary containing execution results
        """
        if self.logger:
            self.logger.debug("Executing shell command in Docker container: %s", " ".join(command))
        
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
            # Ensure Docker image is available before first execution
            if self.auto_pull_image:
                await self._ensure_docker_image()
                
            # Generate container name
            container_name = self._generate_container_name()
            
            # Determine working directory inside container
            container_workdir = self.volume_mount_path
            if workdir:
                # Convert relative workdir to absolute container path
                if not os.path.isabs(workdir):
                    container_workdir = os.path.join(self.volume_mount_path, workdir)
                else:
                    container_workdir = workdir
            
            # Build the command to execute
            if self.should_use_shell_execution(command):
                # Commands that truly need shell interpretation
                quoted_command = self._quote_command_for_shell(command)
                exec_command = ['/bin/bash', '-c', quoted_command]
            else:
                # Commands that can run directly
                exec_command = command
            
            # Special handling for git commands
            if len(command) > 0 and command[0] == "git":
                exec_command = await self._prepare_git_command(command)
            
            # Build Docker command
            docker_cmd = self._get_docker_command(
                exec_command,
                container_name=container_name,
                working_dir=container_workdir
            )
            
            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
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
                print(f"{COLOR['GREEN']}{{'stdout': '{stdout_text}', 'stderr': '{stderr_text}', 'exit_code': {process.returncode}}}{COLOR['ENDC']}")
                return result
            
            except asyncio.TimeoutError:
                # Kill the container if it's still running
                try:
                    await asyncio.create_subprocess_exec('docker', 'kill', container_name)
                except:
                    pass
                
                response = {
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds",
                    "exit_code": 124  # 124 is the exit code for timeout in timeout command
                }
                print(f"{COLOR['RED']}{response['stderr']}{COLOR['ENDC']}")
                return response
        
        except Exception as e:
            if self.logger:
                self.logger.error("Error executing shell command in Docker: %s", str(e))
            response = {
                "stdout": "",
                "stderr": f"Error executing command: {str(e)}",
                "exit_code": 1
            }
            print(f"{COLOR['RED']}{response['stderr']}{COLOR['ENDC']}")
            return response
    
    async def _prepare_git_command(self, command: List[str]) -> List[str]:
        """
        Prepare a git command with proper environment and credential handling.
        
        Args:
            command: Git command to prepare
            
        Returns:
            Prepared command list
        """
        # Get GitHub credentials from environment
        github_username = self.environment_variables.get('GITHUB_USERNAME', 'tinyagent')
        github_token = self.environment_variables.get('GITHUB_TOKEN', '')
        git_author_name = self.environment_variables.get('GIT_AUTHOR_NAME', 'TinyAgent')
        git_author_email = self.environment_variables.get('GIT_AUTHOR_EMAIL', 'tinyagent@example.com')
        
        # Create git configuration script
        git_config_script = f"""#!/bin/bash
set -e

# Configure Git user
git config --global user.name "{git_author_name}"
git config --global user.email "{git_author_email}"
git config --global safe.directory "*"

# Disable credential helpers and prompts
git config --global credential.helper ""
git config --global core.askpass /bin/echo
export GIT_TERMINAL_PROMPT=0
export GIT_ASKPASS=/bin/echo

# Execute the original git command
exec {' '.join(shlex.quote(arg) for arg in command)}
"""
        
        # Write the script to workspace
        script_path = os.path.join(self.scripts_dir, 'git_command.sh')
        with open(script_path, 'w') as f:
            f.write(git_config_script)
        os.chmod(script_path, 0o755)
        
        # Return command to execute the script
        container_script_path = os.path.join(self.volume_mount_path, 'scripts', 'git_command.sh')
        return ['/bin/bash', container_script_path]
    
    @classmethod
    def is_supported(cls) -> bool:
        """
        Check if the current system supports Docker execution.
        
        Returns:
            True if Docker is available, False otherwise
        """
        try:
            result = subprocess.run(['docker', '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Also check if Docker daemon is running
                result = subprocess.run(['docker', 'info'], capture_output=True, text=True, timeout=5)
                return result.returncode == 0
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False
    
    async def _get_container_system_info(self) -> Dict[str, Any]:
        """
        Get system information from inside a container.
        
        Returns:
            Dictionary containing container system information
        """
        if self.container_system_info is not None:
            return self.container_system_info
        
        info_script = '''
import os, platform, subprocess, pwd, sys
import json

info = {
    "cwd": os.getcwd(),
    "platform": platform.system(),
    "architecture": platform.machine(),
    "python_version": platform.python_version(),
    "user": pwd.getpwuid(os.getuid()).pw_name,
    "home": os.path.expanduser("~"),
    "shell": os.environ.get("SHELL", "/bin/bash"),
    "available_commands": []
}

# Check available commands
commands_to_check = ["git", "curl", "wget", "vim", "nano", "htop", "jq", "node", "npm"]
for cmd in commands_to_check:
    try:
        result = subprocess.run(["which", cmd], check=True, capture_output=True, text=True)
        if result.returncode == 0:
            info["available_commands"].append(cmd)
    except:
        pass

print("SYSTEM_INFO_JSON:" + json.dumps(info))
'''
        
        try:
            # Generate temporary container to gather system info
            container_name = f"{self.container_name_prefix}_sysinfo_{uuid.uuid4().hex[:8]}"
            
            # Build Docker command for system info gathering
            docker_cmd = [
                'docker', 'run', '--rm',
                '--name', container_name,
                '--user', '1000:1000',
                '--workdir', self.volume_mount_path,
                '--network', 'none' if not self.enable_network else 'bridge',
                self.docker_image,
                'python3', '-c', info_script
            ]
            
            # Execute the command
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            stdout_text = stdout.decode('utf-8', errors='replace')
            
            # Parse system info from output
            for line in stdout_text.split('\n'):
                if line.startswith('SYSTEM_INFO_JSON:'):
                    info_json = line[17:]  # Remove prefix
                    self.container_system_info = json.loads(info_json)
                    break
            else:
                # Fallback system info if parsing fails
                self.container_system_info = {
                    "cwd": self.volume_mount_path,
                    "platform": "Linux",
                    "architecture": "x86_64",
                    "python_version": "3.11",
                    "user": "tinyagent",
                    "home": "/home/tinyagent",
                    "shell": "/bin/bash",
                    "available_commands": ["python3", "pip"]
                }
            
            if self.logger:
                self.logger.debug("Container system info: %s", self.container_system_info)
                
        except Exception as e:
            if self.logger:
                self.logger.warning("Failed to get container system info: %s", str(e))
            # Provide fallback system info
            self.container_system_info = {
                "cwd": self.volume_mount_path,
                "platform": "Linux",
                "architecture": "x86_64", 
                "python_version": "3.11",
                "user": "tinyagent",
                "home": "/home/tinyagent",
                "shell": "/bin/bash",
                "available_commands": ["python3", "pip"]
            }
        
        return self.container_system_info
    
    async def get_dynamic_system_prompt(self) -> str:
        """
        Get a dynamic system prompt that reflects the actual container environment.
        
        Returns:
            System prompt string with container-specific information
        """
        if self.dynamic_system_prompt_cache is not None:
            return self.dynamic_system_prompt_cache
        
        # Ensure Docker image is available
        if self.auto_pull_image:
            await self._ensure_docker_image()
        
        # Get container system information
        container_info = await self._get_container_system_info()
        
        # Build dynamic system prompt
        available_tools_str = ", ".join(container_info.get("available_commands", []))
        
        system_prompt = f"""You are executing code in a secure Docker container environment.

CONTAINER ENVIRONMENT:
- Working directory: {container_info.get('cwd', self.volume_mount_path)}
- Platform: {container_info.get('platform', 'Linux')} {container_info.get('architecture', 'x86_64')}
- Python version: {container_info.get('python_version', '3.11')}
- User: {container_info.get('user', 'tinyagent')}
- Available shell: {container_info.get('shell', '/bin/bash')}
- Available tools: {available_tools_str}

WORKING DIRECTORY MAPPING:
- Host directory: {self.working_directory}
- Container directory: {self.volume_mount_path}
- All file operations are relative to the container working directory
- You have read/write access to the mounted working directory

SECURITY CONTEXT:
- Running in isolated Docker container
- Network access: {'enabled' if self.enable_network else 'disabled'}
- Resource limits: Memory {self.memory_limit}, CPU {self.cpu_limit}
- Non-root user execution for security

Use this environment information for accurate file operations and system commands.
"""
        
        self.dynamic_system_prompt_cache = system_prompt
        return system_prompt
    
    def _resolve_file_path(self, file_path: str) -> str:
        """
        Resolve host file path to container path for unified API.
        
        Args:
            file_path: File path that could be relative or absolute
            
        Returns:
            Container path for the file
            
        Raises:
            ValueError: If the path is outside the allowed working directory
        """
        if os.path.isabs(file_path):
            # Absolute path - check if it's within working directory
            if file_path.startswith(self.working_directory):
                # Path is within working directory, map to container
                relative_path = os.path.relpath(file_path, self.working_directory)
                return os.path.join(self.volume_mount_path, relative_path)
            elif file_path.startswith(self.volume_mount_path):
                # Already a container path
                return file_path
            else:
                # Check if it's in additional allowed directories
                for allowed_dir in self.additional_read_dirs + self.additional_write_dirs:
                    if file_path.startswith(allowed_dir):
                        # Map to container path (this is a simplified mapping)
                        relative_path = os.path.relpath(file_path, allowed_dir)
                        return os.path.join(self.volume_mount_path, 'additional', os.path.basename(allowed_dir), relative_path)
                
                raise ValueError(f"File path {file_path} is outside allowed directories")
        else:
            # Relative path - always relative to container working directory
            return os.path.join(self.volume_mount_path, file_path)
    
    async def read_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        Read file with automatic path resolution for unified API.
        
        Args:
            file_path: File path to read (can be host or container path)
            **kwargs: Additional arguments passed to base class
            
        Returns:
            Dictionary containing file read results
        """
        try:
            container_path = self._resolve_file_path(file_path)
            return await super().read_file(container_path, **kwargs)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "path": file_path,
                "size": 0,
                "content": None
            }
    
    async def write_file(self, file_path: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Write file with automatic path resolution for unified API.
        
        Args:
            file_path: File path to write (can be host or container path)
            content: Content to write
            **kwargs: Additional arguments passed to base class
            
        Returns:
            Dictionary containing file write results
        """
        try:
            container_path = self._resolve_file_path(file_path)
            return await super().write_file(container_path, content, **kwargs)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "path": file_path,
                "bytes_written": 0,
                "operation": "write"
            }
    
    async def update_file(self, file_path: str, old_content: str, new_content: str, **kwargs) -> Dict[str, Any]:
        """
        Update file with automatic path resolution for unified API.
        
        Args:
            file_path: File path to update (can be host or container path)
            old_content: Content to replace
            new_content: Replacement content
            **kwargs: Additional arguments passed to base class
            
        Returns:
            Dictionary containing file update results
        """
        try:
            container_path = self._resolve_file_path(file_path)
            return await super().update_file(container_path, old_content, new_content, **kwargs)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "path": file_path,
                "changes_made": False,
                "old_content": old_content,
                "new_content": new_content,
                "bytes_written": 0
            }

    @classmethod 
    def create_with_config(cls, config_builder: DockerConfigBuilder, **kwargs) -> 'DockerProvider':
        """
        Create DockerProvider instance using configuration builder.
        
        Args:
            config_builder: Pre-configured DockerConfigBuilder instance
            **kwargs: Additional configuration to override
            
        Returns:
            DockerProvider instance
        """
        config = config_builder.build_config()
        config.update(kwargs)
        return cls(**config)
    
    @classmethod
    def for_data_science(cls, working_directory: str = None, **kwargs) -> 'DockerProvider':
        """
        Create DockerProvider optimized for data science workloads.
        
        Args:
            working_directory: Working directory path
            **kwargs: Additional configuration
            
        Returns:
            DockerProvider instance
        """
        builder = DockerConfigBuilder().for_data_science()
        if working_directory:
            builder.with_working_directory(working_directory)
        
        return cls.create_with_config(builder, **kwargs)
    
    @classmethod 
    def for_web_development(cls, working_directory: str = None, **kwargs) -> 'DockerProvider':
        """
        Create DockerProvider optimized for web development workloads.
        
        Args:
            working_directory: Working directory path
            **kwargs: Additional configuration
            
        Returns:
            DockerProvider instance
        """
        builder = DockerConfigBuilder().for_web_development()
        if working_directory:
            builder.with_working_directory(working_directory)
        
        return cls.create_with_config(builder, **kwargs)

    async def cleanup(self):
        """Clean up any resources used by the provider."""
        # Reset state
        self.executed_default_codes = False
        self._globals_dict = {}
        self._locals_dict = {}
        
        # Stop and remove any active containers
        for container_name in list(self.active_containers):
            try:
                await asyncio.create_subprocess_exec('docker', 'kill', container_name)
                await asyncio.create_subprocess_exec('docker', 'rm', container_name)
            except Exception:
                pass
        self.active_containers.clear()
        
        # Clean up workspace directory
        try:
            if hasattr(self, 'workspace_dir') and os.path.isdir(self.workspace_dir):
                shutil.rmtree(self.workspace_dir, ignore_errors=True)
                if self.logger:
                    self.logger.debug("Cleaned up workspace directory: %s", self.workspace_dir)
        except Exception as e:
            if self.logger:
                self.logger.warning("Failed to clean up workspace directory: %s", str(e))