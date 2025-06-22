# TinyAgent code execution safety utilities
# -----------------------------------------
#
# This helper module defines *very* lightweight safeguards that are applied
# before running any user-supplied Python code inside the Modal sandbox.
# The goal is **not** to build a full blown secure interpreter (this would
# require a much more sophisticated setup à la Pyodide or the `python-secure`
# project).  Instead we implement the following pragmatic defence layers:
#
# 1.  Static AST inspection of the submitted code to detect direct `import` or
#     `from … import …` statements that reference known dangerous modules
#     (e.g. `os`, `subprocess`, …).  This prevents the *most common* attack
#     vector where an LLM attempts to read or modify the host file-system or
#     spawn sub-processes.
# 2.  Runtime patching of the built-in `__import__` hook so that *dynamic*
#     imports carried out via `importlib` or `__import__(…)` are blocked at
#     execution time as well.
# 3.  Static AST inspection to detect calls to dangerous functions like `exec`,
#     `eval`, `compile`, etc. that could be used to bypass security measures.
# 4.  Runtime patching of built-in dangerous functions to prevent their use
#     at execution time.
#
# The chosen approach keeps the TinyAgent runtime *fast* and *lean* while
# still providing a reasonable first line of defence against obviously
# malicious code.

from __future__ import annotations

import ast
import builtins
import warnings
from typing import Iterable, List, Set, Sequence, Any, Callable
import contextlib

__all__ = [
    "DANGEROUS_MODULES",
    "DANGEROUS_FUNCTIONS",
    "RUNTIME_BLOCKED_FUNCTIONS",
    "validate_code_safety",
    "install_import_hook",
    "function_safety_context",
]

# ---------------------------------------------------------------------------
# Threat model / deny-list
# ---------------------------------------------------------------------------

# Non-exhaustive list of modules that grant (direct or indirect) access to the
# underlying operating system, spawn sub-processes, perform unrestricted I/O,
# or allow the user to circumvent the static import analysis performed below.
DANGEROUS_MODULES: Set[str] = {
    "builtins",  # Gives access to exec/eval etc.
    "ctypes",
    "importlib",
    "io",
    "multiprocessing",
    "os",
    "pathlib",
    "pty",
    "shlex",
    "shutil",
    "signal",
    "socket",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
    "webbrowser",
}

# List of dangerous built-in functions that could be used to bypass security
# measures or execute arbitrary code
DANGEROUS_FUNCTIONS: Set[str] = {
    "exec",
    "eval",
    "compile",
    "__import__",
    "open",
    "input",
    "breakpoint",
}

# Functions that should be blocked at runtime (a subset of DANGEROUS_FUNCTIONS)
RUNTIME_BLOCKED_FUNCTIONS: Set[str] = {
    "exec",
    "eval",
}

