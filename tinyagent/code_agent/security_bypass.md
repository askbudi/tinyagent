# TinyAgent Security Bypass Mechanism

## Overview

TinyAgent implements a security mechanism that prevents user code from importing potentially dangerous modules. However, there are legitimate cases where the framework itself or developer-provided tools need to import these modules. The security bypass mechanism allows trusted code to bypass these security checks.

## How It Works

The security bypass mechanism works through a `trusted_code` flag that can be passed to the security functions:

1. `validate_code_safety(code, authorized_imports=None, trusted_code=False)`
2. `install_import_hook(blocked_modules=None, authorized_imports=None, trusted_code=False)`
3. `_run_python(code, globals_dict=None, locals_dict=None, authorized_imports=None, trusted_code=False)`

When `trusted_code=True`, the security checks are bypassed, allowing the code to import any module.

## When to Use

The `trusted_code` flag should only be set to `True` for:

1. **Framework Code**: Code that is part of the TinyAgent framework itself
2. **Developer-Provided Tools**: Tools provided by the developer that need to import restricted modules
3. **Default Executed Code**: Code that is executed by default when initializing the environment

## Implementation in Modal Provider

The Modal Provider automatically sets `trusted_code=True` for:

- The first execution that includes framework code and tool definitions
- Default Python code provided during initialization

For all subsequent user code executions, `trusted_code` is set to `False`.

## Example

```python
# Framework code (trusted)
provider._python_executor("""
import cloudpickle
import sys
import os

# Framework initialization code
""", trusted_code=True)

# User code (untrusted)
provider._python_executor("""
# This will fail if it tries to import restricted modules
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3]})
""", trusted_code=False)
```

## Testing

To verify the security bypass mechanism works correctly, run the test suite:

```bash
cd tinyagent/code_agent/tests
python run_security_tests.py
```

This will run both unit tests and integration tests for the security bypass mechanism. 