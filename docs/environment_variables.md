# Environment Variables Support in TinyCodeAgent

The TinyCodeAgent's SeatbeltProvider now supports custom environment variables that can be passed to the sandboxed execution environment. This feature enables developers to configure applications, pass secrets securely, and customize the runtime environment without modifying code.

## Overview

Environment variables in the SeatbeltProvider provide:
- **Secure Configuration**: Pass configuration values without hardcoding them
- **Runtime Customization**: Modify behavior based on environment settings
- **Secrets Management**: Safely pass API keys and credentials to the sandbox
- **Build Configuration**: Set build-time and runtime parameters
- **Feature Flags**: Enable/disable features through environment configuration

## Setup and Configuration

### During Agent Initialization

You can set environment variables when creating the TinyCodeAgent:

```python
from tinyagent.code_agent import TinyCodeAgent

agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    provider="seatbelt",
    provider_config={
        "environment_variables": {
            "API_KEY": "your_api_key_here",
            "DEBUG_MODE": "true",
            "DATABASE_URL": "postgresql://localhost:5432/mydb",
            "CONFIG_PATH": "/path/to/config",
            "FEATURE_NEW_UI": "enabled"
        },
        # Other seatbelt configuration...
        "additional_read_dirs": ["/path/to/read"],
        "additional_write_dirs": ["/path/to/write"]
    },
    local_execution=True
)
```

### Dynamic Environment Variable Management

After agent creation, you can manage environment variables dynamically:

```python
# Add a single environment variable
agent.add_environment_variable("NEW_FEATURE", "experimental")

# Set multiple environment variables (replaces all existing ones)
agent.set_environment_variables({
    "APP_NAME": "MyApp",
    "VERSION": "2.0.0",
    "ENVIRONMENT": "production"
})

# Remove a specific environment variable
agent.remove_environment_variable("OLD_FEATURE")

# Get current environment variables
current_vars = agent.get_environment_variables()
print(f"Current env vars: {list(current_vars.keys())}")
```

## Environment Variable Inheritance

The SeatbeltProvider creates a complete environment that includes:

1. **Essential System Variables**: PATH, HOME, USER, TERM, LANG, LC_ALL
2. **Python-Specific Variables**: PYTHONPATH, PYTHONHOME, VIRTUAL_ENV, CONDA_*
3. **User-Defined Variables**: Your custom environment variables (highest priority)

User-defined variables can override system variables if needed.

## Security Considerations

### Sandboxed Environment
- Environment variables are isolated within the sandbox
- System environment variables are filtered and controlled
- Sensitive system variables are not automatically passed through

### Variable Validation
```python
# Environment variables are strings only
agent.add_environment_variable("PORT", "8080")  # ✅ Correct
agent.add_environment_variable("DEBUG", "true")  # ✅ Correct as string

# Complex objects need to be serialized
import json
config = {"host": "localhost", "port": 5432}
agent.add_environment_variable("DB_CONFIG", json.dumps(config))
```

## Usage Examples

### Configuration Management

```python
# Set configuration through environment variables
agent.set_environment_variables({
    "DATABASE_HOST": "localhost",
    "DATABASE_PORT": "5432",
    "DATABASE_NAME": "myapp",
    "CACHE_TTL": "3600",
    "LOG_LEVEL": "INFO"
})

# Use in Python code
response = await agent.run("""
import os

# Access configuration
db_host = os.environ.get('DATABASE_HOST', 'localhost')
db_port = int(os.environ.get('DATABASE_PORT', '5432'))
log_level = os.environ.get('LOG_LEVEL', 'INFO')

print(f"Database: {db_host}:{db_port}")
print(f"Log Level: {log_level}")

# Create configuration object
config = {
    'database': {
        'host': db_host,
        'port': db_port,
        'name': os.environ.get('DATABASE_NAME')
    },
    'cache_ttl': int(os.environ.get('CACHE_TTL', '0')),
    'log_level': log_level
}

print("Configuration:", config)
""")
```

### Feature Flags

