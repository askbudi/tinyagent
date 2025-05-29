import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Callable
from contextlib import AsyncExitStack
from enum import Enum

# MCP core imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Set up logging
logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Enum to track the connection state of the MCP client."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class MCPClient:
    """
    MCP Client with improved support for multiple concurrent connections.
    
    This implementation fixes the issue where closing one MCP client would
    interfere with other active clients by using proper task isolation
    and connection state management.
    
    Fixes the error: "Attempted to exit a cancel scope that isn't the current 
    task's current cancel scope" when multiple MCP clients are used.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.session = None
        self.exit_stack = None
        self.stdio = None
        self.sock_write = None
        self.logger = logger or logging.getLogger(__name__)
        self._state = ConnectionState.DISCONNECTED
        self._connection_lock = asyncio.Lock()
        
        # Simplified callback system
        self.callbacks: List[callable] = []
        
        self.logger.debug("MCPClient initialized")

    @property
    def state(self) -> ConnectionState:
        """Get the current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if the client is currently connected."""
        return self._state == ConnectionState.CONNECTED

    def add_callback(self, callback: callable) -> None:
        """
        Add a callback function to the client.
        
        Args:
            callback: A function that accepts (event_name, client, **kwargs)
        """
        self.callbacks.append(callback)
    
    async def _run_callbacks(self, event_name: str, **kwargs) -> None:
        """
        Run all registered callbacks for an event.
        
        Args:
            event_name: The name of the event
            **kwargs: Additional data for the event
        """
        for callback in self.callbacks:
            try:
                self.logger.debug(f"Running callback: {callback}")
                if asyncio.iscoroutinefunction(callback):
                    self.logger.debug(f"Callback is a coroutine function")
                    await callback(event_name, self, **kwargs)
                else:
                    # Check if the callback is a class with an async __call__ method
                    if hasattr(callback, '__call__') and asyncio.iscoroutinefunction(callback.__call__):
                        self.logger.debug(f"Callback is a class with an async __call__ method")  
                        await callback(event_name, self, **kwargs)
                    else:
                        self.logger.debug(f"Callback is a regular function")
                        callback(event_name, self, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in callback for {event_name}: {str(e)}")

    async def connect(self, command: str, args: list[str]) -> None:
        """
        Launches the MCP server subprocess and initializes the client session.
        
        Args:
            command: e.g. "python" or "node"
            args: list of args to pass, e.g. ["my_server.py"] or ["build/index.js"]
            
        Raises:
            RuntimeError: If already connected or connection fails
        """
        async with self._connection_lock:
            if self._state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
                raise RuntimeError(f"Client is already {self._state.value}")
            
            self._state = ConnectionState.CONNECTING
            self.logger.debug(f"Connecting to MCP server: {command} {args}")
            
            try:
                # Create a new exit stack for this connection
                self.exit_stack = AsyncExitStack()
                
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
                
                self._state = ConnectionState.CONNECTED
                self.logger.info("Successfully connected to MCP server")
                
                # Notify connection established
                await self._run_callbacks("connection_established", command=command, args=args)
                
            except Exception as e:
                self._state = ConnectionState.ERROR
                self.logger.error(f"Failed to connect to MCP server: {e}")
                
                # Clean up on connection failure
                await self._cleanup_connection()
                raise RuntimeError(f"Failed to connect to MCP server: {e}") from e

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools from the MCP server.
        
        Returns:
            List of tool information dictionaries
            
        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected:
            raise RuntimeError("Client is not connected. Call connect() first.")
        
        try:
            resp = await self.session.list_tools()
            tools = []
            print("Available tools:")
            for tool in resp.tools:
                tool_info = {
                    "name": tool.name,
                    "description": tool.description,
                    "schema": getattr(tool, 'inputSchema', None)
                }
                tools.append(tool_info)
                print(f"  • {tool.name}: {tool.description}")
            return tools
        except Exception as e:
            self.logger.error(f"Error listing tools: {e}")
            raise

    async def call_tool(self, name: str, arguments: dict) -> Any:
        """
        Invokes a named tool and returns its raw content list.
        
        Args:
            name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool response content
            
        Raises:
            RuntimeError: If not connected
        """
        if not self.is_connected:
            raise RuntimeError("Client is not connected. Call connect() first.")
        
        # Notify tool start
        await self._run_callbacks("tool_start", tool_name=name, arguments=arguments)
        
        try:
            self.logger.debug(f"Calling tool '{name}' with arguments: {arguments}")
            resp = await self.session.call_tool(name, arguments)
            
            # Notify tool end
            await self._run_callbacks("tool_end", tool_name=name, arguments=arguments, 
                                    result=resp.content, success=True)
            
            self.logger.debug(f"Tool '{name}' completed successfully")
            return resp.content
            
        except Exception as e:
            self.logger.error(f"Error calling tool '{name}': {e}")
            # Notify tool end with error
            await self._run_callbacks("tool_end", tool_name=name, arguments=arguments, 
                                    error=str(e), success=False)
            raise

    async def _cleanup_connection(self) -> None:
        """Internal method to clean up connection resources."""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
            except Exception as e:
                self.logger.warning(f"Error during exit stack cleanup: {e}")
            finally:
                self.exit_stack = None
        
        # Reset connection-related attributes
        self.session = None
        self.stdio = None
        self.sock_write = None

    async def close(self) -> None:
        """
        Clean up subprocess and streams.
        
        This method is safe to call multiple times and from multiple clients.
        It properly isolates cleanup to prevent interference with other MCP clients.
        """
        async with self._connection_lock:
            if self._state in [ConnectionState.DISCONNECTED, ConnectionState.DISCONNECTING]:
                self.logger.debug("Client is already disconnected or disconnecting")
                return
            
            self._state = ConnectionState.DISCONNECTING
            self.logger.debug("Closing MCP client connection")
            
            try:
                # Notify connection closing
                await self._run_callbacks("connection_closing")
                
                # Clean up the connection
                await self._cleanup_connection()
                
                self._state = ConnectionState.DISCONNECTED
                self.logger.info("MCP client connection closed successfully")
                
                # Notify connection closed
                await self._run_callbacks("connection_closed")
                
            except Exception as e:
                self._state = ConnectionState.ERROR
                self.logger.error(f"Error during client cleanup: {e}")
                # Don't re-raise the exception to prevent interference with other clients
            finally:
                # Ensure we always end up in a clean state
                if self._state == ConnectionState.DISCONNECTING:
                    self._state = ConnectionState.DISCONNECTED

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


async def run_example():
    """Example usage of MCPClient with proper logging and multiple clients."""
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
    
    mcp_logger.debug("Starting MCPClient example with multiple clients")
    
    # Test multiple clients
    clients = []
    
    try:
        # Create multiple clients
        for i in range(3):
            client = MCPClient(logger=mcp_logger)
            clients.append(client)
            
            # Connect each client
            await client.connect("python", ["-m", "mcp.examples.echo_server"])
            mcp_logger.info(f"Client {i+1} connected")
            
            # List tools for each client
            tools = await client.list_tools()
            mcp_logger.info(f"Client {i+1} has {len(tools)} tools")
        
        # Test calling tools from different clients
        for i, client in enumerate(clients):
            result = await client.call_tool("echo", {"message": f"Hello from client {i+1}!"})
            mcp_logger.info(f"Client {i+1} result: {result}")
        
        # Close clients one by one to test isolation
        for i, client in enumerate(clients):
            await client.close()
            mcp_logger.info(f"Client {i+1} closed")
            
            # Verify other clients still work
            for j, other_client in enumerate(clients[i+1:], i+1):
                if other_client.is_connected:
                    result = await other_client.call_tool("echo", {"message": f"Still working from client {j+1}!"})
                    mcp_logger.info(f"Client {j+1} still working: {result}")
        
    except Exception as e:
        mcp_logger.error(f"Error in example: {e}")
    finally:
        # Ensure all clients are closed
        for i, client in enumerate(clients):
            if client.is_connected:
                await client.close()
                mcp_logger.info(f"Final cleanup: Client {i+1} closed")
        
        mcp_logger.debug("Example completed")


# Example of using the client as an async context manager
async def context_manager_example():
    """Example showing async context manager usage."""
    async with MCPClient() as client:
        await client.connect("python", ["-m", "mcp.examples.echo_server"])
        tools = await client.list_tools()
        result = await client.call_tool("echo", {"message": "Context manager test"})
        print(f"Result: {result}")
    # Client is automatically closed when exiting the context