# Essential modules that are always allowed, even in untrusted code
# These are needed for the framework to function properly
ESSENTIAL_MODULES: Set[str] = {
    "cloudpickle",
    "tinyagent",
    "json",
    "time",
    "datetime",
    "requests",
    
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _is_allowed(module_root: str, allowed: Sequence[str] | None) -> bool:
    """Return ``True`` if *module_root* is within *allowed* specification."""

    if allowed is None:
        # No explicit allow-list means everything that is **not** in the
        # dangerous list is considered fine.
        return True

    # Fast path – wildcard allows everything.
    if "*" in allowed:
        return True

    for pattern in allowed:
        if pattern.endswith(".*"):
            if module_root == pattern[:-2]:
                return True
        elif module_root == pattern:
            return True
    return False


# ---------------------------------------------------------------------------
# Static analysis helpers
# ---------------------------------------------------------------------------

def _iter_import_nodes(tree: ast.AST) -> Iterable[ast.AST]:
    """Yield all *import* related nodes from *tree*."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node


def _extract_module_roots(node: ast.AST) -> List[str]:
    """Return the *top-level* module names referenced in an import node."""
    roots: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            roots.append(alias.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        if node.module is not None:
            roots.append(node.module.split(".")[0])
    return roots


def _check_for_dangerous_function_calls(tree: ast.AST, authorized_functions: Sequence[str] | None = None) -> Set[str]:
    """
    Check for calls to dangerous functions in the AST.
    
    Parameters
    ----------
    tree
        The AST to check
    authorized_functions
        Optional white-list of dangerous functions that are allowed
        
    Returns
    -------
    Set[str]
        Set of dangerous function names found in the code
    """
    dangerous_calls = set()
    
    # Convert authorized_functions to a set if it's not None
    authorized_set = set(authorized_functions) if authorized_functions is not None else set()
    
    for node in ast.walk(tree):
        # Check for direct function calls: func()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in DANGEROUS_FUNCTIONS and func_name not in authorized_set:
                dangerous_calls.add(func_name)
        
        # Check for calls via string literals in exec/eval: exec("import os")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ["exec", "eval"]:
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                dangerous_calls.add(f"{node.func.id} with string literal")
        
        # Check for attribute access: builtins.exec()
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in DANGEROUS_FUNCTIONS:
                if isinstance(node.func.value, ast.Name):
                    module_name = node.func.value.id
                    func_name = f"{module_name}.{node.func.attr}"
                    if node.func.attr not in authorized_set:
                        dangerous_calls.add(func_name)
        
        # Check for string manipulation that could be used to bypass security
        # For example: e = "e" + "x" + "e" + "c"; e("import os")
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.BinOp):
                    # Check if we're building a string that could be a dangerous function name
                    potential_name = _extract_string_from_binop(node.value)
                    if potential_name in DANGEROUS_FUNCTIONS:
                        dangerous_calls.add(f"string manipulation to create '{potential_name}'")
        
        # Check for getattr(builtins, "exec") pattern
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                attr_name = node.args[1].value
                if attr_name in DANGEROUS_FUNCTIONS and attr_name not in authorized_set:
                    if isinstance(node.args[0], ast.Name):
                        module_name = node.args[0].id
                        dangerous_calls.add(f"getattr({module_name}, '{attr_name}')")
    
    return dangerous_calls


def _extract_string_from_binop(node: ast.BinOp) -> str:
    """
    Attempt to extract a string from a binary operation node.
    This helps detect string concatenation that builds dangerous function names.
    
    For example: "e" + "x" + "e" + "c" -> "exec"
    
    Parameters
    ----------
    node
        The binary operation node
        
    Returns
    -------
    str
        The extracted string, or empty string if not extractable
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    
    if not isinstance(node, ast.BinOp):
        return ""
    
    # Handle string concatenation
    if isinstance(node.op, ast.Add):
        left_str = _extract_string_from_binop(node.left)
        right_str = _extract_string_from_binop(node.right)
        return left_str + right_str
    
    return ""


def _detect_string_obfuscation(tree: ast.AST) -> bool:
    """
    Detect common string obfuscation techniques that might be used to bypass security.
    
    Parameters
    ----------
    tree
        The AST to check
        
    Returns
    -------
    bool
        True if suspicious string manipulation is detected
    """
    suspicious_patterns = False
    
    for node in ast.walk(tree):
        # Check for chr() usage to build strings
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "chr":
            suspicious_patterns = True
            break
            
        # Check for ord() usage in combination with string operations
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ord":
            suspicious_patterns = True
            break
            
        # Check for suspicious string joins with list comprehensions
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and 
            node.func.attr == "join" and isinstance(node.args[0], ast.ListComp)):
            suspicious_patterns = True
            break
            
        # Check for base64 decoding
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and 
            node.func.attr in ["b64decode", "b64encode", "b32decode", "b32encode", "b16decode", "b16encode"]):
            suspicious_patterns = True
            break
            
        # Check for string formatting that might be used to build dangerous code
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            suspicious_patterns = True
            break
            
    return suspicious_patterns