```python
# Set feature flags
agent.set_environment_variables({
    "FEATURE_NEW_UI": "enabled",
    "FEATURE_BETA_API": "disabled",
    "FEATURE_ANALYTICS": "enabled"
})

# Use feature flags in code
response = await agent.run("""
import os

def is_feature_enabled(feature_name):
    return os.environ.get(feature_name, "disabled").lower() == "enabled"

# Check features
if is_feature_enabled("FEATURE_NEW_UI"):
    print("New UI is enabled")

if is_feature_enabled("FEATURE_BETA_API"):
    print("Beta API is enabled")
else:
    print("Using stable API")

# Dynamic behavior based on features
features = {
    name: is_feature_enabled(name) 
    for name in os.environ 
    if name.startswith("FEATURE_")
}

print("Active features:", [name for name, enabled in features.items() if enabled])
""")
```

### Secrets and API Keys

```python
# Set API credentials (be careful with secrets in logs)
agent.add_environment_variable("OPENAI_API_KEY", "sk-...")
agent.add_environment_variable("DATABASE_PASSWORD", "secret123")

# Use in secure manner
response = await agent.run("""
import os
import requests

# Access API key securely
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment")

# Use the API key (don't print it)
headers = {'Authorization': f'Bearer {api_key}'}
print("API key loaded successfully (not displayed for security)")

# Database connection with password
db_password = os.environ.get('DATABASE_PASSWORD')
connection_string = f"postgresql://user:{db_password}@localhost:5432/db"
# Don't print connection string with password
print("Database connection configured")
""")
```

### Build and Deployment Configuration

```python
# Set build-time configuration
agent.set_environment_variables({
    "BUILD_ENV": "production",
    "VERSION": "1.2.3",
    "COMMIT_SHA": "abc123def",
    "BUILD_DATE": "2024-01-15",
    "DEPLOYMENT_REGION": "us-west-2"
})

# Use in deployment scripts
response = await agent.run("""
import os
from datetime import datetime

# Build information
build_info = {
    'environment': os.environ.get('BUILD_ENV', 'development'),
    'version': os.environ.get('VERSION', 'unknown'),
    'commit': os.environ.get('COMMIT_SHA', 'unknown'),
    'build_date': os.environ.get('BUILD_DATE', 'unknown'),
    'region': os.environ.get('DEPLOYMENT_REGION', 'unknown')
}

print("Build Information:")
for key, value in build_info.items():
    print(f"  {key}: {value}")

# Generate deployment manifest
manifest = f'''
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  version: "{build_info['version']}"
  environment: "{build_info['environment']}"
  commit: "{build_info['commit']}"
  region: "{build_info['region']}"
'''

print("\\nDeployment Manifest:")
print(manifest)
""")
```

## Shell Command Integration

Environment variables are also available in shell commands:

```python
agent.add_environment_variable("OUTPUT_DIR", "/tmp/myapp")
agent.add_environment_variable("LOG_FILE", "app.log")

response = await agent.run("""
Use environment variables in shell commands:
1. Create a directory using $OUTPUT_DIR
2. Create a log file using $LOG_FILE
3. List environment variables that start with our custom prefixes
""")
```

## Best Practices

### 1. Use Descriptive Names
```python
# Good
agent.add_environment_variable("DATABASE_CONNECTION_TIMEOUT", "30")
agent.add_environment_variable("FEATURE_ENHANCED_LOGGING", "enabled")

# Avoid
agent.add_environment_variable("TIMEOUT", "30")
agent.add_environment_variable("FLAG1", "1")
```

### 2. Use String Values
```python
# Convert non-string values to strings
agent.add_environment_variable("PORT", str(8080))
agent.add_environment_variable("ENABLED", str(True).lower())
agent.add_environment_variable("RATIO", str(0.5))
```

### 3. Provide Defaults in Code
```python
response = await agent.run("""
import os

# Always provide defaults
timeout = int(os.environ.get('TIMEOUT', '30'))
debug = os.environ.get('DEBUG', 'false').lower() == 'true'
host = os.environ.get('HOST', 'localhost')
""")
```

