# tinyagent.mcp_client API Reference

## Classes

### Any

```python
Any(/, *args, **kwargs)
```
Special type indicating an unconstrained type.

- Any is compatible with every type.
- Any assumed to have all methods.
- All values assumed to be instances of Any.

Note that all the above statements are true from the point of view of
static type checkers. At runtime, Any should not be used with instance
checks.

Import: `from tinyagent.mcp_client import Any`

### AsyncExitStack

```python
AsyncExitStack()
```
Async context manager for dynamic management of a stack of exit
callbacks.

For example:
    async with AsyncExitStack() as stack:
        connections = [await stack.enter_async_context(get_connection())
            for i in range(5)]
        # All opened connections will automatically be released at the
        # end of the async with statement, even if attempts to open a
        # connection later in the list raise an exception.

Import: `from tinyagent.mcp_client import AsyncExitStack`

### ClientSession

```python
ClientSession(read_stream: anyio.streams.memory.MemoryObjectReceiveStream[mcp.types.JSONRPCMessage | Exception], write_stream: anyio.streams.memory.MemoryObjectSendStream[mcp.types.JSONRPCMessage], read_timeout_seconds: datetime.timedelta | None = None, sampling_callback: mcp.client.session.SamplingFnT | None = None, list_roots_callback: mcp.client.session.ListRootsFnT | None = None, logging_callback: mcp.client.session.LoggingFnT | None = None, message_handler: mcp.client.session.MessageHandlerFnT | None = None, client_info: mcp.types.Implementation | None = None) -> None
```

Import: `from tinyagent.mcp_client import ClientSession`

### MCPClient

```python
MCPClient(logger: Optional[logging.Logger] = None)
```

Import: `from tinyagent.mcp_client import MCPClient`

### StdioServerParameters

```python
StdioServerParameters(/, **data: 'Any') -> 'None'
```

Import: `from tinyagent.mcp_client import StdioServerParameters`

## Functions

### run_example

```python
run_example()
```
Example usage of MCPClient with proper logging.

Import: `from tinyagent.mcp_client import run_example`

### stdio_client

```python
stdio_client(server: mcp.client.stdio.StdioServerParameters, errlog: <class 'TextIO'> = <_io.TextIOWrapper name='<stderr>' mode='w' encoding='utf-8'>)
```
Client transport for stdio: this will connect to a server by spawning a
process and communicating with it over stdin/stdout.

Import: `from tinyagent.mcp_client import stdio_client`
