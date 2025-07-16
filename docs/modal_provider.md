# Modal Provider

The Modal provider uses [Modal.com](https://modal.com) to execute code in a remote, sandboxed environment. This provides strong isolation and security guarantees, making it ideal for executing untrusted code.

## Features

- **Remote execution**: Code runs in Modal's cloud environment, not on your local machine
- **Sandboxing**: Strong isolation between executions
- **Automatic dependency management**: Easy installation of Python packages
- **Scalable**: Can handle multiple concurrent executions

## Configuration

### Basic Configuration

```python
from tinyagent.code_agent import TinyCodeAgent

# Create TinyCodeAgent with Modal provider
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    provider="modal",
    provider_config={
        "pip_packages": ["pandas", "matplotlib", "scikit-learn"],  # Additional packages to install
        "apt_packages": ["git", "curl", "nodejs"],  # System packages to install
        "python_version": "3.10",  # Python version to use
        "sandbox_name": "my-code-sandbox",  # Name for the Modal sandbox
        "local_execution": False,  # Use Modal's remote execution (default)
    }
)
```

### Configuring Safety Settings

The ModalProvider allows you to configure safety settings for code execution:

```python
from tinyagent.code_agent import TinyCodeAgent

# Create TinyCodeAgent with modal provider and custom safety settings
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    provider="modal",
    provider_config={
        # Code safety settings
        "authorized_imports": ["pandas", "numpy.*"],  # Allow only specific imports
        "authorized_functions": [],  # Don't allow any dangerous functions
        "check_string_obfuscation": True,  # Check for string obfuscation
        
        # Shell safety settings (disabled by default for Modal)
        "bypass_shell_safety": False,  # Keep shell command safety checks (default)
        "additional_safe_shell_commands": ["npm", "node", "python"],  # Add specific commands
        "additional_safe_control_operators": []  # No additional operators
    }
)
```

### Shell Command Safety

By default, the ModalProvider enforces strict shell command safety checks. Only a predefined list of safe commands (like `ls`, `cat`, `grep`, etc.) are allowed. You can customize this behavior with the following options:

- `bypass_shell_safety`: If `True`, all shell commands are allowed. Default is `False` for Modal provider.
- `additional_safe_shell_commands`: A list of additional shell commands to consider safe. Use `["*"]` to allow all commands.
- `additional_safe_control_operators`: A list of additional shell control operators to consider safe. Use `["*"]` to allow all operators.

The default safe commands include basic utilities like `ls`, `cat`, `grep`, etc. The default safe control operators include `&&`, `||`, `;`, and `|`.

## Examples

### Basic Usage

```python
import asyncio
from tinyagent.code_agent import TinyCodeAgent

async def main():
    # Create the agent with Modal provider
    agent = TinyCodeAgent(
        model="gpt-4.1-mini",
        provider="modal",
        provider_config={
            "pip_packages": ["pandas", "matplotlib"],
        }
    )
    
    # Run a prompt
    response = await agent.run("""
    Create a pandas DataFrame with sample data and plot a histogram of the values.
    """)
    
    print(response)
    
    # Clean up
    await agent.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Using Local Execution Mode

Modal also supports local execution for development and testing:

```python
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    provider="modal",
    provider_config={
        "local_execution": True,  # Use Modal's local execution mode
        "pip_packages": ["pandas", "matplotlib"],
    }
)
```

### Using Modal Secrets

You can pass secrets to the Modal environment:

```python
agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    provider="modal",
    provider_config={
        "modal_secrets": {
            "API_KEY": "your-api-key",
            "DATABASE_URL": "your-db-url"
        }
    }
)
``` 