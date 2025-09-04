# DockerProvider Documentation

The DockerProvider is TinyAgent's cross-platform solution for secure code execution using Docker containers. It provides equivalent functionality to platform-specific providers (SeatbeltProvider for macOS, BubblewrapProvider for Linux) while working on any system with Docker installed.

## Overview

The DockerProvider executes Python code and shell commands within Docker containers, providing:

- **Cross-platform compatibility** - Works on Windows, macOS, and Linux
- **Security isolation** - Code runs in sandboxed containers with limited privileges
- **Resource controls** - Configurable memory, CPU, and process limits
- **Network isolation** - Optional network access control
- **State persistence** - Maintains Python globals/locals between executions
- **Volume mounting** - Controlled file system access

## Quick Start

### Basic Usage

```python
from tinyagent.code_agent import TinyCodeAgent

# Simple usage with auto-detection
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="docker"  # Explicitly use Docker
)

response = await agent.run_async("Calculate the fibonacci sequence up to 100")
```

### With Custom Configuration

```python
from tinyagent.code_agent import TinyCodeAgent

# Advanced configuration
docker_config = {
    "docker_image": "tinyagent-runtime:latest",
    "enable_network": True,
    "memory_limit": "1g",
    "cpu_limit": "2.0",
    "timeout": 300,
}

agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="docker",
    provider_config=docker_config
)
```

## Configuration Options

### Basic Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `docker_image` | `str` | `"tinyagent-runtime:latest"` | Docker image to use |
| `enable_network` | `bool` | `False` | Enable network access in containers |
| `memory_limit` | `str` | `"512m"` | Memory limit (e.g., "1g", "512m") |
| `cpu_limit` | `str` | `"1.0"` | CPU limit (e.g., "2.0", "0.5") |
| `timeout` | `int` | `300` | Default timeout in seconds |
| `auto_pull_image` | `bool` | `True` | Automatically pull missing images |

### Advanced Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `container_name_prefix` | `str` | `"tinyagent"` | Prefix for container names |
| `volume_mount_path` | `str` | `"/workspace"` | Container workspace path |
| `additional_read_dirs` | `List[str]` | `[]` | Host directories to mount read-only |
| `additional_write_dirs` | `List[str]` | `[]` | Host directories to mount read-write |
| `environment_variables` | `Dict[str, str]` | `{}` | Environment variables for container |

## Security Features

### Container Security

The DockerProvider implements multiple security layers:

```python
# Default security settings
docker_config = {
    # Run as non-root user (UID 1000)
    # Drop all Linux capabilities
    # Read-only root filesystem
    # No new privileges
    # Process and memory limits
    
    "enable_network": False,    # Network isolation by default
    "memory_limit": "512m",     # Prevent memory exhaustion
    "cpu_limit": "1.0",         # CPU usage limits
}
```

### Shell Command Safety

```python
# Enable shell command filtering
docker_config = {
    "bypass_shell_safety": False,  # Enable safety checks
    "additional_safe_shell_commands": ["custom_tool"],
}

agent = TinyCodeAgent(
    provider="docker",
    provider_config=docker_config,
    check_string_obfuscation=True  # Enable Python safety checks
)
```

## Volume Mounts and File Access

### Read-Only Data Access

```python
docker_config = {
    "additional_read_dirs": [
        "/path/to/data",
        "/path/to/configs"
    ]
}
```

### Read-Write Access

```python
docker_config = {
    "additional_write_dirs": [
        "/path/to/output",
        "/path/to/workspace"
    ]
}
```

### Complete File Access Example

```python
import tempfile
import os

# Create directories
with tempfile.TemporaryDirectory() as temp_dir:
    data_dir = os.path.join(temp_dir, "data")
    output_dir = os.path.join(temp_dir, "output")
    os.makedirs(data_dir)
    os.makedirs(output_dir)
    
    # Configure Docker with volume mounts
    docker_config = {
        "additional_read_dirs": [data_dir],
        "additional_write_dirs": [output_dir],
    }
    
    agent = TinyCodeAgent(
        provider="docker",
        provider_config=docker_config
    )
    
    # Agent can now read from data_dir and write to output_dir
    await agent.run_async(f"Process files from {data_dir} and save results to {output_dir}")
```

