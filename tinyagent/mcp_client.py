import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Tuple

# Keep your MCPClient implementation unchanged
import asyncio
from contextlib import AsyncExitStack

# MCP core imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class MCPClient:
    def __init__(self):
        self.session = None
        self.exit_stack = AsyncExitStack()

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
        resp = await self.session.call_tool(name, arguments)
        return resp.content

    async def close(self):
        """Clean up subprocess and streams."""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
            except (RuntimeError, asyncio.CancelledError) as e:
                # Log the error but don't re-raise it
                print(f"Error during client cleanup: {e}")
            finally:
                # Always reset these regardless of success or failure
                self.session = None
                self.exit_stack = AsyncExitStack()
