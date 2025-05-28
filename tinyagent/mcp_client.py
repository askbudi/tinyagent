#!/usr/bin/env python
# coding=utf-8

# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import warnings
import asyncio
import logging
from types import TracebackType
from typing import TYPE_CHECKING, Any, Optional, List, Dict
from contextlib import AsyncExitStack

# MCP core imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

__all__ = ["MCPClient"]

if TYPE_CHECKING:
    from mcp import StdioServerParameters

# Set up logging
logger = logging.getLogger(__name__)

class MCPClient:
    """Manages the connection to an MCP server using per-instance context manager pattern.

    This implementation adopts the per-instance context manager pattern from smolagents
    to fix cross-talk and cancel-scope errors when multiple clients are connected concurrently.

    Note: tools can only be accessed after the connection has been started with the
        `connect()` method. If you don't use the context manager we strongly encourage 
        to use "try ... finally" to ensure the connection is cleaned up.

    Args:
        server_parameters (StdioServerParameters | dict[str, Any] | None):
            Configuration parameters to connect to the MCP server.

            - An instance of `mcp.StdioServerParameters` for connecting a Stdio MCP server 
              via standard input/output using a subprocess.

            - A `dict` with command and args for stdio connection.

        logger (Optional[logging.Logger]): Custom logger instance.

    Example:
        ```python
        # fully managed context manager
        async with MCPClient() as client:
            await client.connect("python", ["-m", "mcp.examples.echo_server"])
            tools = await client.list_tools()

        # manually manage the connection:
        try:
            mcp_client = MCPClient()
            await mcp_client.connect("python", ["-m", "mcp.examples.echo_server"])
            tools = await mcp_client.list_tools()

            # use your tools here.
        finally:
            await mcp_client.disconnect()
        ```
    """

    def __init__(
        self,
        server_parameters: "StdioServerParameters" | dict[str, Any] | None = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.server_parameters = server_parameters
        self.session = None
        self.exit_stack = AsyncExitStack()
        self.logger = logger or logging.getLogger(__name__)
        
        # Simplified callback system
        self.callbacks: List[callable] = []
        
        self.logger.debug("MCPClient initialized with per-instance context manager")

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

    async def connect(self, command: str = None, args: list[str] = None):
        """Connect to the MCP server and initialize the session."""
        if command and args:
            # Legacy support for direct command/args
            params = StdioServerParameters(command=command, args=args)
        elif self.server_parameters:
            if isinstance(self.server_parameters, dict):
                # Convert dict to StdioServerParameters
                params = StdioServerParameters(
                    command=self.server_parameters.get('command'),
                    args=self.server_parameters.get('args', [])
                )
            else:
                params = self.server_parameters
        else:
            raise ValueError("Either command/args or server_parameters must be provided")
        
        try:
            # Open the stdio client transport using per-instance exit stack
            self.stdio, self.sock_write = await self.exit_stack.enter_async_context(
                stdio_client(params)
            )
            # Create and initialize the MCP client session
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.stdio, self.sock_write)
            )
            await self.session.initialize()
            self.logger.debug("MCP client connected successfully")
        except Exception as e:
            self.logger.error(f"Failed to connect MCP client: {e}")
            # Clean up on connection failure
            await self._cleanup_exit_stack()
            raise

    async def disconnect(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        exc_traceback: TracebackType | None = None,
    ):
        """Disconnect from the MCP server"""
        await self._cleanup_exit_stack()

    async def _cleanup_exit_stack(self):
        """Clean up the exit stack safely"""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
                self.logger.debug("Exit stack closed successfully")
            except Exception as e:
                # Log the error but don't re-raise it to prevent cascade failures
                self.logger.error(f"Error during exit stack cleanup: {e}")
            finally:
                # Always reset these regardless of success or failure
                self.session = None
                self.exit_stack = AsyncExitStack()

    async def list_tools(self):
        """List available tools from the MCP server."""
        if not self.session:
            raise ValueError("Client not connected. Call connect() first.")
        
        resp = await self.session.list_tools()
        self.logger.info("Available tools:")
        for tool in resp.tools:
            self.logger.info(f"  {tool.name}: {tool.description}")
        return resp.tools

    async def call_tool(self, name: str, arguments: dict):
        """
        Invokes a named tool and returns its raw content list.
        """
        if not self.session:
            raise ValueError("Client not connected. Call connect() first.")
        
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
        """Clean up subprocess and streams. Alias for disconnect()."""
        await self.disconnect()

    async def __aenter__(self):
        """Connect to the MCP server and return the client directly."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ):
        """Disconnect from the MCP server."""
        await self.disconnect(exc_type, exc_value, exc_traceback)

async def run_example():
    """Example usage of MCPClient with proper logging."""
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Get module-specific logger
    mcp_logger = logging.getLogger('tinyagent.mcp_client')
    mcp_logger.setLevel(logging.DEBUG)
    
    mcp_logger.debug("Starting MCPClient example with per-instance context manager")
    
    # Create client with our logger
    async with MCPClient(logger=mcp_logger) as client:
        # Connect to a simple echo server
        await client.connect("python", ["-m", "mcp.examples.echo_server"])
        
        # List available tools
        tools = await client.list_tools()
        
        # Call the echo tool
        result = await client.call_tool("echo", {"message": "Hello, MCP!"})
        mcp_logger.info(f"Echo result: {result}")
        
    mcp_logger.debug("Example completed")

if __name__ == "__main__":
    asyncio.run(run_example())