## Environment Variables

### Basic Environment Setup

```python
docker_config = {
    "environment_variables": {
        "API_KEY": "your-api-key",
        "DEBUG": "true",
        "DATA_PATH": "/workspace/data"
    }
}
```

### Dynamic Environment Management

```python
from tinyagent.code_agent.providers.docker_provider import DockerProvider

# Create provider
provider = DockerProvider()

# Add environment variables
provider.add_environment_variable("NEW_VAR", "new_value")

# Remove environment variables
provider.remove_environment_variable("OLD_VAR")

# Set multiple variables
provider.set_environment_variables({
    "VAR1": "value1",
    "VAR2": "value2"
})

# Get current environment
env_vars = provider.get_environment_variables()
```

## Network Access

### Enabling Network Access

```python
# Enable network for HTTP requests, API calls, etc.
docker_config = {
    "enable_network": True
}

agent = TinyCodeAgent(
    provider="docker", 
    provider_config=docker_config
)

# Now the agent can make network requests
await agent.run_async("""
import requests
response = requests.get('https://api.github.com/user')
print(response.status_code)
""")
```

### Git Operations with Network

```python
docker_config = {
    "enable_network": True,
    "environment_variables": {
        "GIT_AUTHOR_NAME": "TinyAgent",
        "GIT_AUTHOR_EMAIL": "tinyagent@example.com",
        # Optional: for private repos
        # "GITHUB_TOKEN": "your_token",
        # "GITHUB_USERNAME": "your_username"
    }
}
```

## Docker Image Management

### Using the Default Image

The DockerProvider includes an optimized runtime image with common packages:

```bash
# Build the default image
cd docker/execution-runtime
./build.sh

# Or use docker-compose
docker-compose build
```

### Custom Images

```python
# Use your own image
docker_config = {
    "docker_image": "your-org/custom-python:latest",
    "auto_pull_image": True  # Pull if not available locally
}
```

### Image Requirements

Your Docker image should:

1. **Run as non-root user** (UID 1000 recommended)
2. **Include Python 3.8+** with essential packages
3. **Have a `/workspace` directory** for mounting
4. **Include `cloudpickle`** for state serialization

Example Dockerfile:
```dockerfile
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 tinyagent

# Install required packages
RUN pip install cloudpickle requests numpy pandas

# Create workspace
RUN mkdir /workspace && chown tinyagent:tinyagent /workspace

# Switch to non-root user
USER tinyagent
WORKDIR /workspace
```

## Performance Optimization

### Resource Tuning

```python
# For CPU-intensive tasks
docker_config = {
    "memory_limit": "2g",
    "cpu_limit": "4.0",
    "timeout": 600
}

# For memory-intensive tasks
docker_config = {
    "memory_limit": "8g", 
    "cpu_limit": "2.0"
}

# For lightweight tasks
docker_config = {
    "memory_limit": "256m",
    "cpu_limit": "0.5"
}
```

### Container Reuse

The DockerProvider automatically manages container lifecycle:

- **State persistence**: Python globals/locals preserved between executions
- **Automatic cleanup**: Containers removed after use
- **Resource limits**: Prevents resource leaks

## Error Handling and Debugging

### Timeout Handling

```python
# Configure timeouts
docker_config = {
    "timeout": 120  # 2-minute default timeout
}

# Per-execution timeout
result = await provider.execute_python(
    ["import time; time.sleep(5)"], 
    timeout=10
)
```

### Error Diagnostics

```python
# Enable detailed logging
from tinyagent.hooks.logging_manager import LoggingManager

log_manager = LoggingManager(level="DEBUG")

agent = TinyCodeAgent(
    provider="docker",
    log_manager=log_manager
)

# Check execution results
result = await agent.run_async("problematic code")
if "error_traceback" in result:
    print("Error occurred:", result["error_traceback"])
```

### Common Issues and Solutions

#### Docker Not Available

```python
from tinyagent.code_agent.providers.docker_provider import DockerProvider

if not DockerProvider.is_supported():
    print("Docker is not available. Please:")
    print("1. Install Docker Desktop (Windows/macOS) or Docker Engine (Linux)")
    print("2. Start the Docker daemon")
    print("3. Verify with: docker --version")
```