### 4. Group Related Variables
```python
# Database configuration
agent.set_environment_variables({
    "DB_HOST": "localhost",
    "DB_PORT": "5432", 
    "DB_NAME": "myapp",
    "DB_USER": "appuser",
    "DB_PASSWORD": "secret"
})

# Application configuration  
agent.set_environment_variables({
    "APP_NAME": "MyApplication",
    "APP_VERSION": "1.0.0",
    "APP_ENV": "production",
    "APP_DEBUG": "false"
})
```

### 5. Security Best Practices
```python
# Don't log sensitive values
api_key = "sk-secret123"
agent.add_environment_variable("API_KEY", api_key)
print("API key set")  # Don't print the actual key

# Use temporary variables for secrets when possible
sensitive_vars = {
    "API_KEY": get_api_key_from_secure_store(),
    "DB_PASSWORD": get_db_password()
}
agent.set_environment_variables(sensitive_vars)

# Clear sensitive variables when done
agent.remove_environment_variable("API_KEY")
agent.remove_environment_variable("DB_PASSWORD")
```

## Limitations and Considerations

### Platform Support
- Currently only supported on macOS with SeatbeltProvider
- Requires `sandbox-exec` command to be available
- Not available with ModalProvider (use Modal's built-in environment support)

### Variable Scope
- Environment variables are process-scoped within the sandbox
- Variables persist across Python executions within the same agent session
- Variables are reset when the agent is recreated

### Performance
- Environment variables are passed to every subprocess execution
- Large numbers of variables may impact performance slightly
- Consider grouping related configuration into JSON strings for complex data

### Memory
- Environment variables are stored in memory within the agent
- Values are copied when accessed through the API
- Consider memory usage for large configuration values

## Integration with Other Features

### With Additional Directories
```python
config_dir = "/path/to/config"
output_dir = "/path/to/output"

agent = TinyCodeAgent(
    provider="seatbelt",
    provider_config={
        "additional_read_dirs": [config_dir],
        "additional_write_dirs": [output_dir],
        "environment_variables": {
            "CONFIG_DIR": config_dir,
            "OUTPUT_DIR": output_dir,
            "APP_NAME": "MyApp"
        }
    },
    local_execution=True
)
```

### With Git Checkpoints
```python
# Environment variables are available in git commands
agent.enable_auto_git_checkpoint(True)
agent.add_environment_variable("GIT_AUTHOR_NAME", "TinyAgent")
agent.add_environment_variable("GIT_AUTHOR_EMAIL", "agent@example.com")
```

## Troubleshooting

### Common Issues

1. **Variable Not Found**
   ```python
   # Always check if variable exists
   value = os.environ.get('MY_VAR')
   if value is None:
       print("MY_VAR not found in environment")
   ```

2. **Type Conversion Errors**
   ```python
   # Convert strings to appropriate types
   try:
       port = int(os.environ.get('PORT', '8080'))
   except ValueError:
       print("Invalid port number in environment")
       port = 8080
   ```

3. **Path Issues**
   ```python
   # Ensure paths are absolute and exist
   import os
   config_path = os.environ.get('CONFIG_PATH')
   if config_path and os.path.exists(config_path):
       print(f"Config found at: {config_path}")
   ```

### Debugging Environment Variables

```python
# List all environment variables
response = await agent.run("""
import os

print("All environment variables:")
for key, value in sorted(os.environ.items()):
    # Don't print sensitive values
    if any(sensitive in key.upper() for sensitive in ['PASSWORD', 'KEY', 'SECRET', 'TOKEN']):
        print(f"{key}: [REDACTED]")
    else:
        print(f"{key}: {value}")
""")

# Check specific variables
current_vars = agent.get_environment_variables()
print("TinyCodeAgent managed variables:", current_vars)
```

This environment variable support makes the SeatbeltProvider much more flexible for real-world applications while maintaining the security benefits of sandboxed execution. 