"""
Simple MCP integration for TinyAgent following Agno's one-session-per-call approach.

This module implements lightweight MCP connection management with:
- One session per tool call (ephemeral sessions)
- Simple error handling with fail-fast approach
- No complex health checks or retry logic
- Concurrent request isolation
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable
from datetime import timedelta
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
logger = logging.getLogger(__name__)

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

    logger.debug(progress_msg)



@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    command: str
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    timeout: float = 5.0  # Short timeout, fail fast
    include_tools: Optional[List[str]] = None
    exclude_tools: Optional[List[str]] = None
    progress_callback: Optional[Callable[[float, Optional[float], Optional[str]], Awaitable[None]]] = None
    enable_default_progress_callback: bool = True

class TinyMCPTools:
    """
    Simple MCP tools manager following Agno's approach.

    Maintains a session for the context lifecycle with simple error handling.
    No complex health checks or retry logic - just fail fast and clean.
    """

    def __init__(self,
                 config: MCPServerConfig,
                 logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Session management
        self.session: Optional[ClientSession] = None
        self._context = None
        self._session_context = None
        self._initialized = False

        # Tool schemas
        self.tool_schemas: Dict[str, Any] = {}

        # Progress callback setup
        self.progress_callback = config.progress_callback
        if self.progress_callback is None and config.enable_default_progress_callback:
            # Use default progress callback with bound logger
            self.progress_callback = lambda p, t, m: default_progress_callback(p, t, m, self.logger)

    async def __aenter__(self) -> "TinyMCPTools":
        """Async context manager entry - establish connection and discover tools."""
        if self.session is not None:
            if not self._initialized:
                await self.initialize()
            return self

        try:
            # Create stdio client context
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

            self.logger.debug(f"Connected to MCP server '{self.config.name}'")
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

            # Store schemas
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
        Call a tool using the established session.

        Simple error handling with fail-fast approach - no retries or complex recovery.
        If the session is broken, the entire context needs to be recreated.
        """
        if tool_name not in self.tool_schemas:
            raise ValueError(f"Tool '{tool_name}' not available on server '{self.config.name}'")

        if not self.session:
            raise RuntimeError("Session not established")

        self.logger.debug(f"Calling MCP tool '{tool_name}' with args: {arguments}")

        try:
            # Use provided progress_callback, or fall back to instance callback
            final_progress_callback = progress_callback or self.progress_callback

            # Call the tool with current session
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
            return response

        except Exception as e:
            # Simple error handling - log and re-raise
            error_msg = f"Error calling MCP tool '{tool_name}' on server '{self.config.name}': {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

class TinyMultiMCPTools:
    """
    Simple multi-server MCP manager.

    Manages multiple MCP servers simultaneously with proper resource cleanup.
    """

    def __init__(self,
                 server_configs: List[MCPServerConfig],
                 logger: Optional[logging.Logger] = None):
        self.server_configs = server_configs
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug(f"TinyMultiMCPTools initialized with {len(server_configs)} server configs")

        # Connection management
        self._async_exit_stack = None
        self.mcp_tools: Dict[str, TinyMCPTools] = {}

        # Tool registry
        self.all_tools: Dict[str, Any] = {}
        self.tool_to_server: Dict[str, str] = {}

    async def __aenter__(self) -> "TinyMultiMCPTools":
        """Connect to all MCP servers."""
        try:
            # Use AsyncExitStack to manage all the contexts
            self._async_exit_stack = AsyncExitStack()

            for config in self.server_configs:
                # Create and connect to each server
                mcp_tools = TinyMCPTools(config, self.logger)

                # Enter the context and add to exit stack
                await self._async_exit_stack.enter_async_context(mcp_tools)
                self.mcp_tools[config.name] = mcp_tools

                # Register tools with conflict detection
                for tool_name, tool_schema in mcp_tools.tool_schemas.items():
                    if tool_name in self.all_tools:
                        self.logger.warning(
                            f"Tool '{tool_name}' from server '{config.name}' "
                            f"overrides tool from server '{self.tool_to_server[tool_name]}'"
                        )

                    self.all_tools[tool_name] = tool_schema
                    self.tool_to_server[tool_name] = config.name

            total_tools = len(self.all_tools)
            total_servers = len(self.mcp_tools)
            self.logger.info(f"Connected to {total_servers} MCP servers with {total_tools} total tools")
            return self

        except Exception as e:
            # Cleanup on error
            if hasattr(self, '_async_exit_stack'):
                await self._async_exit_stack.aclose()
            raise RuntimeError(f"Failed to initialize multi-MCP tools: {e}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup all MCP connections."""
        try:
            if hasattr(self, '_async_exit_stack'):
                await self._async_exit_stack.aclose()
        except Exception as e:
            self.logger.error(f"Error during multi-MCP cleanup: {e}")

        self.mcp_tools.clear()
        self.all_tools.clear()
        self.tool_to_server.clear()
        self.logger.debug("All MCP connections closed")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], read_timeout_seconds: timedelta | None = None, progress_callback: Optional[Callable[[float, Optional[float], Optional[str]], Awaitable[None]]] = None) -> Any:
        """
        Call a tool on the appropriate server.

        Uses the established session for that server.
        """
        server_name = self.tool_to_server.get(tool_name)
        if not server_name:
            raise ValueError(f"Tool '{tool_name}' not found in any connected server")

        mcp_tools = self.mcp_tools.get(server_name)
        if not mcp_tools:
            raise RuntimeError(f"Server '{server_name}' not connected")

        return await mcp_tools.call_tool(tool_name, arguments, read_timeout_seconds=read_timeout_seconds, progress_callback=progress_callback)


    async def call_tools_parallel(self, tool_calls: List[Dict[str, Any]], progress_callback: Optional[Callable[[float, Optional[float], Optional[str]], Awaitable[None]]] = None) -> List[Any]:
        """
        Execute multiple tools in parallel with excellent isolation.

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
        for tool_name, schema in self.all_tools.items():
            server_name = self.tool_to_server[tool_name]
            schemas[tool_name] = {
                **schema,
                'server': server_name
            }
        return schemas

    def get_tools_by_server(self) -> Dict[str, List[str]]:
        """Get tools grouped by server."""
        server_tools = {}
        for tool_name, server_name in self.tool_to_server.items():
            if server_name not in server_tools:
                server_tools[server_name] = []
            server_tools[server_name].append(tool_name)
        return server_tools