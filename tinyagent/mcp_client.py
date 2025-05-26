import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional, Any

# MCP core imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Set up logging
logger = logging.getLogger(__name__)

class MCPClient:
    """
    Asynchronous client for MCP servers that supports multiple concurrent instances without cancel-scope errors.

    Usage:
        client = MCPClient()
        await client.connect(...)
        # use client.call_tool, etc.
        await client.close()
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.stdio = None
        self.sock_write = None
        self.session = None
        self.callbacks: List[Callable] = []
        self.logger.debug("MCPClient initialized")

    def add_callback(self, callback: Callable) -> None:
        """Register a callback(event_name, client, **kwargs)"""
        self.callbacks.append(callback)

    async def _run_callbacks(self, event_name: str, **kwargs) -> None:
        for cb in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event_name, self, **kwargs)
                elif hasattr(cb, '__call__') and asyncio.iscoroutinefunction(cb.__call__):
                    await cb(event_name, self, **kwargs)
                else:
                    cb(event_name, self, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in callback for {event_name}: {e}")

    async def connect(self, command: str, args: List[str]) -> None:
        """
        Launch MCP server subprocess and initialize client.
        :param command: executable, e.g. 'python'
        :param args: list of args, e.g. ['-m', 'mcp.examples.echo_server']
        """
        params = StdioServerParameters(command=command, args=args)
        # open stdio transport
        self.stdio, self.sock_write = await stdio_client(params)
        # enter client session context
        self.session = await ClientSession(self.stdio, self.sock_write).__aenter__()
        await self.session.initialize()
        self.logger.debug("MCPClient connected to server")

    async def list_tools(self) -> None:
        resp = await self.session.list_tools()
        print("Available tools:")
        for tool in resp.tools:
            print(f"- {tool.name}: {tool.description}")

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        await self._run_callbacks("tool_start", tool_name=name, arguments=arguments)
        try:
            resp = await self.session.call_tool(name, arguments)
            await self._run_callbacks(
                "tool_end", tool_name=name, arguments=arguments, result=resp.content, success=True
            )
            return resp.content
        except Exception as e:
            await self._run_callbacks(
                "tool_end", tool_name=name, arguments=arguments, error=str(e), success=False
            )
            raise

    async def close(self) -> None:
        """Clean up session and subprocess."""
        # exit session context
        if self.session:
            try:
                await self.session.__aexit__(None, None, None)
            except Exception as e:
                self.logger.error(f"Error closing session: {e}")
        # close stdio and sock
        for stream in [self.sock_write, self.stdio]:
            try:
                if hasattr(stream, 'close'):
                    stream.close()
            except Exception as e:
                self.logger.error(f"Error closing stream: {e}")
        # reset state
        self.session = None
        self.sock_write = None
        self.stdio = None
        self.logger.debug("MCPClient closed")
