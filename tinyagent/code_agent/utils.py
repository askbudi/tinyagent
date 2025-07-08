import sys
import cloudpickle
import subprocess
import os
from typing import Dict, Any, List, Tuple
from .safety import validate_code_safety, function_safety_context
import shlex
import yaml
from pathlib import Path
import re


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