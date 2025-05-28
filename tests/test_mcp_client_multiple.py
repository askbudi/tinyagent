import asyncio
import pytest
from tinyagent.mcp_client import MCPClient
@pytest.mark.asyncio
async def test_multiple_clients():
    clients = [MCPClient() for _ in range(3)]
    await asyncio.gather(*(client.connect("python", ["-m", "mcp.examples.echo_server"]) for client in clients))
    results = await asyncio.gather(*(client.call_tool("echo", {"message": f"Hello {i}"}) for i, client in enumerate(clients)))
    for i, result in enumerate(results):
        assert result == f"Hello {i}"
    await asyncio.gather(*(client.close() for client in clients))