def validate_code_safety(code: str, *, authorized_imports: Sequence[str] | None = None, 
                        authorized_functions: Sequence[str] | None = None, trusted_code: bool = False) -> None:
    """Static validation of user code.

    Parameters
    ----------
    code
        The user supplied source code (single string or multi-line).
    authorized_imports
        Optional white-list restricting which modules may be imported.  If
        *None* every module that is not in :pydata:`DANGEROUS_MODULES` is
        allowed.  Wildcards are supported – e.g. ``["numpy.*"]`` allows any
        sub-package of *numpy*.
    authorized_functions
        Optional white-list of dangerous functions that are allowed.
    trusted_code
        If True, skip security checks. This should only be used for code that is part of the
        framework, developer-provided tools, or default executed code.
    """
    # Skip security checks for trusted code
    if trusted_code:
        return

    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError:
        # If the code does not even parse we leave the error handling to the
        # caller (who will attempt to compile / execute the code later on).
        return

    blocked: set[str] = set()
    
    # Convert authorized_imports to a set if it's not None
    combined_allowed = None
    if authorized_imports is not None:
        combined_allowed = set(list(authorized_imports) + list(ESSENTIAL_MODULES))
    
    
    for node in _iter_import_nodes(tree):
        for root in _extract_module_roots(node):

            # Check if module is explicitly allowed
            if combined_allowed is not None:
                allowed = _is_allowed(root, combined_allowed)
            else:
                # If no explicit allow-list, only allow if not in DANGEROUS_MODULES
                allowed = root not in DANGEROUS_MODULES

            if root in DANGEROUS_MODULES and allowed and combined_allowed is not None:
                warnings.warn(
                    f"⚠️  Importing dangerous module '{root}' was allowed due to authorized_imports configuration.",
                    stacklevel=2,
                )
            
            # Block dangerous modules unless explicitly allowed
            if root in DANGEROUS_MODULES and not allowed:
                blocked.add(root)
            # If there is an explicit allow-list, block everything not on it
            elif authorized_imports is not None and not allowed and root not in ESSENTIAL_MODULES:
                blocked.add(root)

    # ------------------------------------------------------------------
    # Detect direct calls to __import__ (e.g.  __import__("os")) in *untrusted* code
    # ------------------------------------------------------------------
    for _node in ast.walk(tree):
        if isinstance(_node, ast.Call):
            # Pattern: __import__(...)
            if isinstance(_node.func, ast.Name) and _node.func.id == "__import__":
                raise ValueError("Usage of __import__ is not allowed in untrusted code.")
            # Pattern: builtins.__import__(...)
            if (
                isinstance(_node.func, ast.Attribute)
                and isinstance(_node.func.value, ast.Name)
                and _node.func.attr == "__import__"
                and _node.func.value.id == "builtins"
            ):
                raise ValueError("Usage of builtins.__import__ is not allowed in untrusted code.")

    # ------------------------------------------------------------------
    # Detect calls to dangerous functions (e.g. exec, eval) in *untrusted* code
    # ------------------------------------------------------------------
    dangerous_calls = _check_for_dangerous_function_calls(tree, authorized_functions)
    if dangerous_calls:
        offenders = ", ".join(sorted(dangerous_calls))
        raise ValueError(f"Usage of dangerous function(s) {offenders} is not allowed in untrusted code.")

    # ------------------------------------------------------------------
    # Detect string obfuscation techniques that might be used to bypass security
    # ------------------------------------------------------------------
    if _detect_string_obfuscation(tree):
        raise ValueError("Suspicious string manipulation detected that could be used to bypass security.")

    if blocked:
        offenders = ", ".join(sorted(blocked))
        msg = f"Importing module(s) {offenders} is not allowed."
        if authorized_imports is not None:
            msg += " Allowed imports are: " + ", ".join(sorted(authorized_imports))
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# Runtime import hook
# ---------------------------------------------------------------------------

