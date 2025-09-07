# tinyagent.code_agent API Reference

## Classes

### TinyCodeAgent

```python
TinyCodeAgent(model: str = 'gpt-4.1-mini', api_key: Optional[str] = None, log_manager: Optional[tinyagent.hooks.logging_manager.LoggingManager] = None, provider: str = 'modal', tools: Optional[List[Any]] = None, code_tools: Optional[List[Any]] = None, authorized_imports: Optional[List[str]] = None, system_prompt_template: Optional[str] = None, system_prompt: Optional[str] = None, provider_config: Optional[Dict[str, Any]] = None, user_variables: Optional[Dict[str, Any]] = None, pip_packages: Optional[List[str]] = None, local_execution: bool = False, check_string_obfuscation: bool = True, default_workdir: Optional[str] = None, summary_config: Optional[Dict[str, Any]] = None, ui: Optional[str] = None, truncation_config: Optional[Dict[str, Any]] = None, **agent_kwargs)
```
A TinyAgent specialized for code execution tasks.

This class provides a high-level interface for creating agents that can execute
Python code using various providers (Modal, Docker, local execution, etc.).

Import: `from tinyagent.code_agent import TinyCodeAgent`

### CodeExecutionProvider

```python
CodeExecutionProvider(log_manager: tinyagent.hooks.logging_manager.LoggingManager, default_python_codes: Optional[List[str]] = None, code_tools: List[Dict[str, Any]] = None, pip_packages: List[str] = None, secrets: Dict[str, Any] = None, lazy_init: bool = True, bypass_shell_safety: bool = False, additional_safe_shell_commands: Optional[List[str]] = None, additional_safe_control_operators: Optional[List[str]] = None, **kwargs)
```
Abstract base class for code execution providers.

This class defines the interface that all code execution providers must implement.
It allows for easy extension to support different execution environments
(Modal, Docker, local execution, cloud functions, etc.) with minimal code changes.

Import: `from tinyagent.code_agent import CodeExecutionProvider`

### ModalProvider

```python
ModalProvider(log_manager, default_python_codes: Optional[List[str]] = None, code_tools: List[Dict[str, Any]] = None, pip_packages: Optional[List[str]] = None, default_packages: Optional[List[str]] = None, apt_packages: Optional[List[str]] = None, python_version: Optional[str] = None, authorized_imports: list[str] | None = None, authorized_functions: list[str] | None = None, modal_secrets: Optional[Dict[str, Optional[str]]] = None, lazy_init: bool = True, sandbox_name: str = 'tinycodeagent-sandbox', local_execution: bool = False, check_string_obfuscation: bool = True, bypass_shell_safety: bool = False, additional_safe_shell_commands: Optional[List[str]] = None, additional_safe_control_operators: Optional[List[str]] = None, **kwargs)
```
Modal-based code execution provider.

This provider uses Modal.com to execute Python code in a remote, sandboxed environment.
It provides scalable, secure code execution with automatic dependency management.
Can also run locally for development/testing purposes using Modal's native .local() method.

Import: `from tinyagent.code_agent import ModalProvider`

## Functions

### get_weather

```python
get_weather(city: str) -> str
```
Get the weather for a given city.
Args:
    city: The city to get the weather for

Returns:
    The weather for the given city

Import: `from tinyagent.code_agent import get_weather`

### get_traffic

```python
get_traffic(city: str) -> str
```
Get the traffic for a given city.
Args:
    city: The city to get the traffic for

Returns:
    The traffic for the given city

Import: `from tinyagent.code_agent import get_traffic`
