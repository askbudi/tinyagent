import asyncio
import json
import logging
from typing import Optional, List, Callable, Any, Coroutine

from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession, StdioServerParameters

logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, logger: Optional[logging.Logger] = None):
        # We'll hold each context manager separately rather than in one stack:
        self._stdio_ctx = None
        self._session_ctx = None
        self.stdio = None
        self.sock_write = None
        self.session = None

        self.logger = logger or logging.getLogger(__name__)
        # Simplified callback system
        self.callbacks: List[Callable[..., Coroutine[Any, Any, Any]]] = []

        self.logger.debug('MCPClient initialized')

    def add_callback(self, callback: Callable[..., Coroutine[Any, Any, Any]]) -> None:
        self.callbacks.append(callback)

    async def _run_callbacks(self, event: str, **kwargs):
        for cb in self.callbacks:
            try:
                await cb(event, **kwargs)
            except Exception as e:
                self.logger.error(f'Error in callback {cb}: {e}')

    async def connect(self, command: str, args: list):
        params = StdioServerParameters(command=command, args=args)
        # 1) enter stdio_client context
        self._stdio_ctx = stdio_client(params)
        try:
            self.stdio, self.sock_write = await self._stdio_ctx.__aenter__()
        except Exception as e:
            self.logger.error(f'Failed to start stdio_client: {e}')
            raise

        # 2) enter ClientSession context
        self._session_ctx = ClientSession(self.stdio, self.sock_write)
        try:
            self.session = await self._session_ctx.__aenter__()
            await self.session.initialize()
        except Exception as e:
            self.logger.error(f'Failed to initialize MCP session: {e}')
            # make sure we unwind the stdio context if session init fails
            await self._stdio_ctx.__aexit__(None, None, None)
            raise

    async def list_tools(self):
        resp = await self.session.list_tools()
        print('Available tools:')
        for tool in resp.tools:
            print(f' • {tool.name}: {tool.description}')

    async def call_tool(self, name: str, arguments: dict):
        await self._run_callbacks('tool_start', tool_name=name, arguments=arguments)
        try:
            resp = await self.session.call_tool(name, arguments)
            await self._run_callbacks('tool_end', tool_name=name, arguments=arguments, result=resp.content, success=True)
            return resp.content
        except Exception as e:
            await self._run_callbacks('tool_end', tool_name=name, arguments=arguments, error=str(e), success=False)
            raise

    async def close(self):
        """Clean up subprocess and streams, one context at a time."""
        # 1) teardown session
        if self._session_ctx is not None:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception as e:
                self.logger.error(f'Error closing MCP session: {e}')
            finally:
                self.session = None
                self._session_ctx = None

        # 2) teardown stdio
        if self._stdio_ctx is not None:
            try:
                await self._stdio_ctx.__aexit__(None, None, None)
            except Exception as e:
                self.logger.error(f'Error closing stdio client: {e}')
            finally:
                self.stdio = None
                self.sock_write = None
                self._stdio_ctx = None
