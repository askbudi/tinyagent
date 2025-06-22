# TinyCodeAgent Security Guide

This document provides a comprehensive overview of the security features implemented in TinyCodeAgent, explaining the security model, limitations, and how developers can use and modify these features.

## Table of Contents

1. [Security Model Overview](#security-model-overview)
2. [Security Features](#security-features)
3. [Security Limitations](#security-limitations)
4. [Usage Guide](#usage-guide)
5. [Customization Guide](#customization-guide)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

## Security Model Overview

TinyCodeAgent implements a lightweight but effective security model for executing untrusted Python code. Rather than attempting to build a full-blown secure interpreter (which would require a much more sophisticated setup like Pyodide or the `python-secure` project), TinyCodeAgent focuses on pragmatic defense layers that keep the runtime fast and lean while providing reasonable protection against common attack vectors.

The security model consists of four main defense layers:

1. **Static AST inspection for dangerous imports**: Detects and blocks direct `import` or `from ... import ...` statements that reference known dangerous modules.
2. **Runtime import hook**: Blocks dynamic imports carried out via `importlib` or `__import__()` at execution time.
3. **Static AST inspection for dangerous functions**: Detects and blocks calls to dangerous functions like `exec`, `eval`, `compile`, etc.
4. **Runtime function blocking**: Uses a context manager to temporarily replace dangerous built-in functions with safe versions during code execution.

## Security Features

### Dangerous Modules Detection

TinyCodeAgent maintains a list of dangerous modules that could be used to access the underlying operating system, spawn sub-processes, perform unrestricted I/O, or circumvent security measures:

```python
DANGEROUS_MODULES = {
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
```

### Dangerous Functions Detection

TinyCodeAgent also maintains a list of dangerous built-in functions that could be used to bypass security measures or execute arbitrary code:

```python
DANGEROUS_FUNCTIONS = {
    "exec",
    "eval",
    "compile",
    "__import__",
    "open",
    "input",
    "breakpoint",
}
```

A subset of these functions are blocked at runtime:

```python
RUNTIME_BLOCKED_FUNCTIONS = {
    "exec",
    "eval",
}
```

### String Obfuscation Detection

TinyCodeAgent can detect common string obfuscation techniques that might be used to bypass security, such as:

- Using `chr()` to build strings character by character
- Using `ord()` in combination with string operations
- Using suspicious string joins with list comprehensions
- Using base64 encoding/decoding
- Using string formatting that might be used to build dangerous code

### Whitelist Support

TinyCodeAgent supports whitelisting specific modules and functions:

- `authorized_imports`: A list of module names that are allowed to be imported, even if they are in the dangerous modules list
- `authorized_functions`: A list of function names that are allowed to be used, even if they are in the dangerous functions list

## Security Limitations

While TinyCodeAgent provides reasonable security for many use cases, it has some limitations:

1. **Not a Sandbox**: TinyCodeAgent does not provide true isolation or sandboxing. It's designed to prevent obvious security breaches but is not suitable for executing completely untrusted code.

2. **Static Analysis Limitations**: The static analysis can only detect direct calls to dangerous functions and imports. It may miss more sophisticated attacks that use indirect methods to access dangerous functionality.

3. **Runtime Hook Limitations**: The runtime hooks only protect against a subset of dangerous functions. They cannot prevent all possible ways to execute arbitrary code.

4. **No Memory or CPU Limits**: TinyCodeAgent does not implement memory or CPU usage limits. Malicious code could still cause denial-of-service by consuming excessive resources.

5. **No Network Isolation**: TinyCodeAgent does not restrict network access. Untrusted code could still make outbound network connections.

## Usage Guide

### Basic Usage

To execute code with the default security settings:

```python
from tinyagent.code_agent.utils import _run_python

# Execute code with default security settings
result = _run_python('print("Hello, world!")')
print(result['printed_output'])
```

### Using Whitelists

To allow specific dangerous modules or functions:

```python
from tinyagent.code_agent.utils import _run_python

# Allow the 'os' module and the 'exec' function
result = _run_python(
    'import os; print(os.getcwd())',
    authorized_imports=['os'],
    authorized_functions=['exec']
)
print(result['printed_output'])
```

### Trusted Code

For code that you trust and want to execute without security restrictions:

```python
from tinyagent.code_agent.utils import _run_python

# Execute trusted code without security restrictions
result = _run_python(
    'import os; print(os.getcwd())',
    trusted_code=True
)
print(result['printed_output'])
```

## Customization Guide

### Adding Custom Dangerous Modules

To add custom dangerous modules to the default list:

```python
from tinyagent.code_agent.safety import DANGEROUS_MODULES

# Add custom dangerous modules
DANGEROUS_MODULES.add("my_dangerous_module")
```

### Adding Custom Dangerous Functions

To add custom dangerous functions to the default list:

```python
from tinyagent.code_agent.safety import DANGEROUS_FUNCTIONS

# Add custom dangerous functions
DANGEROUS_FUNCTIONS.add("my_dangerous_function")
```

### Adding Custom Runtime Blocked Functions

To add custom functions to block at runtime:

```python
from tinyagent.code_agent.safety import RUNTIME_BLOCKED_FUNCTIONS

# Add custom runtime blocked functions
RUNTIME_BLOCKED_FUNCTIONS.add("my_dangerous_function")
```

### Extending String Obfuscation Detection

To extend the string obfuscation detection, you can modify the `_detect_string_obfuscation` function in `safety.py`:

```python
def _detect_string_obfuscation(tree: ast.AST) -> bool:
    """
    Detect common string obfuscation techniques that might be used to bypass security.
    """
    suspicious_patterns = False
    
    for node in ast.walk(tree):
        # Add your custom detection logic here
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "my_suspicious_function":
            suspicious_patterns = True
            break
            
    return suspicious_patterns
```

## Best Practices

1. **Default to Deny**: Start with the most restrictive security settings and only whitelist modules and functions that are absolutely necessary.

2. **Use Whitelists Sparingly**: Only whitelist dangerous modules and functions when absolutely necessary, and be specific about what you allow.

3. **Validate Inputs**: Always validate inputs before passing them to `_run_python` to prevent injection attacks.

4. **Monitor Resource Usage**: Implement external monitoring for memory and CPU usage to prevent denial-of-service attacks.

5. **Regular Security Reviews**: Regularly review the security model and update it as new vulnerabilities are discovered.

6. **Defense in Depth**: Don't rely solely on TinyCodeAgent's security features. Implement additional security measures at other layers of your application.

7. **Understand the Risks**: Be aware of the security limitations and make informed decisions about what code to execute.

8. **Keep Dependencies Updated**: Regularly update TinyCodeAgent and its dependencies to benefit from security fixes.

9. **Test Security Features**: Regularly test the security features with potential attack vectors to ensure they are working as expected.

10. **Document Security Decisions**: Document any security decisions, especially when whitelisting dangerous modules or functions, to help with future security reviews.

## Troubleshooting

### Common Issues

#### 1. Function is blocked by TinyAgent safety policy

**Problem**: You see an error like `RuntimeError: Function 'exec' is blocked by TinyAgent safety policy`

**Solution**: This is the runtime function hook working as intended. If you need to use this function, you have two options:
- Add the function to your authorized functions list: `authorized_functions=['exec']`
- Use trusted mode for code you know is safe: `trusted_code=True`

#### 2. Import of module is blocked by TinyAgent safety policy

**Problem**: You see an error like `ImportError: Import of module 'os' is blocked by TinyAgent safety policy`

**Solution**: This is the import hook working as intended. If you need to use this module, you have two options:
- Add the module to your authorized imports list: `authorized_imports=['os']`
- Use trusted mode for code you know is safe: `trusted_code=True`

#### 3. String obfuscation detected

**Problem**: You see an error like `ValueError: Suspicious string manipulation detected that could be used to bypass security.`

**Solution**: The code is using string manipulation techniques that look like they're trying to bypass security. If this is a false positive, you can:
- Modify the `_detect_string_obfuscation` function to be less strict
- Use trusted mode for code you know is safe: `trusted_code=True`

#### 4. Issues with the function_safety_context

**Problem**: The `function_safety_context` context manager is causing unexpected issues.

**Solution**: If you're experiencing problems with the context manager, you can:
- Make sure you're using it correctly in a `with` statement
- Check if there are any conflicts with other code that might be modifying builtins
- Consider using only the static analysis part of the security system by setting `trusted_code=True` 