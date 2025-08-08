import sys
import cloudpickle
import subprocess
import os
from typing import Dict, Any, List, Tuple, Optional
from .safety import validate_code_safety, function_safety_context
import shlex
import yaml
from pathlib import Path
import re
import platform


def clean_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean the response from code execution, keeping only relevant fields.
    
    Args:
        resp: Raw response dictionary from code execution
        
    Returns:
        Cleaned response with only essential fields
    """
    return {k: v for k, v in resp.items() if k in ['printed_output', 'return_value', 'stderr', 'error_traceback']}


def truncate_output(output: str, max_tokens: int = 3000, max_lines: int = 250) -> Tuple[str, bool, int, int]:
    """
    Truncate output based on token count and line count.
    
    Args:
        output: The output string to truncate
        max_tokens: Maximum number of tokens to keep
        max_lines: Maximum number of lines to keep
        
    Returns:
        Tuple containing:
        - Truncated output
        - Boolean indicating if truncation occurred
        - Original token count
        - Original line count
    """
    # Count original lines
    lines = output.splitlines()
    original_line_count = len(lines)
    
    # Approximate token count (rough estimate: 4 chars ≈ 1 token)
    original_token_count = len(output) // 4
    
    # Check if truncation is needed
    if original_line_count <= max_lines and original_token_count <= max_tokens:
        return output, False, original_token_count, original_line_count
    
    # Truncate by lines first
    if original_line_count > max_lines:
        lines = lines[:max_lines]  # Keep only the first max_lines
    
    # Join lines back together
    truncated = '\n'.join(lines)
    
    # If still too many tokens, truncate further
    if len(truncated) // 4 > max_tokens:
        # Keep the first max_tokens*4 characters (approximate)
        truncated = truncated[:max_tokens*4]
        
        # Try to start at a newline to avoid partial lines
        newline_pos = truncated.find('\n')
        if newline_pos > 0:
            truncated = truncated[newline_pos+1:]
    
    return truncated, True, original_token_count, original_line_count


def load_truncation_template(template_type: str = "python_output") -> str:
    """
    Load the truncation message template.
    
    Args:
        template_type: Type of template to load ("python_output" or "bash_output")
        
    Returns:
        Template string for the truncation message
    """
    template_path = Path(__file__).parent.parent / "prompts" / "truncation.yaml"
    
    try:
        with open(template_path, 'r') as f:
            templates = yaml.safe_load(f)
        
        return templates.get("truncation_messages", {}).get(template_type, {}).get("message", 
            "--- Output truncated due to size limitations ---")
    except Exception:
        # Fallback template if file can't be loaded
        return "--- Output truncated due to size limitations ---"


def format_truncation_message(output: str, is_truncated: bool, original_tokens: int, 
                             original_lines: int, max_lines: int, template_type: str = "python_output") -> str:
    """
    Format the truncated output with a truncation message if needed.
    
    Args:
        output: The truncated output
        is_truncated: Whether truncation occurred
        original_tokens: Original token count
        original_lines: Original line count
        max_lines: Maximum line count used for truncation
        template_type: Type of template to use
        
    Returns:
        Formatted output with truncation message if needed
    """
    if not is_truncated:
        return output
    
    # Load the appropriate template
    template = load_truncation_template(template_type)
    
    # Determine size unit (tokens or KB)
    if original_tokens > 1000:
        size_value = original_tokens / 1000
        size_unit = "K tokens"
    else:
        size_value = original_tokens
        size_unit = "tokens"
    
    # Format the message
    message = template.format(
        original_size=round(size_value, 1),
        size_unit=size_unit,
        original_lines=original_lines,
        max_lines=max_lines
    )
    
    # Append the message to the output
    return f"{output}\n\n{message}"


def make_session_blob(ns: dict) -> bytes:
    """
    Create a serialized blob of the session namespace, excluding unserializable objects.
    
    Args:
        ns: Namespace dictionary to serialize
        
    Returns:
        Serialized bytes of the clean namespace
    """
    clean = {}
    for name, val in ns.items():
        try:
            # Try serializing just this one object
            cloudpickle.dumps(val)
        except Exception:
            # drop anything that fails
            continue
        else:
            clean[name] = val

    return cloudpickle.dumps(clean)


def _run_shell(
    command: List[str],
    timeout: int = 10,
    workdir: str = None
) -> Dict[str, Any]:
    """
    Execute a shell command securely with proper timeout and error handling.
    
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
    try:
        # Set working directory if provided
        cwd = os.path.expanduser(workdir) if workdir else None
        
        # Check if this is a command that needs bash -c wrapping
        if len(command) > 0:
            # Special handling for bash login shells to avoid profile loading errors
            if command[0] == "bash" and len(command) >= 3 and command[1] == "-lc":
                # Create a clean environment that doesn't load user profile files
                env = os.environ.copy()
                env.update({
                    "BASH_ENV": "/dev/null",
                    "ENV": "/dev/null",
                    "BASH_PROFILE": "/dev/null",
                    "PROFILE": "/dev/null"
                })
                # Replace -lc with -c to avoid loading login profiles
                modified_command = ["bash", "-c", command[2]]
                process = subprocess.run(
                    modified_command,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                    check=False,
                    env=env
                )
            # If the command already uses bash -c, use it directly
            # This handles heredoc syntax and other complex shell constructs
            elif command[0] == "bash" and len(command) >= 3 and command[1] == "-c":
                process = subprocess.run(
                    command,
                    shell=False,  # No need for shell=True as we're explicitly using bash -c
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                    check=False
                )
            # Special handling for interpreter commands with inline code execution flags
            # This covers python -c, node -e, ruby -e, perl -e, etc.
            elif len(command) >= 3 and command[0] in ["python", "node", "ruby", "perl", "php", "deno"] and command[1] in ["-c", "-e", "--eval", "--execute"]:
                # Execute the interpreter command directly without shell wrapping
                process = subprocess.run(
                    command,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                    check=False
                )
            else:
                # Check if the command contains heredoc syntax
                command_str = " ".join(command)
                if "<<" in command_str and any(f"<<'{token}'" in command_str or f'<<"{token}"' in command_str or f"<<{token}" in command_str for token in ["EOF", "EOL", "END", "HEREDOC", "PY", "JS", "RUBY", "PHP"]):
                    # For commands with heredoc, pass directly to bash -c without additional quoting
                    process = subprocess.run(
                        ["bash", "-c", command_str],
                        shell=False,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=cwd,
                        check=False
                    )
                else:
                    # For all other commands, wrap in bash -c to handle shell operators
                    # and properly quote arguments that need quoting
                    
                    # Shell operators that should not be quoted
                    shell_operators = ['|', '&&', '||', '>', '<', '>>', '<<', ';']
                    
                    # Quote each part that needs quoting
                    quoted_parts = []
                    for part in command:
                        if part in shell_operators:
                            # Don't quote shell operators
                            quoted_parts.append(part)
                        else:
                            # Use shlex.quote to properly escape special characters
                            quoted_parts.append(shlex.quote(part))
                    
                    shell_command = " ".join(quoted_parts)
                    process = subprocess.run(
                        ["bash", "-c", shell_command],
                        shell=False,  # Using explicit bash -c instead of shell=True
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        cwd=cwd,
                        check=False
                    )
        else:
            # Empty command
            return {
                "stdout": "",
                "stderr": "Empty command",
                "exit_code": 1
            }
        
        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "exit_code": process.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "exit_code": 124  # Standard timeout exit code
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Error executing command: {str(e)}",
            "exit_code": 1
        }