def install_import_hook(
    *,
    blocked_modules: Set[str] | None = None,
    authorized_imports: Sequence[str] | None = None,
    trusted_code: bool = False,
) -> None:
    """Monkey-patch the built-in ``__import__`` to deny run-time imports.

    The hook is *process-wide* but extremely cheap to install.  It simply
    checks the *root* package name against the provided *blocked_modules*
    (defaults to :pydata:`DANGEROUS_MODULES`) and raises ``ImportError`` if the
    import should be denied.

    Calling this function **multiple times** is safe – only the first call
    installs the wrapper, subsequent calls are ignored.
    
    Parameters
    ----------
    blocked_modules
        Set of module names to block. Defaults to DANGEROUS_MODULES.
    authorized_imports
        Optional white-list restricting which modules may be imported.
    trusted_code
        If True, skip security checks. This should only be used for code that is part of the
        framework, developer-provided tools, or default executed code.
    """
    # Skip security checks for trusted code
    if trusted_code:
        return

    blocked_modules = blocked_modules or DANGEROUS_MODULES
    
    # Convert authorized_imports to a set if it's not None
    authorized_set = set(authorized_imports) if authorized_imports is not None else None
    
    # Create a combined set for allowed modules (essential + authorized)
    combined_allowed = None
    if authorized_set is not None:
        combined_allowed = set(list(authorized_set) + list(ESSENTIAL_MODULES))

    # Check if we have already installed the hook to avoid double-wrapping.
    if getattr(builtins, "__tinyagent_import_hook_installed", False):
        return

    original_import = builtins.__import__

    def _safe_import(
        name: str,
        globals=None,
        locals=None,
        fromlist=(),
        level: int = 0,
    ):  # type: ignore[override]
        root = name.split(".")[0]
        
        # Check if module is explicitly allowed
        if combined_allowed is not None:
            allowed = _is_allowed(root, combined_allowed)
        else:
            # If no explicit allow-list, only allow if not in blocked_modules
            allowed = root not in blocked_modules

        if root in blocked_modules and allowed and authorized_set is not None:
            warnings.warn(
                f"⚠️  Importing dangerous module '{root}' was allowed due to authorized_imports configuration.",
                stacklevel=2,
            )
        elif root in blocked_modules and not allowed:
            raise ImportError(
                f"Import of module '{name}' is blocked by TinyAgent safety policy"
            )
        elif authorized_set is not None and not allowed and root not in ESSENTIAL_MODULES:
            raise ImportError(
                f"Import of module '{name}' is not in the authorized imports list: {', '.join(sorted(authorized_set))}"
            )

        return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = _safe_import  # type: ignore[assignment]
    setattr(builtins, "__tinyagent_import_hook_installed", True)


# ---------------------------------------------------------------------------
# Runtime function hook
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def function_safety_context(
    *,
    blocked_functions: Set[str] | None = None,
    authorized_functions: Sequence[str] | None = None,
    trusted_code: bool = False,
):
    """
    Context manager for safely executing code with dangerous functions blocked.
    
    Parameters
    ----------
    blocked_functions
        Set of function names to block. Defaults to RUNTIME_BLOCKED_FUNCTIONS.
    authorized_functions
        Optional white-list of dangerous functions that are allowed.
    trusted_code
        If True, skip security checks. This should only be used for code that is part of the
        framework, developer-provided tools, or default executed code.
    """
    if trusted_code:
        yield
        return
        
    # Install the function hook
    blocked_functions = blocked_functions or RUNTIME_BLOCKED_FUNCTIONS
    
    # Convert authorized_functions to a set if it's not None
    authorized_set = set(authorized_functions) if authorized_functions is not None else set()
    
    # Store original functions
    original_functions = {}
    
    # Replace dangerous functions with safe versions
    for func_name in blocked_functions:
        if hasattr(builtins, func_name) and func_name not in authorized_set:
            original_functions[func_name] = getattr(builtins, func_name)
            
            # Create a closure to capture the function name
            def make_safe_function(name):
                def safe_function(*args, **kwargs):
                    raise RuntimeError(f"Function '{name}' is blocked by TinyAgent safety policy")
                return safe_function
            
            # Replace the function
            setattr(builtins, func_name, make_safe_function(func_name))
    
    try:
        yield
    finally:
        # Restore original functions
        for func_name, original_func in original_functions.items():
            setattr(builtins, func_name, original_func)