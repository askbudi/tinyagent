++ b/tinyagent/mcp_client.py
import asyncio
import json
import logging
from typing import Optional, List, Coroutine, Any
from typing import Dict, List, Optional, Any, Tuple, Callable

# Set up logging
class MCPClient:

        # We'll hold each context manager separately rather than in one stack:
        self._stdio_ctx = None
        self._session_ctx = None
        self.stdio = None
        self.sock_write = None
        self.session = None
        self.session = None
        # Simplified callback system
        self.callbacks: List[Callable[..., Coroutine[Any,Any,Any]]] = []
        
        for callback in self.callbacks:
            try:
        params = StdioServerParameters(command=command, args=args)

        # 1) enter stdio_client context
        self._stdio_ctx = stdio_client(params)
        try:
            self.stdio, self.sock_write = await self._stdio_ctx.__aenter__()
        except Exception as e:
            self.logger.error(f"Failed to start stdio_client: {e}")
            raise

        # 2) enter ClientSession context
        self._session_ctx = ClientSession(self.stdio, self.sock_write)
        try:
            self.session = await self._session_ctx.__aenter__()
            await self.session.initialize()
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP session: {e}")
            # make sure we unwind the stdio context if session init fails
            await self._stdio_ctx.__aexit__(None, None, None)
            raise
        for callback in self.callbacks:
            try:
        # 1) teardown session
        if self._session_ctx is not None:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception as e:
                self.logger.error(f"Error closing MCP session: {e}")
            finally:
                self.session = None
                self._session_ctx = None

        # 2) teardown stdio
        if self._stdio_ctx is not None:
            try:
                await self._stdio_ctx.__aexit__(None, None, None)
            except Exception as e:
                self.logger.error(f"Error closing stdio client: {e}")
            finally:
                self.stdio = None
                self.sock_write = None
                self._stdio_ctx = None
                        await callback(event_name, self, **kwargs)
                    else:
                        logger.debug(f"Callback is a regular function")
                        callback(event_name, self, **kwargs)
            except Exception as e:
                logger.error(f"Error in callback for {event_name}: {str(e)}")

    async def connect(self, command: str, args: list[str]):
        """
        Launches the MCP server subprocess and initializes the client session.
        :param command: e.g. "python" or "node"
        :param args: list of args to pass, e.g. ["my_server.py"] or ["build/index.js"]
        """
        # Prepare stdio transport parameters
        params = StdioServerParameters(command=command, args=args)
        # Open the stdio client transport
        self.stdio, self.sock_write = await self.exit_stack.enter_async_context(
            stdio_client(params)
        )
        # Create and initialize the MCP client session
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.sock_write)
        )
        await self.session.initialize()

    async def list_tools(self):
        resp = await self.session.list_tools()
        print("Available tools:")
        for tool in resp.tools:
            print(f" • {tool.name}: {tool.description}")

    async def call_tool(self, name: str, arguments: dict):
        """
        Invokes a named tool and returns its raw content list.
        """
        # Notify tool start
        await self._run_callbacks("tool_start", tool_name=name, arguments=arguments)
        
        try:
            resp = await self.session.call_tool(name, arguments)
            
            # Notify tool end
            await self._run_callbacks("tool_end", tool_name=name, arguments=arguments, 
                                    result=resp.content, success=True)
            
            return resp.content
        except Exception as e:
            # Notify tool end with error
            await self._run_callbacks("tool_end", tool_name=name, arguments=arguments, 
                                    error=str(e), success=False)
            raise

    async def close(self):
        """Clean up subprocess and streams."""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
            except (RuntimeError, asyncio.CancelledError) as e:
                # Log the error but don't re-raise it
                self.logger.error(f"Error during client cleanup: {e}")
            finally:
                # Always reset these regardless of success or failure
                self.session = None
                self.exit_stack = AsyncExitStack()

async def run_example():
    """Example usage of MCPClient with proper logging."""
    import sys
    from tinyagent.hooks.logging_manager import LoggingManager
    
    # Create and configure logging manager
    log_manager = LoggingManager(default_level=logging.INFO)
    log_manager.set_levels({
        'tinyagent.mcp_client': logging.DEBUG,  # Debug for this module
        'tinyagent.tiny_agent': logging.INFO,
    })
    
    # Configure a console handler
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    
    # Get module-specific logger
    mcp_logger = log_manager.get_logger('tinyagent.mcp_client')
    
    mcp_logger.debug("Starting MCPClient example")
    
    # Create client with our logger
    client = MCPClient(logger=mcp_logger)
    
    try:
        # Connect to a simple echo server
        await client.connect("python", ["-m", "mcp.examples.echo_server"])
        
        # List available tools
        await client.list_tools()
        
        # Call the echo tool
        result = await client.call_tool("echo", {"message": "Hello, MCP!"})
        mcp_logger.info(f"Echo result: {result}")
        
    finally:
        # Clean up
        await client.close()
        mcp_logger.debug("Example completed")