def _run_python(
    code: str,
    globals_dict: Dict[str, Any] | None = None,
    locals_dict: Dict[str, Any] | None = None,
    authorized_imports: List[str] | None = None,
    authorized_functions: List[str] | None = None,
    trusted_code: bool = False,
    check_string_obfuscation: bool = True,
):
    """
    Execute Python code in a controlled environment with proper error handling.
    
    Args:
        code: Python code to execute
        globals_dict: Global variables dictionary
        locals_dict: Local variables dictionary
        authorized_imports: List of authorized imports that user code may access. Wildcards (e.g. "numpy.*") are supported. A value of None disables the allow-list and only blocks dangerous modules.
        authorized_functions: List of authorized dangerous functions that user code may access. A value of None disables the allow-list and blocks all dangerous functions.
        trusted_code: If True, skip security checks. Should only be used for framework code, tools, or default executed code.
        check_string_obfuscation: If True (default), check for string obfuscation techniques. Set to False to allow legitimate use of base64 encoding and other string manipulations.
        
    Returns:
        Dictionary containing execution results
    """
    import contextlib
    import traceback
    import io
    import ast
    import builtins  # Needed for import hook
    import sys

    # ------------------------------------------------------------------
    # 1. Static safety analysis – refuse code containing dangerous imports or functions
    # ------------------------------------------------------------------
    validate_code_safety(code, authorized_imports=authorized_imports, 
                        authorized_functions=authorized_functions, trusted_code=trusted_code,
                        check_string_obfuscation=check_string_obfuscation)

    # Make copies to avoid mutating the original parameters
    globals_dict = globals_dict or {}
    locals_dict = locals_dict or {}
    updated_globals = globals_dict.copy()
    updated_locals = locals_dict.copy()
    
    # Only pre-import a **minimal** set of safe modules so that common helper
    # functions work out of the box without giving user code access to the
    # full standard library.  Anything outside this list must be imported
    # explicitly by the user – and will be blocked by the safety layer above
    # if considered dangerous.
    essential_modules = ['requests', 'json', 'time', 'datetime', 're', 'random', 'math','cloudpickle']
    
    for module_name in essential_modules:
        try:
            module = __import__(module_name)
            updated_globals[module_name] = module
            #print(f"✓ {module_name} module loaded successfully")
        except ImportError:
            print(f"⚠️  Warning: {module_name} module not available")
    
    # Variable to store print output
    output_buffer = []
    
    # Create a custom print function that captures output
    def custom_print(*args, **kwargs):
        # Get the sep and end kwargs, defaulting to ' ' and '\n'
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        
        # Convert all arguments to strings and join them
        output = sep.join(str(arg) for arg in args) + end
        
        # Store the output
        output_buffer.append(output)
    
    # Add the custom print function to the globals
    #updated_globals['print'] = custom_print
    
    # Parse the code
    try:
        tree = ast.parse(code, mode="exec")
        compiled = compile(tree, filename="<ast>", mode="exec")
    except SyntaxError as e:
        # Return syntax error without executing
        return {
            "printed_output": "", 
            "return_value": None, 
            "stderr": "", 
            "error_traceback": f"Syntax error: {str(e)}",
            "updated_globals": updated_globals,
            "updated_locals": updated_locals
        }
    
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()   
    # Execute with exception handling
    error_traceback = None
    output = None

    # Merge all variables into globals to avoid scoping issues with generator expressions
    # When exec() is called with both globals and locals, generator expressions can't
    # access local variables. By using only globals, everything runs in global scope.
    merged_globals = updated_globals.copy()
    merged_globals.update(updated_locals)

    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        try:
            # Add 'exec' to authorized_functions for internal use
            internal_authorized_functions = ['exec','eval']
            if authorized_functions is not None and not isinstance(authorized_functions, bool):
                internal_authorized_functions.extend(authorized_functions)
            
            # Execute with only globals - this fixes generator expression scoping issues
            # Use the function_safety_context to block dangerous functions during execution
            with function_safety_context(authorized_functions=internal_authorized_functions, trusted_code=trusted_code):
                output = exec(compiled, merged_globals)
            
            # Update both dictionaries with any new variables created during execution
            for key, value in merged_globals.items():
                if key not in updated_globals and key not in updated_locals:
                    updated_locals[key] = value
                elif key in updated_locals or key not in updated_globals:
                    updated_locals[key] = value
                updated_globals[key] = value
        except Exception:
            # Capture the full traceback as a string
            error_traceback = traceback.format_exc()
            
            # CRITICAL FIX: Even when an exception occurs, we need to update the globals and locals
            # with any variables that were successfully created/modified before the exception
            for key, value in merged_globals.items():
                # Skip special variables and modules
                if key.startswith('__') or key in ['builtins', 'traceback', 'contextlib', 'io', 'ast', 'sys']:
                    continue
                    
                # Update both dictionaries with the current state
                if key in updated_locals or key not in updated_globals:
                    updated_locals[key] = value
                updated_globals[key] = value

    # Join all captured output
    #printed_output = ''.join(output_buffer)  
    printed_output = stdout_buf.getvalue()
    stderr_output = stderr_buf.getvalue()
    error_traceback_output = error_traceback

    return {
        "printed_output": printed_output, 
        "return_value": output, 
        "stderr": stderr_output, 
        "error_traceback": error_traceback_output,
        "updated_globals": updated_globals,
        "updated_locals": updated_locals
    } 

