# Seatbelt Provider for TinyCodeAgent

The Seatbelt Provider adds sandboxed execution capabilities to TinyCodeAgent using macOS's `sandbox-exec` (Seatbelt) technology. This provider allows you to execute Python code and shell commands within a macOS sandbox for enhanced security.

## Requirements

- macOS operating system
- `sandbox-exec` command available (standard on macOS)
- Local execution mode enabled (`local_execution=True`)

## Features

- Sandboxed execution of Python code
- Sandboxed execution of shell commands
- Support for custom seatbelt profiles
- Integration with existing Python environments
- Compatible with TinyCodeAgent's code tools and user variables
- Stateful execution with persistent variables between runs
- Configurable safety settings

## Usage

### Basic Usage

```python
from tinyagent.code_agent import TinyCodeAgent

# Check if seatbelt is supported on this system
if TinyCodeAgent.is_seatbelt_supported():
    # Create TinyCodeAgent with seatbelt provider
    agent = TinyCodeAgent(
        model="gpt-4.1-mini",
        provider="seatbelt",
        provider_config={
            # You can provide either a profile string or a path to a profile file
            "seatbelt_profile": seatbelt_profile_string,
            # OR
            # "seatbelt_profile_path": "/path/to/seatbelt.sb",
            
            # Optional: Path to Python environment
            "python_env_path": "/path/to/python/env",
        },
        local_execution=True,  # Required for seatbelt
    )
```

### Using an Existing Seatbelt Profile

```python
from tinyagent.code_agent import TinyCodeAgent

# Path to seatbelt profile file
seatbelt_profile_path = "/path/to/seatbelt.sb"

# Create TinyCodeAgent with seatbelt provider
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    provider="seatbelt",
    provider_config={
        "seatbelt_profile_path": seatbelt_profile_path,
    },
    local_execution=True,  # Required for seatbelt
)
```

### Using a Custom Seatbelt Profile String

```python
from tinyagent.code_agent import TinyCodeAgent
import os

# Create a custom seatbelt profile
seatbelt_profile = f"""(version 1)

; Default to deny everything
(deny default)

; Allow network connections with proper DNS resolution
(allow network*)
(allow network-outbound)
(allow mach-lookup)

; Allow process execution
(allow process-exec)
(allow process-fork)
(allow signal (target self))

; Restrict file read to current path and system files
(deny file-read* (subpath "/Users"))
(allow file-read*
  (subpath "{os.getcwd()}")
  (subpath "/usr")
  (subpath "/System")
  (subpath "/Library")
  (subpath "/bin")
  (subpath "/sbin")
  (subpath "/opt")
  (subpath "/private/tmp")
  (subpath "/private/var/tmp")
  (subpath "/dev")
  (subpath "/etc")
  (literal "/")
  (literal "/."))

; Allow write access to specified folder and temp directories
(deny file-write* (subpath "/"))
(allow file-write*
  (subpath "{os.getcwd()}")
  (subpath "/private/tmp")
  (subpath "/private/var/tmp")
  (subpath "/dev"))

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
"""

# Create TinyCodeAgent with seatbelt provider
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    provider="seatbelt",
    provider_config={
        "seatbelt_profile": seatbelt_profile,
    },
    local_execution=True,  # Required for seatbelt
)
```

### Configuring Safety Settings

The SeatbeltProvider allows you to configure safety settings for code execution. By default, the seatbelt provider is more permissive than the Modal or local providers, since the sandbox already provides a security layer.

```python
from tinyagent.code_agent import TinyCodeAgent

# Create TinyCodeAgent with seatbelt provider and custom safety settings
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    provider="seatbelt",
    provider_config={
        "seatbelt_profile_path": "/path/to/seatbelt.sb",
        
        # Code safety settings
        "authorized_imports": ["*"],  # Allow all imports within the sandbox
        "authorized_functions": ["eval", "exec"],  # Allow potentially dangerous functions
        "check_string_obfuscation": False,  # Don't check for string obfuscation
        
        # Shell safety settings (enabled by default for seatbelt)
        "bypass_shell_safety": True,  # Bypass shell command safety checks
        "additional_safe_shell_commands": ["*"],  # Allow all shell commands
        # Or specify additional commands:
        # "additional_safe_shell_commands": ["npm", "node", "python", "pip", "git"],
        "additional_safe_control_operators": ["*"]  # Allow all control operators
    },
    local_execution=True,  # Required for seatbelt
)
```

### Stateful Execution

The SeatbeltProvider supports stateful execution, meaning variables and imports persist between runs:

