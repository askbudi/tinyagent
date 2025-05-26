#!/usr/bin/env python
# coding=utf-8
"""
MCPClient implementation for TinyAgent based on HuggingFace SmolAgents
"""
from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any, Union, List, Dict

from mcpadapt.core import MCPAdapt
from mcpadapt.smolagents_adapter import SmolAgentsAdapter
from smolagents.tools import Tool

__all__ = ["MCPClient"]

if TYPE_CHECKING:
    from mcpadapt.core import StdioServerParameters

class MCPClient:
    """Manage the connection to an MCP server and expose tools to TinyAgent."""
    def __init__(
        self,
        server_parameters: Union[
            StdioServerParameters,
            Dict[str, Any],
            List[Union[StdioServerParameters, Dict[str, Any]]],
        ],
    ):
        try:
            # Ensure MCPAdapt is available
            import mcpadapt
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "Please install the 'mcp' extra to use MCPClient: `pip install 'tinyagent[mcp]'`"
            )
        self._adapter = MCPAdapt(server_parameters, SmolAgentsAdapter())
        self._tools: List[Tool] | None = None
        # Automatically connect on init
        self.connect()

    def connect(self) -> None:
        """Connect to the MCP server and initialize tools."""
        self._tools = self._adapter.__enter__()

    def disconnect(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        exc_traceback: TracebackType | None = None,
    ) -> None:
        """Disconnect from the MCP server."""
        self._adapter.__exit__(exc_type, exc_value, exc_traceback)

    def get_tools(self) -> List[Tool]:
        """Return the list of tools from the MCP server."""
        if self._tools is None:
            raise ValueError(
                "Could not retrieve tools, ensure `connect()` has been called."
            )
        return self._tools

    def __enter__(
        self,
    ) -> List[Tool]:
        """Enter context, return tools."""
        return self.get_tools()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        """Exit context, disconnect."""
        self.disconnect(exc_type, exc_value, exc_traceback)