def detect_system_capabilities() -> Dict[str, Any]:
    """Detect runtime system capabilities for dynamic bash tool enhancement.
    
    Returns:
        Dictionary containing:
        - os_info: Basic OS information
        - modern_tools: Available modern CLI tools
        - find_capabilities: BSD vs GNU find detection
        - shells: Available shells
        - preferred_alternatives: Mapping of commands to better alternatives
    """
    capabilities = {
        'os_info': {
            'system': platform.system(),
            'release': platform.release(),
            'machine': platform.machine(),
            'is_macos': platform.system() == 'Darwin',
            'is_linux': platform.system() == 'Linux',
            'is_windows': platform.system() == 'Windows'
        },
        'modern_tools': {},
        'find_capabilities': {
            'supports_maxdepth': False,
            'type': 'unknown'
        },
        'shells': [],
        'preferred_alternatives': {}
    }
    
    # Detect modern CLI tools
    modern_tools_to_check = {
        'rg': {'purpose': 'faster grep', 'alternative_to': 'grep'},
        'fd': {'purpose': 'faster find', 'alternative_to': 'find'},
        'bat': {'purpose': 'better cat with syntax highlighting', 'alternative_to': 'cat'},
        'exa': {'purpose': 'better ls with git integration', 'alternative_to': 'ls'},
        'tree': {'purpose': 'directory tree visualization', 'alternative_to': 'ls -R'},
        'jq': {'purpose': 'JSON processing', 'alternative_to': 'grep/sed'},
        'fzf': {'purpose': 'fuzzy finder', 'alternative_to': 'grep'},
        'ag': {'purpose': 'fast grep', 'alternative_to': 'grep'}
    }
    
    for tool, info in modern_tools_to_check.items():
        try:
            result = subprocess.run(['which', tool], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                capabilities['modern_tools'][tool] = {
                    'available': True,
                    'path': result.stdout.strip(),
                    **info
                }
                # Build preferred alternatives mapping
                alt_to = info.get('alternative_to')
                if alt_to:
                    if alt_to not in capabilities['preferred_alternatives']:
                        capabilities['preferred_alternatives'][alt_to] = []
                    capabilities['preferred_alternatives'][alt_to].append(tool)
            else:
                capabilities['modern_tools'][tool] = {'available': False, **info}
        except:
            capabilities['modern_tools'][tool] = {'available': False, **info}
    
    # Check find capabilities (BSD vs GNU)
    try:
        # Test if find supports -maxdepth (GNU feature)
        test_result = subprocess.run(
            ['find', '.', '-maxdepth', '0', '-type', 'd'],
            capture_output=True, text=True, timeout=3, cwd='/tmp'
        )
        if test_result.returncode == 0:
            capabilities['find_capabilities']['supports_maxdepth'] = True
            capabilities['find_capabilities']['type'] = 'GNU'
        else:
            capabilities['find_capabilities']['type'] = 'BSD'
    except:
        # Fallback detection based on OS
        if capabilities['os_info']['is_macos']:
            capabilities['find_capabilities']['type'] = 'BSD'
        elif capabilities['os_info']['is_linux']:
            capabilities['find_capabilities']['supports_maxdepth'] = True
            capabilities['find_capabilities']['type'] = 'GNU'
    
    # Check available shells
    common_shells = ['bash', 'zsh', 'sh', 'fish', 'tcsh', 'dash']
    for shell in common_shells:
        try:
            result = subprocess.run(['which', shell], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                capabilities['shells'].append({
                    'name': shell,
                    'path': result.stdout.strip()
                })
        except:
            pass
    
    return capabilities


def get_system_info():
    """Get essential system information for bash command execution with platform-specific guidance"""
    info = []
    
    # OS information
    os_name = platform.system()
    info.append(f"OS: {os_name}")
    info.append(f"OS Version: {platform.release()}")
    info.append(f"Architecture: {platform.machine()}")
    
    # Shell information
    try:
        shell = os.environ.get('SHELL', 'unknown')
        info.append(f"Default Shell: {shell}")
    except:
        info.append("Default Shell: unknown")
    
    # Path separator
    info.append(f"Path Separator: '{os.path.sep}'")
    
    # Check if common shells are available
    common_shells = ['bash', 'zsh', 'sh', 'fish', 'tcsh']
    available_shells = []
    for shell in common_shells:
        try:
            result = subprocess.run(['which', shell], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                available_shells.append(shell)
        except:
            pass
    if available_shells:
        info.append(f"Available Shells: {', '.join(available_shells)}")
    
    # Add platform-specific command guidance
    if os_name == "Darwin":  # macOS
        info.append("PLATFORM NOTES: macOS/BSD - find lacks -maxdepth, use: ls -1d */ | head -20 for dirs")
        info.append("SIMPLE COMMANDS: ls -la (list), mkdir -p (create dirs), ps aux (processes)")
    elif os_name == "Linux":
        info.append("PLATFORM NOTES: Linux/GNU - find supports -maxdepth, ls --color available")
        info.append("SIMPLE COMMANDS: ls -la --color (list), find . -maxdepth 1 -type d (dirs)")
    elif os_name == "Windows":
        info.append("PLATFORM NOTES: Windows - prefer PowerShell cmdlets or WSL for Unix commands")
        info.append("SIMPLE COMMANDS: dir (list), mkdir (create dirs), tasklist (processes)")
    
    return ' | '.join(info)


def get_command_alternatives(capabilities: Dict[str, Any]) -> Dict[str, str]:
    """Generate command alternative suggestions based on detected capabilities."""
    alternatives = {
        # Basic commands with platform-safe alternatives
        'find': 'Use glob_tool() instead for file patterns',
        'grep': 'Use grep_tool() for content search',
        'cat': 'Use read_file() for file reading',
        'head': 'Use read_file() with limit parameter',
        'tail': 'Use read_file() with offset parameter',
    }
    
    # Add modern tool alternatives if available
    modern_tools = capabilities.get('modern_tools', {})
    preferred_alts = capabilities.get('preferred_alternatives', {})
    
    for old_cmd, new_tools in preferred_alts.items():
        available_tools = [tool for tool in new_tools if modern_tools.get(tool, {}).get('available', False)]
        if available_tools:
            tool_suggestions = []
            for tool in available_tools:
                purpose = modern_tools[tool].get('purpose', '')
                tool_suggestions.append(f"{tool} ({purpose})")
            alternatives[old_cmd] = f"Try: {' or '.join(tool_suggestions)}"
    
    return alternatives


def get_helpful_error_tip(command: str, stderr: str, capabilities: Optional[Dict[str, Any]] = None) -> str:
    """Generate helpful error tips based on command failure patterns and detected capabilities."""
    try:
        if capabilities is None:
            capabilities = detect_system_capabilities()
            
        os_info = capabilities['os_info']
        find_caps = capabilities['find_capabilities']
        modern_tools = capabilities['modern_tools']
        alternatives = get_command_alternatives(capabilities)
        
        tips = []
        
        # Enhanced system context with actionable info
        os_type = "macOS (BSD)" if os_info['is_macos'] else "Linux (GNU)" if os_info['is_linux'] else "Windows"
        tips.append(f"🔍 CONTEXT: Running on {os_type} | Platform-specific help below")
        
        # Enhanced pattern detection with specific solutions
        command_lower = command.lower()
        stderr_lower = stderr.lower()
        
        # Find command issues
        if "find" in command:
            if "-maxdepth" in command and not find_caps['supports_maxdepth']:
                tips.append("❌ Your system's find doesn't support -maxdepth (BSD find)")
                tips.append("✅ Try: ls -1d */ | head -20 (for directories)")
                if modern_tools.get('fd', {}).get('available'):
                    tips.append(f"✅ Or use fd: {modern_tools['fd']['path']}")
            elif any(complex_flag in command for complex_flag in ['-exec', '-print0', '-delete']):
                tips.append("❌ Complex find operations are platform-dependent")
                tips.append("✅ Use glob_tool() for file patterns or simpler ls commands")
            else:
                tips.append("❌ find commands often fail across platforms")
                tips.append(f"✅ {alternatives.get('find', 'Use glob_tool() instead')}")
        
        # ls command issues  
        elif "ls" in command:
            if "--color" in command and os_info['is_macos']:
                tips.append("❌ macOS ls doesn't support --color (GNU option)")
                tips.append("✅ Try: ls -la (or ls -G for color on macOS)")
            elif any(gnu_flag in command for gnu_flag in ['--time-style', '--group-directories-first']):
                tips.append("❌ GNU ls options not available on BSD/macOS")
                tips.append("✅ Use basic ls -la for cross-platform compatibility")
                if modern_tools.get('exa', {}).get('available'):
                    tips.append(f"✅ Or try exa: {modern_tools['exa']['path']} -la")
        
        # grep command issues
        elif "grep" in command:
            if "-r" in command or "--recursive" in command:
                tips.append("❌ Avoid bash grep for recursive file searches")
                tips.append("✅ Use grep_tool(pattern='...', output_mode='content') instead")
                if modern_tools.get('rg', {}).get('available'):
                    tips.append(f"✅ Or use ripgrep: {modern_tools['rg']['path']} 'pattern'")
            elif any(pattern in stderr_lower for pattern in ['invalid option', 'unrecognized option']):
                tips.append("❌ grep option compatibility varies across systems")
                tips.append("✅ Use basic grep patterns or grep_tool() for consistency")
        
        # File reading commands
        elif any(cmd in command for cmd in ['cat', 'head', 'tail', 'less', 'more']):
            file_cmd = next(cmd for cmd in ['cat', 'head', 'tail', 'less', 'more'] if cmd in command)
            tips.append(f"❌ Use read_file() instead of {file_cmd} for better error handling")
            if file_cmd == 'head':
                tips.append("✅ read_file(path, limit=N) for first N lines")
            elif file_cmd == 'tail':
                tips.append("✅ read_file(path, offset=-N) for last N lines") 
            else:
                tips.append("✅ read_file(path) for full file content")
            
            if modern_tools.get('bat', {}).get('available') and file_cmd == 'cat':
                tips.append(f"✅ Or use bat for syntax highlighting: {modern_tools['bat']['path']}")
        
        # Permission and sandbox errors
        elif any(perm_error in stderr_lower for perm_error in ['permission denied', 'operation not permitted', 'not allowed']):
            tips.append("❌ Permission/sandbox restriction detected")
            tips.append("✅ Try alternative approach with specialized tools")
            tips.append("✅ Check if you need different working directory")
        
        # Command not found errors
        elif "command not found" in stderr_lower or "not found" in stderr_lower:
            missing_cmd = None
            # Try to extract the missing command
            if "command not found" in stderr_lower:
                parts = stderr_lower.split("command not found")
                if parts:
                    missing_cmd = parts[0].strip().split()[-1] if parts[0].strip() else None
            
            tips.append("❌ Command not available on this system")
            if missing_cmd and missing_cmd in alternatives:
                tips.append(f"✅ {alternatives[missing_cmd]}")
            tips.append("✅ Use specialized tools (read_file, glob_tool, grep_tool)")
        
        # Network/connectivity issues
        elif any(net_error in stderr_lower for net_error in ['connection', 'network', 'timeout', 'unreachable']):
            tips.append("❌ Network connectivity issue detected")
            tips.append("✅ Check network connection and retry")
            tips.append("✅ Consider using local alternatives if available")
        
        # File/directory not found
        elif any(not_found in stderr_lower for not_found in ['no such file', 'cannot access', 'does not exist']):
            tips.append("❌ File or directory not found")
            tips.append("✅ Check file path and working directory")
            tips.append("✅ Use ls -la to verify current directory contents")
        
        # Enhanced fallback with progressive complexity
        if len(tips) <= 1:  # Only system info
            tips.append("🎯 NEXT ACTIONS:")
            tips.append("1. Try simpler command: ls -la, mkdir -p, ps aux")
            tips.append("2. Use specialized tools: read_file(), glob_tool(), grep_tool()")
            tips.append("3. Check command syntax for your platform")
            
            # Suggest available modern alternatives with clear benefits
            available_modern = [name for name, info in modern_tools.items() if info.get('available')]
            if available_modern:
                high_value_tools = [t for t in available_modern if t in ['rg', 'fd', 'bat']]
                if high_value_tools:
                    tips.append(f"4. Try faster alternatives: {', '.join(high_value_tools)}")
        
        return " | ".join(tips)
        
    except Exception as e:
        # Enhanced fallback that includes basic capability detection
        try:
            basic_info = get_system_info()
            return f"System: {basic_info} | Error generating tips: {str(e)}"
        except:
            return f"Error generating tips: {str(e)}"


def generate_dynamic_bash_description(capabilities: Optional[Dict[str, Any]] = None) -> str:
    """Generate dynamic bash tool description based on detected system capabilities.
    
    Applies prompt engineering best practices:
    - Clear hierarchy with specific examples
    - Platform-specific guidance
    - Action-oriented instructions
    - Error prevention through steering
    """
    if capabilities is None:
        capabilities = detect_system_capabilities()
    
    os_info = capabilities['os_info']
    find_caps = capabilities['find_capabilities']
    modern_tools = capabilities['modern_tools']
    
    # Base description with clear tool hierarchy
    description = """Execute shell commands safely in provider sandbox.

🚨 CRITICAL: USE SPECIALIZED TOOLS FIRST (they handle cross-platform issues automatically):
• File operations: read_file(), write_file(), update_file() instead of cat/echo/>
• File discovery: glob_tool(pattern="**/*.py") instead of find commands  
• Content search: grep_tool(pattern="...", output_mode="content") instead of grep/rg
• These tools are SAFER and FASTER than equivalent bash commands

"""
    
    # Dynamic platform-specific quick reference
    if os_info['is_macos']:
        description += """🍎 YOUR SYSTEM: macOS (BSD commands)
SAFE COMMANDS THAT WORK:
• ls -la, ls -1d */  (directories)
• mkdir -p, ps aux, df -h
• git status, npm test, which node

COMMANDS THAT FAIL ON YOUR SYSTEM:
❌ find . -maxdepth 1  → ✅ ls -1d */ | head -20
❌ ls --color         → ✅ ls -G  
❌ sed -i ''          → ✅ Use update_file() instead

"""
    elif os_info['is_linux']:
        description += """🐧 YOUR SYSTEM: Linux (GNU commands)
SAFE COMMANDS THAT WORK:
• ls -la --color, find . -maxdepth 1 -type d
• mkdir -p, ps aux, df -h  
• git status, npm test, which node

ENHANCED OPTIONS AVAILABLE:
✅ find . -maxdepth 1 -type d (GNU find supports this)
✅ ls --color=auto (GNU ls supports this)
✅ Advanced grep/sed options work

"""
    elif os_info['is_windows']:
        description += """🪟 YOUR SYSTEM: Windows
RECOMMENDED APPROACH:
• Use PowerShell commands or WSL for Unix compatibility
• Basic: dir, mkdir, tasklist
• Consider: wsl bash for Unix commands

"""
    
    # Modern tools with clear value proposition
    available_modern = {name: info for name, info in modern_tools.items() if info.get('available', False)}
    if available_modern:
        description += "⚡ FASTER ALTERNATIVES DETECTED ON YOUR SYSTEM:\n"
        priority_tools = {'rg': '10x faster than grep', 'fd': '5x faster than find', 'bat': 'syntax highlighting'}
        
        for tool in ['rg', 'fd', 'bat']:  # Show high-impact tools first
            if tool in available_modern:
                info = available_modern[tool]
                benefit = priority_tools.get(tool, info.get('purpose', ''))
                description += f"• {tool}: {benefit} at {info['path']}\n"
        
        # Show remaining tools
        for tool, info in available_modern.items():
            if tool not in ['rg', 'fd', 'bat']:
                description += f"• {tool}: {info.get('purpose', '')} at {info['path']}\n"
        description += "\n"
    
    # Tier-based command safety guide
    description += """🎯 BASH COMMAND SAFETY GUIDE:

TIER 1 - SAFE EVERYWHERE (use these freely):
• Build: npm run build, pytest, cargo test, make install
• Git: git status, git add, git commit, git log --oneline -10
• System: ps aux, df -h, uname -a, whoami, which command
• Directories: mkdir -p path/to/dir, ls -la

TIER 2 - PLATFORM DIFFERENCES (check examples above):
• find (BSD vs GNU differences)
• ls with flags (--color works on Linux, -G on macOS)
• sed -i (syntax varies)

TIER 3 - AVOID IN BASH (use specialized tools):
❌ Reading files: cat, head, tail, less, more
❌ Writing files: echo >, cat >, tee
❌ Searching: grep -r, find -name, locate
❌ File operations: cp, mv, rm (for code files)

"""
    
    # Quick error recovery guide
    description += f"""🔧 WHEN COMMANDS FAIL:
1. Check if you're on {'macOS (BSD)' if os_info['is_macos'] else 'Linux (GNU)' if os_info['is_linux'] else 'Windows'}
2. Try simpler version: ls -la instead of ls --color
3. Use specialized tool: read_file() instead of cat
4. Look for error patterns: "not found" = tool not available"""
    
    if find_caps['type'] == 'BSD':
        description += "\n5. On your system: Use ls -1d */ instead of find . -maxdepth 1"
    
    description += """

📋 COMMON WORKFLOWS:

Check project status:
bash(command="git status && ls -la")
bash(command="which node python pip")

Run tests and builds:  
bash(command="npm test")
bash(command="python -m pytest tests/ -v")
bash(command="cargo build --release")

Process management:
bash(command="ps aux | grep python")
bash(command="kill -9 $(pgrep -f 'process_name')")

System diagnostics:
bash(command="df -h")  # Disk space
bash(command="free -h")  # Memory (Linux)
bash(command="top -l 1 -s 0 | head -10")  # Processes snapshot

Arguments:
• command (string): Shell command to execute
• absolute_workdir (optional): Working directory  
• timeout (optional): Max seconds (default: 60)

Returns: {stdout: "...", stderr: "...", exit_code: 0}
"""
    
    return description