```python
# First run - create variables
response1 = await agent.run("""
Create a variable called data with the values [1, 2, 3, 4, 5]
Import numpy as np
Calculate the mean and standard deviation of the data
""")

# Second run - use variables from the first run
response2 = await agent.run("""
# The 'data' variable and numpy import are still available
Add 10 to each value in data
Calculate the new mean and standard deviation
""")
```

### Integration with sandbox_start.sh

If you have an existing sandbox setup using a script like `sandbox_start.sh`, you can integrate it with the seatbelt provider:

```python
from tinyagent.code_agent import TinyCodeAgent

# Path to seatbelt profile file
seatbelt_profile_path = "/path/to/seatbelt.sb"

# Path to Python environment (from sandbox_start.sh)
python_env_path = "/path/to/python/env"

# Create TinyCodeAgent with seatbelt provider
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    provider="seatbelt",
    provider_config={
        "seatbelt_profile_path": seatbelt_profile_path,
        "python_env_path": python_env_path,
    },
    local_execution=True,  # Required for seatbelt
)
```

## Seatbelt Profile Format

A seatbelt profile is a text file that defines the sandbox rules. Here's a basic structure:

```
(version 1)

; Default to deny everything
(deny default)

; Allow network connections
(allow network*)
(allow network-outbound)
(allow mach-lookup)

; Allow process execution
(allow process-exec)
(allow process-fork)
(allow signal (target self))

; Restrict file read to specific paths
(deny file-read* (subpath "/Users"))
(allow file-read*
  (subpath "/path/to/allowed/directory")
  (subpath "/usr")
  (subpath "/System")
  (subpath "/Library")
  (subpath "/bin")
  (subpath "/sbin")
  (subpath "/opt")
  (subpath "/private/tmp")
  (subpath "/private/var/tmp")
  (subpath "/dev")
  (subpath "/etc")
  (literal "/")
  (literal "/."))

; Restrict file write to specific paths
(deny file-write* (subpath "/"))
(allow file-write*
  (subpath "/path/to/allowed/directory")
  (subpath "/private/tmp")
  (subpath "/private/var/tmp")
  (subpath "/dev"))

; Allow standard device operations
(allow file-write-data
  (literal "/dev/null")
  (literal "/dev/dtracehelper")
  (literal "/dev/tty")
  (literal "/dev/stdout")
  (literal "/dev/stderr"))

; Allow other necessary operations
(allow iokit-open)
(allow ipc-posix-shm)
(allow file-read-metadata)
(allow process-info-pidinfo)
(allow process-info-setcontrol)
```

## Implementation Details

### Stateful Execution

The SeatbeltProvider maintains state between runs by:

1. Serializing the Python environment state (globals and locals dictionaries) to a temporary file
2. Creating a wrapper script that loads the state, executes the code, and saves the updated state
3. Running the wrapper script in the sandbox
4. Loading the updated state back into the provider after execution

This approach allows variables, imports, and other state to persist between runs, similar to how the Modal provider works.

### Safety Measures

The SeatbeltProvider implements the same safety measures as the Modal provider:

1. **Static code analysis**: Checks for dangerous imports and function calls
2. **String obfuscation detection**: Optionally checks for attempts to obfuscate code
3. **Runtime function safety**: Restricts access to dangerous functions during execution
4. **Shell command safety**: Controls which shell commands can be executed

However, since the code is already running in a sandbox, the default safety settings are more permissive than in the Modal or local providers.

### Shell Command Safety

By default, the SeatbeltProvider bypasses shell command safety checks since the seatbelt sandbox already provides protection. You can control this behavior with the following options:

- `bypass_shell_safety`: If `True` (default for SeatbeltProvider), all shell commands are allowed. If `False`, only commands in the safe list are allowed.
- `additional_safe_shell_commands`: A list of additional shell commands to consider safe. Use `["*"]` to allow all commands.
- `additional_safe_control_operators`: A list of additional shell control operators to consider safe. Use `["*"]` to allow all operators.

The default safe commands include basic utilities like `ls`, `cat`, `grep`, etc. The default safe control operators include `&&`, `||`, `;`, and `|`.

## Examples

See the example scripts in the `examples/` directory:

- `seatbelt_example.py`: Basic example using a seatbelt profile with stateful execution
- `sandbox_start_example.py`: Example integrating with `sandbox_start.sh`

## Notes on Security

- The seatbelt provider adds an additional layer of security but is not a complete security solution.
- Always review and customize the seatbelt profile to match your security requirements.
- The default profile provided is restrictive but may need adjustments for your specific use case.
- For production use, consider creating a custom profile that follows the principle of least privilege.
- The combination of seatbelt sandboxing and code safety measures provides a robust security model.

## Future Development

- Support for Linux sandboxing mechanisms (e.g., seccomp, namespaces)
- Enhanced profile customization options
- Pre-defined profiles for common use cases 