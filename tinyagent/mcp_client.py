import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, Union

from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

class MCPClient:
    """
    Manages multiple connections to MCP servers and aggregates tools.
    """
    def __init__(
        self,
        server_parameters: Union[
            StdioServerParameters,
            Dict[str, Any],
            List[Union[StdioServerParameters, Dict[str, Any]]]
        ],
        logger: Optional[logging.Logger] = None,
    ):
        self.logger = logger or logging.getLogger(__name__)
        # Normalize to list
        if not isinstance(server_parameters, list):
            self.server_parameters = [server_parameters]
        else:
            self.server_parameters = server_parameters

        self.exit_stack = AsyncExitStack()
        self.sessions: List[ClientSession] = []
        self.tools: List[Dict[str, Any]] = []
        self._tool_session: Dict[str, ClientSession] = {}
        self.callbacks: List[Callable] = []

    def add_callback(self, callback: Callable) -> None:
        """
        Add a callback: async or sync func(event_name, client, **kwargs)
        """
        self.callbacks.append(callback)

    async def _run_callbacks(self, event_name: str, **kwargs) -> None:
        for callback in self.callbacks:
            try:
                self.logger.debug(f"Callback: {callback}, event: {event_name}")
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_name, self, **kwargs)
                else:
                    if hasattr(callback, '__call__') and asyncio.iscoroutinefunction(callback.__call__):
                        await callback(event_name, self, **kwargs)
                    else:
                        callback(event_name, self, **kwargs)
            except Exception as e:
                self.logger.error(f"Error in callback {event_name}: {e}")

    async def connect(self) -> None:
        """
        Connect to all MCP servers and gather tools.
        """
        for params in self.server_parameters:
            # Build parameters object
            if isinstance(params, dict):
                params_obj = StdioServerParameters(**params)
            elif isinstance(params, StdioServerParameters):
                params_obj = params
            else:
                raise ValueError(f"Invalid server param type: {type(params)}")

            # Enter stdio transport
            stdio, sock_write = await self.exit_stack.enter_async_context(
                stdio_client(params_obj)
            )
            # Enter client session
            session = await self.exit_stack.enter_async_context(
                ClientSession(stdio, sock_write)
            )
            await session.initialize()
            self.sessions.append(session)

        # Aggregate tools and map to sessions
        for session in self.sessions:
            resp = await session.list_tools()
            for tool in resp.tools:
                self.tools.append({
                    'name': tool.name,
                    'description': tool.description,
                    'schema': getattr(tool, 'schema', None),
                })
                self._tool_session[tool.name] = session

    async def list_tools(self) -> None:
        """
        Print all available tools.
        """
        print("Available tools:")
        for t in self.tools:
            print(f" • {t['name']}: {t['description']}")

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """
        Invoke named tool on its session.
        """
        await self._run_callbacks("tool_start", tool_name=name, arguments=arguments)
        if name not in self._tool_session:
            raise ValueError(f"Tool '{name}' not found.")
        session = self._tool_session[name]
        try:
            resp = await session.call_tool(name, arguments)
            await self._run_callbacks(
                "tool_end",
                tool_name=name,
                arguments=arguments,
                result=resp.content,
                success=True,
            )
            return resp.content
        except Exception as e:
            await self._run_callbacks(
                "tool_end",
                tool_name=name,
                arguments=arguments,
                error=str(e),
                success=False,
            )
            raise

    async def close(self) -> None:
        """
        Cleanup all sessions and transports.
        """
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
        finally:
            self.sessions = []
            self.tools = []
            self._tool_session = {}
            self.exit_stack = AsyncExitStack()
