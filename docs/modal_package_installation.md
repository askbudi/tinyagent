# Modal Package Installation Guide

This guide shows you how to define packages that need to be installed in the Modal environment when using TinyCodeAgent.

## Quick Reference

### Default Packages
The following packages are automatically installed:
- `cloudpickle` - For object serialization
- `requests` - For HTTP requests  
- `tinyagent-py[all]` - Core TinyAgent functionality
- `gradio` - For UI components
- `arize-phoenix-otel` - For observability

### Method 1: Direct Parameter (Recommended)

```python
from tinyagent.code_agent import TinyCodeAgent

agent = TinyCodeAgent(
    model="gpt-4o-mini",
    pip_packages=[
        "pandas>=2.0.0",
        "numpy>=1.24.0", 
        "matplotlib>=3.7.0",
        "scikit-learn>=1.3.0"
    ]
)
```

### Method 2: Via Provider Config

```python
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider_config={
        "pip_packages": [
            "fastapi>=0.100.0",
            "uvicorn>=0.23.0",
            "pydantic>=2.0.0"
        ]
    }
)
```

### Method 3: Combine Both Sources

```python
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    pip_packages=["pandas>=2.0.0", "numpy>=1.24.0"],
    provider_config={
        "pip_packages": ["matplotlib>=3.7.0", "seaborn>=0.12.0"]
    }
)
# Result: All 4 packages will be installed
```

### Method 4: Add After Initialization (⚠️ Not Recommended)

```python
agent = TinyCodeAgent(model="gpt-4o-mini")
agent.add_pip_packages(["pandas>=2.0.0"])  # Recreates Modal environment!
```

## Package Collections for Common Use Cases

### Data Science Stack
```python
data_science_packages = [
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "scipy>=1.11.0",
    "scikit-learn>=1.3.0",
    "matplotlib>=3.7.0",
    "seaborn>=0.12.0",
    "plotly>=5.15.0",
    "jupyter>=1.0.0"
]
```

### Web Development Stack
```python
web_dev_packages = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "pydantic>=2.0.0",
    "httpx>=0.24.0",
    "python-multipart>=0.0.6",
    "jinja2>=3.1.0"
]
```

### AI/ML Stack
```python
ai_ml_packages = [
    "torch>=2.0.0",
    "transformers>=4.30.0",
    "datasets>=2.12.0",
    "accelerate>=0.20.0",
    "tokenizers>=0.13.0"
]
```

### Database Stack
```python
database_packages = [
    "sqlalchemy>=2.0.0",
    "psycopg2-binary>=2.9.0",
    "pymongo>=4.4.0",
    "redis>=4.6.0"
]
```

## Best Practices

### ✅ DO
- **Set packages during initialization** for best performance
- **Use version constraints** (>=, ==, <) for reproducibility
- **Group related packages** together
- **Test locally first** before deploying to Modal

### ❌ DON'T
- **Add packages after initialization** (recreates environment)
- **Install conflicting versions** 
- **Use overly broad version ranges** 
- **Install unnecessary packages** (increases cold start time)

## Advanced Configuration

### Custom Image Building
```python
from tinyagent.code_agent import TinyCodeAgent

# For specialized requirements
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    pip_packages=[
        "torch>=2.0.0",
        "torchvision>=0.15.0",
        "torchaudio>=2.0.0",
        # GPU-specific packages
        "nvidia-ml-py3>=11.0.0"
    ],
    provider_config={
        "sandbox_name": "my-ml-sandbox",  # Custom sandbox name
        "lazy_init": False,              # Build immediately
    }
)
```

### Handling Private Packages
```python
# For private PyPI or GitHub packages
private_packages = [
    "git+https://github.com/username/private-repo.git@main",
    "--extra-index-url https://private-pypi.company.com/simple/",
    "private-company-package>=1.0.0"
]

agent = TinyCodeAgent(
    model="gpt-4o-mini",
    pip_packages=private_packages
)
```

## Troubleshooting

### Common Issues

1. **Package conflicts**: Use specific versions to avoid conflicts
2. **Long cold starts**: Minimize packages, use package collections
3. **Build failures**: Check package compatibility with Modal's Python version
4. **Missing dependencies**: Include all required system packages

### Debugging Package Installation

```python
# Get list of installed packages
packages = agent.get_pip_packages()
print(f"Installed packages: {packages}")

# Test package availability
await agent.run("""
import pkg_resources
installed_packages = [d.project_name for d in pkg_resources.working_set]
print("Available packages:", sorted(installed_packages))

# Test specific imports
try:
    import pandas as pd
    import numpy as np
    print("✅ Data science packages loaded successfully")
    print(f"Pandas version: {pd.__version__}")
    print(f"NumPy version: {np.__version__}")
except ImportError as e:
    print(f"❌ Import error: {e}")
""")
```

## Performance Considerations

### Package Installation Time
- **Small packages** (~10-20 packages): ~30-60 seconds
- **Medium packages** (20-50 packages): ~1-2 minutes  
- **Large packages** (50+ packages): ~2-5 minutes

### Cold Start Impact
Each additional package increases cold start time. Consider:
- Only install packages you actually need
- Use lighter alternatives when possible
- Pre-build custom images for frequently used stacks

### Memory Usage
Large packages (like PyTorch, TensorFlow) significantly increase memory usage:
- Monitor Modal resource consumption
- Consider upgrading Modal instance size if needed
- Use lighter packages for simple operations

## Examples

See `examples/code_agent_with_packages_example.py` for comprehensive examples of all package installation methods. 