#### Image Pull Failures

```python
# Disable automatic pulling and use local images only
docker_config = {
    "auto_pull_image": False,
    "docker_image": "python:3.11-slim"  # Use widely available image
}
```

#### Permission Errors

```python
# Ensure proper volume mount permissions
import os

# Make directories readable/writable
data_dir = "/path/to/data"
os.chmod(data_dir, 0o755)  # rwxr-xr-x

docker_config = {
    "additional_read_dirs": [data_dir]
}
```

## Integration with Other Providers

### Provider Selection Logic

```python
# Automatic provider selection with Docker as fallback
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    local_execution=True,  # Prefer local providers
    provider_fallback=True  # Allow fallback to Docker
)

# Provider selection order:
# 1. SeatbeltProvider (macOS)
# 2. BubblewrapProvider (Linux) 
# 3. DockerProvider (all platforms)
# 4. ModalProvider (remote)
```

### Explicit Provider Selection

```python
# Force Docker provider
agent = TinyCodeAgent(
    provider="docker",
    provider_fallback=False  # Don't fallback if Docker fails
)
```

## Best Practices

### Security

1. **Minimize network access**: Only enable when required
2. **Use resource limits**: Prevent resource exhaustion
3. **Mount minimal directories**: Only what's needed
4. **Use read-only mounts**: For data that shouldn't be modified
5. **Keep images updated**: Regular security patches

### Performance

1. **Choose appropriate resources**: Match limits to workload
2. **Pre-pull images**: Avoid pull delays during execution
3. **Use persistent volumes**: For large datasets
4. **Monitor resource usage**: Adjust limits as needed

### Development

1. **Test with minimal config**: Start simple, add complexity
2. **Use logging**: Enable debug logging for troubleshooting
3. **Handle errors gracefully**: Check for Docker availability
4. **Clean up resources**: Call `cleanup()` when done

## Examples

See `examples/docker_provider_examples.py` for comprehensive usage examples including:

- Basic Docker usage
- Custom image configuration
- Environment variables
- Volume mounts
- Git operations
- Security features
- Performance comparison
- Error handling

## API Reference

### DockerProvider Class

```python
class DockerProvider(CodeExecutionProvider):
    def __init__(
        self,
        log_manager: Optional[LoggingManager] = None,
        docker_image: str = "tinyagent-runtime:latest",
        enable_network: bool = False,
        memory_limit: str = "512m",
        cpu_limit: str = "1.0",
        timeout: int = 300,
        auto_pull_image: bool = True,
        # ... additional parameters
    )
    
    async def execute_python(
        self, 
        code_lines: List[str], 
        timeout: int = 120
    ) -> Dict[str, Any]
    
    async def execute_shell(
        self,
        command: List[str],
        timeout: int = 10,
        workdir: Optional[str] = None
    ) -> Dict[str, Any]
    
    @classmethod
    def is_supported(cls) -> bool
    
    async def cleanup(self)
    
    # Environment variable management
    def add_environment_variable(self, name: str, value: str)
    def remove_environment_variable(self, name: str)
    def set_environment_variables(self, env_vars: Dict[str, str])
    def get_environment_variables(self) -> Dict[str, str]
```

## Troubleshooting

### Docker Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Docker not running | `DockerProvider.is_supported()` returns `False` | Start Docker daemon/Desktop |
| Permission denied | `permission denied while trying to connect` | Add user to docker group (Linux) |
| Image not found | `Unable to find image` | Check image name, enable `auto_pull_image` |
| Container startup timeout | Long delays before execution | Check Docker daemon resources |

### Container Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Out of memory | `Killed` in stderr | Increase `memory_limit` |
| CPU throttling | Slow execution | Increase `cpu_limit` |
| Network timeout | Connection errors | Enable `enable_network` |
| File not found | `No such file or directory` | Check volume mounts |

### Code Execution Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| Import errors | `ModuleNotFoundError` | Use image with required packages |
| Permission errors | `Permission denied` | Check file/directory permissions |
| Timeout errors | `timed out after X seconds` | Increase timeout or optimize code |
| State not persisted | Variables not available | Check state serialization errors |

For more help, enable debug logging and check the container logs for detailed error information.