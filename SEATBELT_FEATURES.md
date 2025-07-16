# SeatbeltProvider Features

The SeatbeltProvider in TinyAgent offers enhanced security and flexibility for code execution on macOS systems. It leverages macOS's sandbox-exec (seatbelt) mechanism to create a secure execution environment.

## Key Features

### 1. Additional Directory Access

You can specify additional directories for read and write access:

```python
agent = TinyCodeAgent(
    provider="seatbelt",
    provider_config={
        "additional_read_dirs": ["/path/to/read/dir"],
        "additional_write_dirs": ["/path/to/write/dir"]
    },
    local_execution=True  # Required for seatbelt
)
```

This allows the sandboxed environment to access specific directories while maintaining security.

### 2. Special Command Handling

#### Python/Node.js/Ruby/Perl/PHP Commands with -c Flag

The SeatbeltProvider properly handles interpreter commands with inline code execution flags:

```python
# This works correctly with special characters in the code
await agent.run('python -c "import sys; print(\'Special chars: \\\'quotes\\\' work\')"')
```

#### Heredoc Syntax

Heredoc syntax in shell commands is properly supported:

```python
await agent.run('''
cat <<EOF > /tmp/output.txt
This is a test of heredoc syntax
It works across multiple lines
EOF
''')
```

#### Git Commands

Git commands are supported with a custom environment that prevents profile loading errors:

```python
await agent.run('git init my_repo')
await agent.run('git status')
```

### 3. Security Enhancements

#### ANSI Color Code Stripping

Terminal color codes are automatically stripped from command output for better readability:

```python
# Color codes will be stripped from the output
await agent.run('ls --color=always')
```

#### Clean Environment for Shell Commands

The provider creates a clean environment for shell commands, preventing profile loading errors:

```python
# This works without loading user profiles that might cause permission errors
await agent.run('bash -lc "echo Hello"')
```

## Usage Example

```python
from tinyagent.code_agent.tiny_code_agent import TinyCodeAgent
import asyncio
import os

async def main():
    # Create test directories
    test_read_dir = os.path.join(os.getcwd(), "test_read_dir")
    test_write_dir = os.path.join(os.getcwd(), "test_write_dir")
    os.makedirs(test_read_dir, exist_ok=True)
    os.makedirs(test_write_dir, exist_ok=True)
    
    # Create a test file
    with open(os.path.join(test_read_dir, "test.txt"), "w") as f:
        f.write("This is a test file")
    
    # Create agent with seatbelt provider
    agent = TinyCodeAgent(
        model="your-model-name",
        provider="seatbelt",
        provider_config={
            "additional_read_dirs": [test_read_dir],
            "additional_write_dirs": [test_write_dir],
            "bypass_shell_safety": True,
            "additional_safe_shell_commands": ["git", "python"]
        },
        local_execution=True
    )
    
    # Test reading from additional read directory
    await agent.run(f"Read the file in {test_read_dir}")
    
    # Test writing to additional write directory
    await agent.run(f"Create a file in {test_write_dir}")
    
    # Test Python command with special characters
    await agent.run('Run python -c "print(\'Hello with quotes\')"')
    
    # Clean up
    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
```

## Requirements

- macOS system with sandbox-exec available
- Local execution mode (remote execution not supported)

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `seatbelt_profile` | Custom seatbelt profile as a string | Default restrictive profile |
| `seatbelt_profile_path` | Path to a custom seatbelt profile file | None |
| `python_env_path` | Path to Python environment | System Python |
| `additional_read_dirs` | List of additional directories for read access | [] |
| `additional_write_dirs` | List of additional directories for write access | [] |
| `bypass_shell_safety` | Whether to bypass shell command safety checks | True |
| `additional_safe_shell_commands` | Additional shell commands to consider safe | None |
| `additional_safe_control_operators` | Additional shell control operators to consider safe | None | 