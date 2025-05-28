import warnings
import asyncio
import logging
from types import TracebackType
from typing import Any, Optional, List, Union, Tuple
from smolagents.tools import Tool
try:
    from mcpadapt.core import MCPAdapt
    from mcpadapt.smolagents_adapter import SmolAgentsAdapter
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "Please install 'mcp' extra to use MCPClient: `pip install 'tinyagent[mcp]'`"
    )
from mcp.client.stdio import StdioServerParameters
class MCPClient:
    """
    Manages the connection to one or multiple MCP servers and makes its tools available to TinyAgent.
    Example:
        client = MCPClient()
        await client.connect("python", ["-m", "mcp.examples.echo_server"])
        result = await client.call_tool("echo", {"message": "Hello"})
        await client.close()
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        self._adapter = None
        self._tools: Optional[List[Tool]] = None
        self.logger = logger or logging.getLogger(__name__)
        self.logger.debug("MCPClient initialized (smolagents-based)")
