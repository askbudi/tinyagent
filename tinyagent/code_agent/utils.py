import sys
import cloudpickle
from typing import Dict, Any
from .safety import validate_code_safety


def clean_response(resp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean the response from code execution, keeping only relevant fields.
    
    Args:
        resp: Raw response dictionary from code execution
        
    Returns:
        Cleaned response with only essential fields
    """
    return {k: v for k, v in resp.items() if k in ['printed_output', 'return_value', 'stderr', 'error_traceback']}


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


def _run_python(
    code: str,
    globals_dict: Dict[str, Any] | None = None,
    locals_dict: Dict[str, Any] | None = None,
    authorized_imports: list[str] | None = None,
    trusted_code: bool = False,
):
    """
    Execute Python code in a controlled environment with proper error handling.
    
    Args:
        code: Python code to execute
        globals_dict: Global variables dictionary
        locals_dict: Local variables dictionary
        authorized_imports: List of authorized imports that user code may access. Wildcards (e.g. "numpy.*") are supported. A value of None disables the allow-list and only blocks dangerous modules.
        trusted_code: If True, skip security checks. Should only be used for framework code, tools, or default executed code.
        
    Returns:
        Dictionary containing execution results
    """
    import contextlib
    import traceback
    import io
    import ast
    import builtins  # Needed for import hook

    # ------------------------------------------------------------------
    # 1. Static safety analysis – refuse code containing dangerous imports
    # ------------------------------------------------------------------
    validate_code_safety(code, authorized_imports=authorized_imports, trusted_code=trusted_code)


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
    
    tree = ast.parse(code, mode="exec")
    compiled = compile(tree, filename="<ast>", mode="exec")
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    # Execute with stdout+stderr capture and exception handling
    error_traceback = None
    output = None

    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        try:
            # Merge all variables into globals to avoid scoping issues with generator expressions
            # When exec() is called with both globals and locals, generator expressions can't
            # access local variables. By using only globals, everything runs in global scope.
            merged_globals = updated_globals.copy()
            merged_globals.update(updated_locals)
            
            # Execute with only globals - this fixes generator expression scoping issues
            output = exec(code, merged_globals)
            
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