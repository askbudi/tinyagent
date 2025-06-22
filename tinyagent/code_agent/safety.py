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
#
# The chosen approach keeps the TinyAgent runtime *fast* and *lean* while
# still providing a reasonable first line of defence against obviously
# malicious code.

from __future__ import annotations

import ast
import builtins
import warnings
from typing import Iterable, List, Set, Sequence

__all__ = [
    "DANGEROUS_MODULES",
    "validate_code_safety",
    "install_import_hook",
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


def validate_code_safety(code: str, *, authorized_imports: Sequence[str] | None = None, trusted_code: bool = False) -> None:
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