"""
Agno-style MCP integration for TinyAgent.

This module implements MCP connection management inspired by Agno's approach,
providing better async context management, multi-transport support, and
improved error handling.
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Dict, List, Optional, Any, Union
from datetime import timedelta
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

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

class TinyMCPTools:
    """
    Agno-style MCP tools manager with async context management.

    Supports multiple transport types and proper resource cleanup.
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

        # Tool management
        self.tools: List[Any] = []
        self.tool_schemas: Dict[str, Any] = {}

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

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any],read_timeout_seconds: timedelta | None = None) -> Any:
        """Call a tool with error handling and content processing."""
        if not self.session:
            raise RuntimeError("Session not established")

        if tool_name not in self.tool_schemas:
            raise ValueError(f"Tool '{tool_name}' not available on server '{self.config.name}'")

        try:
            self.logger.debug(f"Calling MCP tool '{tool_name}' with args: {arguments}")
            result = await self.session.call_tool(tool_name, arguments, read_timeout_seconds=read_timeout_seconds)

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
            error_msg = f"Error calling MCP tool '{tool_name}' on server '{self.config.name}': {e}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

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

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any],read_timeout_seconds: timedelta | None = None) -> Any:
        """Call a tool on the appropriate server."""
        server_name = self.tool_to_server.get(tool_name)
        if not server_name:
            raise ValueError(f"Tool '{tool_name}' not found in any connected server")

        mcp_tools = self.mcp_tools.get(server_name)
        if not mcp_tools:
            raise RuntimeError(f"Server '{server_name}' not connected")

        return await mcp_tools.call_tool(tool_name, arguments, read_timeout_seconds=read_timeout_seconds)

    async def call_tools_parallel(self, tool_calls: List[Dict[str, Any]]) -> List[Any]:
        """
        Execute multiple tools in parallel with error isolation.

        Args:
            tool_calls: List of dicts with 'name' and 'arguments' keys

        Returns:
            List of results (or exceptions for failed calls)
        """
        async def call_single_tool(call):
            try:
                return await self.call_tool(call['name'], call['arguments'])
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