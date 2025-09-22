"""
Agno-style MCP integration for TinyAgent.

This module implements MCP connection management inspired by Agno's approach,
providing better async context management, multi-transport support, and
improved error handling.
"""

import asyncio
import logging
import time
from contextlib import AsyncExitStack
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable
from datetime import timedelta
from dataclasses import dataclass, field

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
logger = logging.getLogger(__name__)

try:
    from mcp.client.sse import sse_client, SSEClientParams
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False
    # Create dummy for type hints
    class SSEClientParams:
        pass
    def sse_client(*args, **kwargs):
        raise NotImplementedError("SSE client not available")

async def default_progress_callback(
    progress: float,
    total: Optional[float] = None,
    message: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> None:
    """
    Default progress callback that logs to both logger and stdout.

    Args:
        progress: Current progress value
        total: Total expected value (optional)
        message: Progress message (optional)
        logger: Logger instance (optional)
    """
    logger = logger or logging.getLogger(__name__)
    if total and total > 0:
        percentage = (progress / total) * 100
        progress_msg = f"[{percentage:5.1f}%] {message or 'Processing...'}"
    else:
        progress_msg = f"[Step {progress}] {message or 'Processing...'}"

    # Log to logger if provided
    
    logger.debug(progress_msg)

    # Print to stdout
    #print(progress_msg)

@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    transport: str = "stdio"  # "stdio", "sse", or "streamable-http"
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    timeout: float = 300.0
    include_tools: Optional[List[str]] = None
    exclude_tools: Optional[List[str]] = None
    progress_callback: Optional[Callable[[float, Optional[float], Optional[str]], Awaitable[None]]] = None
    enable_default_progress_callback: bool = True
    # Health check configuration
    health_check_interval: float = 30.0  # Ping every 30 seconds
    health_check_timeout: float = 5.0    # Ping timeout of 5 seconds
    max_reconnect_attempts: int = 3      # Max reconnection attempts
    reconnect_backoff_base: float = 1.0  # Base backoff time in seconds
    reconnect_backoff_max: float = 60.0  # Max backoff time

class TinyMCPTools:
    """
    Agno-style MCP tools manager with async context management.

    Supports multiple transport types, proper resource cleanup, and health-check based reconnection.
    """

    def __init__(self,
                 config: MCPServerConfig,
                 logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Connection state
        self.session: Optional[ClientSession] = None
        self._context = None
        self._session_context = None
        self._initialized = False
        self._connection_healthy = False
        self._last_health_check = 0.0
        self._reconnect_attempts = 0
        self._last_reconnect_time = 0.0
        self._had_timeout_error = False  # Track if we had a timeout error
        self._force_reconnect_on_next_call = False  # Force reconnection flag

        # Tool management
        self.tools: List[Any] = []
        self.tool_schemas: Dict[str, Any] = {}

        # Progress callback setup
        self.progress_callback = config.progress_callback
        if self.progress_callback is None and config.enable_default_progress_callback:
            # Use default progress callback with bound logger
            self.progress_callback = lambda p, t, m: default_progress_callback(p, t, m, self.logger)

        # Health monitoring
        self._health_check_lock = asyncio.Lock()

    async def __aenter__(self) -> "TinyMCPTools":
        """Async context manager entry - establish MCP connection."""
        if self.session is not None:
            if not self._initialized:
                await self.initialize()
            return self

        try:
            # Create transport-specific client context
            if self.config.transport == "sse":
                if not SSE_AVAILABLE:
                    raise RuntimeError("SSE client not available - install required dependencies")
                if not self.config.url:
                    raise ValueError("SSE transport requires URL")

                sse_params = SSEClientParams(
                    url=self.config.url,
                    headers=self.config.headers or {}
                )
                self._context = sse_client(**sse_params.__dict__)

            elif self.config.transport == "streamable-http":
                # TODO: Implement streamable-http support when needed
                raise NotImplementedError("streamable-http transport not yet implemented")

            else:  # Default to stdio
                if not self.config.command:
                    raise ValueError("stdio transport requires command")

                server_params = StdioServerParameters(
                    command=self.config.command,
                    args=self.config.args or [],
                    env=self.config.env
                )
                self._context = stdio_client(server_params)

            # Enter the client context
            session_params = await self._context.__aenter__()
            read, write = session_params[0:2]

            # Create and enter session context with timeout
            timeout_seconds = timedelta(seconds=self.config.timeout)
            self._session_context = ClientSession(
                read, write,
                read_timeout_seconds=timeout_seconds
            )
            self.session = await self._session_context.__aenter__()

            # Initialize tools
            await self.initialize()

            self.logger.debug(f"Connected to MCP server '{self.config.name}' via {self.config.transport}")
            return self

        except Exception as e:
            # Cleanup on error
            await self._cleanup_on_error()
            raise RuntimeError(f"Failed to connect to MCP server '{self.config.name}': {e}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup connections."""
        # Cleanup in reverse order: session first, then client context
        if self._session_context is not None:
            try:
                await self._session_context.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                self.logger.warning(f"Error closing session context: {e}")
            finally:
                self.session = None
                self._session_context = None

        if self._context is not None:
            try:
                await self._context.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                self.logger.warning(f"Error closing client context: {e}")
            finally:
                self._context = None

        self._initialized = False
        self._connection_healthy = False
        self._last_health_check = 0.0
        self.logger.debug(f"Disconnected from MCP server '{self.config.name}'")

    async def _cleanup_on_error(self):
        """Cleanup connections when an error occurs during initialization."""
        if self._session_context:
            try:
                await self._session_context.__aexit__(None, None, None)
            except:
                pass
            self._session_context = None
            self.session = None
            self._connection_healthy = False

        if self._context:
            try:
                await self._context.__aexit__(None, None, None)
            except:
                pass
            self._context = None

    async def initialize(self):
        """Initialize tools from the MCP server."""
        if not self.session:
            raise RuntimeError("Session not established")

        try:
            # Initialize the session
            await self.session.initialize()

            # List available tools
            resp = await self.session.list_tools()
            available_tools = resp.tools

            # Apply filtering
            filtered_tools = self._filter_tools(available_tools)

            # Store tools and schemas
            self.tools = filtered_tools
            for tool in filtered_tools:
                self.tool_schemas[tool.name] = {
                    'name': tool.name,
                    'description': tool.description,
                    'inputSchema': tool.inputSchema
                }

            self._initialized = True
            self.logger.debug(f"Initialized {len(filtered_tools)} tools from server '{self.config.name}'")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize MCP server '{self.config.name}': {e}")

    async def _check_connection_health(self) -> bool:
        """
        Check if the MCP connection is healthy using ping.
        Returns True if healthy, False otherwise.

        Special handling: If we had a timeout error recently, force reconnection
        even if ping succeeds (zombie session state).
        """
        if not self.session:
            return False

        # If we had a timeout error, don't trust the ping - force reconnection
        if self._had_timeout_error:
            self.logger.warning(f"Previous timeout detected for server '{self.config.name}' - forcing reconnection despite ping")
            self._connection_healthy = False
            self._had_timeout_error = False  # Reset the flag
            return False

        try:
            # Send ping with timeout
            await asyncio.wait_for(
                self.session.send_ping(),
                timeout=self.config.health_check_timeout
            )
            self._connection_healthy = True
            self._last_health_check = time.time()
            self.logger.debug(f"Health check passed for server '{self.config.name}'")
            return True
        except Exception as e:
            self._connection_healthy = False
            self.logger.warning(f"Health check failed for server '{self.config.name}': {e}")
            return False

    async def _should_perform_health_check(self) -> bool:
        """Check if enough time has passed since last health check."""
        current_time = time.time()
        return (current_time - self._last_health_check) >= self.config.health_check_interval

    async def _calculate_backoff_delay(self) -> float:
        """Calculate exponential backoff delay for reconnection."""
        if self._reconnect_attempts == 0:
            return 0

        delay = min(
            self.config.reconnect_backoff_base * (2 ** (self._reconnect_attempts - 1)),
            self.config.reconnect_backoff_max
        )
        return delay

    async def _attempt_reconnection(self) -> bool:
        """
        Attempt to reconnect to the MCP server with exponential backoff.
        Returns True if successful, False otherwise.
        """
        if self._reconnect_attempts >= self.config.max_reconnect_attempts:
            self.logger.error(f"Max reconnection attempts ({self.config.max_reconnect_attempts}) reached for server '{self.config.name}'")
            return False

        # Calculate backoff delay
        delay = await self._calculate_backoff_delay()
        current_time = time.time()

        # Respect minimum time between reconnection attempts
        if current_time - self._last_reconnect_time < delay:
            return False

        self._reconnect_attempts += 1
        self._last_reconnect_time = current_time

        self.logger.info(f"Attempting reconnection #{self._reconnect_attempts} to server '{self.config.name}' after {delay:.1f}s delay")

        if delay > 0:
            await asyncio.sleep(delay)

        try:
            # Clean up existing connections
            await self._cleanup_on_error()

            # Re-establish connection using the same logic as __aenter__
            if self.config.transport == "sse":
                if not SSE_AVAILABLE:
                    raise RuntimeError("SSE client not available - install required dependencies")
                if not self.config.url:
                    raise ValueError("SSE transport requires URL")

                sse_params = SSEClientParams(
                    url=self.config.url,
                    headers=self.config.headers or {}
                )
                self._context = sse_client(**sse_params.__dict__)

            elif self.config.transport == "streamable-http":
                raise NotImplementedError("streamable-http transport not yet implemented")

            else:  # Default to stdio
                if not self.config.command:
                    raise ValueError("stdio transport requires command")

                server_params = StdioServerParameters(
                    command=self.config.command,
                    args=self.config.args or [],
                    env=self.config.env
                )
                self._context = stdio_client(server_params)

            # Enter the client context
            session_params = await self._context.__aenter__()
            read, write = session_params[0:2]

            # Create and enter session context with timeout
            timeout_seconds = timedelta(seconds=self.config.timeout)
            self._session_context = ClientSession(
                read, write,
                read_timeout_seconds=timeout_seconds
            )
            self.session = await self._session_context.__aenter__()

            # Initialize tools
            await self.initialize()

            # Reset reconnection counter and timeout flags on success
            self._reconnect_attempts = 0
            self._connection_healthy = True
            self._last_health_check = time.time()
            self._had_timeout_error = False
            self._force_reconnect_on_next_call = False

            self.logger.info(f"Successfully reconnected to MCP server '{self.config.name}'")
            return True

        except Exception as e:
            self.logger.error(f"Reconnection attempt failed for server '{self.config.name}': {e}")
            await self._cleanup_on_error()
            return False

    def _filter_tools(self, available_tools: List[Any]) -> List[Any]:
        """Filter tools based on include/exclude lists."""
        filtered = []

        for tool in available_tools:
            # Apply exclude filter
            if self.config.exclude_tools and tool.name in self.config.exclude_tools:
                self.logger.debug(f"Excluding tool '{tool.name}' from server '{self.config.name}'")
                continue

            # Apply include filter
            if self.config.include_tools is None or tool.name in self.config.include_tools:
                filtered.append(tool)
            else:
                self.logger.debug(f"Tool '{tool.name}' not in include list for server '{self.config.name}'")

        return filtered

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], read_timeout_seconds: timedelta | None = None, progress_callback: Optional[Callable[[float, Optional[float], Optional[str]], Awaitable[None]]] = None) -> Any:
        """
        Call a tool with health-check based error handling and automatic reconnection.

        This method implements a resilient approach:
        1. Performs health check if needed
        2. Attempts reconnection if connection is unhealthy or had timeout
        3. Executes the tool call with proper error handling
        4. Recovers from connection failures automatically
        5. Handles zombie session state after timeouts
        """
        if tool_name not in self.tool_schemas:
            raise ValueError(f"Tool '{tool_name}' not available on server '{self.config.name}'")

        # Use lock to prevent concurrent health checks and reconnections
        async with self._health_check_lock:
            # Force reconnection if flag is set (from previous timeout)
            if self._force_reconnect_on_next_call:
                self.logger.warning(f"Force reconnection flag set for server '{self.config.name}' due to previous timeout")
                self._connection_healthy = False
                self._force_reconnect_on_next_call = False

            # Health check: Ping server if interval has passed
            elif await self._should_perform_health_check():
                await self._check_connection_health()

            # If connection is unhealthy or we had a timeout, attempt reconnection
            if not self._connection_healthy or self._had_timeout_error:
                self.logger.warning(f"Connection unhealthy or timeout detected for server '{self.config.name}', attempting reconnection")
                reconnected = await self._attempt_reconnection()
                if not reconnected:
                    raise RuntimeError(f"Failed to reconnect to MCP server '{self.config.name}' after {self._reconnect_attempts} attempts")

        # Ensure session is available
        if not self.session:
            raise RuntimeError("Session not established")

        # Attempt tool call with error recovery
        max_retries = 2  # Try original call + 1 retry after reconnection
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Calling MCP tool '{tool_name}' with args: {arguments} (attempt {attempt + 1})")

                # Use provided progress_callback, or fall back to instance callback
                final_progress_callback = progress_callback or self.progress_callback

                result = await self.session.call_tool(
                    tool_name,
                    arguments,
                    read_timeout_seconds=read_timeout_seconds,
                    progress_callback=final_progress_callback
                )

                # Process response content (similar to Agno's approach)
                response_parts = []
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        response_parts.append(content_item.text)
                    elif hasattr(content_item, 'type'):
                        # Handle other content types as needed
                        response_parts.append(f"[{content_item.type}: {str(content_item)}]")
                    else:
                        response_parts.append(str(content_item))

                response = "\n".join(response_parts).strip()
                self.logger.debug(f"MCP tool '{tool_name}' completed successfully")

                # Mark connection as healthy on successful call
                self._connection_healthy = True
                return response

            except Exception as e:
                error_str = str(e).lower()

                # Check if this is specifically a timeout error
                is_timeout_error = 'timeout' in error_str or 'timed out' in error_str

                # Check if this is a connection error (NOT including timeout for retry purposes)
                is_connection_error = any(err in error_str for err in [
                    'closed', 'connection', 'eof', 'broken pipe', 'reset'
                ])

                if is_timeout_error:
                    # TIMEOUT ERROR: Don't retry the same call!
                    # Mark that we had a timeout - this will force reconnection on NEXT tool call
                    self._had_timeout_error = True
                    self._force_reconnect_on_next_call = True
                    self._connection_healthy = False

                    self.logger.warning(f"Timeout error for tool '{tool_name}' - marking for reconnection on next call")

                    # Don't retry timeout errors - just propagate the error
                    error_msg = f"Tool '{tool_name}' timed out on server '{self.config.name}': {e}"
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

                elif is_connection_error and attempt < max_retries - 1:
                    # CONNECTION ERROR (not timeout): Try to reconnect and retry
                    self.logger.warning(f"Connection error detected for tool '{tool_name}': {e}")
                    self._connection_healthy = False

                    # Attempt immediate reconnection for connection errors
                    async with self._health_check_lock:
                        reconnected = await self._attempt_reconnection()
                        if not reconnected:
                            break

                    self.logger.info(f"Retrying tool call '{tool_name}' after reconnection")
                    continue
                else:
                    # Non-connection error or max retries reached
                    error_msg = f"Error calling MCP tool '{tool_name}' on server '{self.config.name}': {e}"
                    self.logger.error(error_msg)
                    raise RuntimeError(error_msg)

        # If we get here, all retries failed
        raise RuntimeError(f"Failed to call tool '{tool_name}' after {max_retries} attempts")

class TinyMultiMCPTools:
    """
    Agno-style multi-server MCP manager.

    Manages multiple MCP servers simultaneously with proper resource cleanup.
    """

    def __init__(self,
                 server_configs: List[MCPServerConfig],
                 logger: Optional[logging.Logger] = None):
        self.server_configs = server_configs
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug(f"TinyMultiMCPTools initialized with {len(server_configs)} server configs")

        # Connection management
        self._async_exit_stack = AsyncExitStack()
        self.mcp_tools: Dict[str, TinyMCPTools] = {}

        # Tool registry
        self.all_tools: Dict[str, Any] = {}
        self.tool_to_server: Dict[str, str] = {}

    async def __aenter__(self) -> "TinyMultiMCPTools":
        """Connect to all MCP servers."""
        try:
            for config in self.server_configs:
                # Create and connect to each server
                mcp_tools = TinyMCPTools(config, self.logger)

                # Enter the context and add to exit stack
                await self._async_exit_stack.enter_async_context(mcp_tools)
                self.mcp_tools[config.name] = mcp_tools

                # Register tools with conflict detection
                for tool in mcp_tools.tools:
                    if tool.name in self.all_tools:
                        self.logger.warning(
                            f"Tool '{tool.name}' from server '{config.name}' "
                            f"overrides tool from server '{self.tool_to_server[tool.name]}'"
                        )

                    self.all_tools[tool.name] = tool
                    self.tool_to_server[tool.name] = config.name

            total_tools = len(self.all_tools)
            total_servers = len(self.mcp_tools)
            self.logger.info(f"Connected to {total_servers} MCP servers with {total_tools} total tools")
            return self

        except Exception as e:
            # Cleanup on error
            await self._async_exit_stack.aclose()
            raise RuntimeError(f"Failed to initialize multi-MCP tools: {e}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup all MCP connections."""
        try:
            await self._async_exit_stack.aclose()
        except Exception as e:
            self.logger.error(f"Error during multi-MCP cleanup: {e}")

        self.mcp_tools.clear()
        self.all_tools.clear()
        self.tool_to_server.clear()
        self.logger.debug("All MCP connections closed")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], read_timeout_seconds: timedelta | None = None, progress_callback: Optional[Callable[[float, Optional[float], Optional[str]], Awaitable[None]]] = None) -> Any:
        """
        Call a tool on the appropriate server with health-check based resilience.

        The call will automatically handle connection failures and attempt reconnection
        as needed through the individual TinyMCPTools instances.
        """
        server_name = self.tool_to_server.get(tool_name)
        if not server_name:
            raise ValueError(f"Tool '{tool_name}' not found in any connected server")

        mcp_tools = self.mcp_tools.get(server_name)
        if not mcp_tools:
            raise RuntimeError(f"Server '{server_name}' not connected")

        return await mcp_tools.call_tool(tool_name, arguments, read_timeout_seconds=read_timeout_seconds, progress_callback=progress_callback)

    async def health_check_all_servers(self) -> Dict[str, bool]:
        """
        Perform health checks on all connected servers.

        Returns:
            Dict mapping server names to their health status (True = healthy, False = unhealthy)
        """
        health_status = {}

        for server_name, mcp_tools in self.mcp_tools.items():
            try:
                is_healthy = await mcp_tools._check_connection_health()
                health_status[server_name] = is_healthy
                if not is_healthy:
                    self.logger.warning(f"Server '{server_name}' is unhealthy")
            except Exception as e:
                self.logger.error(f"Health check failed for server '{server_name}': {e}")
                health_status[server_name] = False

        healthy_count = sum(health_status.values())
        total_count = len(health_status)
        self.logger.info(f"Health check complete: {healthy_count}/{total_count} servers healthy")

        return health_status

    async def reconnect_unhealthy_servers(self) -> Dict[str, bool]:
        """
        Attempt to reconnect to all unhealthy servers.

        Returns:
            Dict mapping server names to their reconnection success status
        """
        # First, check health of all servers
        health_status = await self.health_check_all_servers()

        reconnection_results = {}

        for server_name, is_healthy in health_status.items():
            if not is_healthy:
                mcp_tools = self.mcp_tools.get(server_name)
                if mcp_tools:
                    self.logger.info(f"Attempting to reconnect unhealthy server '{server_name}'")
                    try:
                        success = await mcp_tools._attempt_reconnection()
                        reconnection_results[server_name] = success
                        if success:
                            self.logger.info(f"Successfully reconnected to server '{server_name}'")
                        else:
                            self.logger.error(f"Failed to reconnect to server '{server_name}'")
                    except Exception as e:
                        self.logger.error(f"Error reconnecting to server '{server_name}': {e}")
                        reconnection_results[server_name] = False
            else:
                # Server is healthy, no reconnection needed
                reconnection_results[server_name] = True

        return reconnection_results

    async def call_tools_parallel(self, tool_calls: List[Dict[str, Any]], progress_callback: Optional[Callable[[float, Optional[float], Optional[str]], Awaitable[None]]] = None) -> List[Any]:
        """
        Execute multiple tools in parallel with error isolation.

        Args:
            tool_calls: List of dicts with 'name', 'arguments', and optionally 'progress_callback' keys
            progress_callback: Default progress callback for all tools (can be overridden per tool)

        Returns:
            List of results (or exceptions for failed calls)
        """
        async def call_single_tool(call):
            try:
                # Use tool-specific progress callback if provided, otherwise use the default
                tool_progress_callback = call.get('progress_callback', progress_callback)
                return await self.call_tool(call['name'], call['arguments'], progress_callback=tool_progress_callback)
            except Exception as e:
                self.logger.error(f"Tool call failed: {call['name']} - {e}")
                return e

        # Execute all tools in parallel with error isolation
        results = await asyncio.gather(
            *(call_single_tool(call) for call in tool_calls),
            return_exceptions=True
        )

        return results

    def get_tool_schemas(self) -> Dict[str, Any]:
        """Get schemas for all available tools."""
        schemas = {}
        for server_name, mcp_tools in self.mcp_tools.items():
            for tool_name, schema in mcp_tools.tool_schemas.items():
                schemas[tool_name] = {
                    **schema,
                    'server': server_name
                }
        return schemas

    def get_tools_by_server(self) -> Dict[str, List[str]]:
        """Get tools grouped by server."""
        server_tools = {}
        for server_name, mcp_tools in self.mcp_tools.items():
            server_tools[server_name] = list(mcp_tools.tool_schemas.keys())
        return server_tools