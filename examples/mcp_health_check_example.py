#!/usr/bin/env python3
"""
Example demonstrating the health-check based MCP solution.

This example shows how to configure and use the enhanced TinyAgent
with resilient MCP connections that automatically recover from failures.
"""

import asyncio
import logging
from datetime import timedelta

from tinyagent.mcp_client import MCPServerConfig, TinyMultiMCPTools

# Configure logging to see health check activity
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_resilient_mcp_usage():
    """
    Example of using the enhanced MCP client with health-check based resilience.
    """
    logger.info("=== MCP Health-Check Example ===")

    # Configure MCP servers with health-check settings
    server_configs = [
        MCPServerConfig(
            name="cursor_subagent",
            command="npx",
            args=["-y", "cursor_subagent"],

            # Standard timeout settings
            timeout=900.0,  # 15 minutes for long-running operations

            # Health check configuration
            health_check_interval=30.0,    # Ping every 30 seconds
            health_check_timeout=5.0,      # Ping timeout of 5 seconds

            # Reconnection configuration
            max_reconnect_attempts=3,      # Try to reconnect up to 3 times
            reconnect_backoff_base=2.0,    # Start with 2 second delays
            reconnect_backoff_max=60.0,    # Max 60 second delay between attempts

            # Tool filtering (optional)
            # include_tools=["specific_tool_name"],  # Only use these tools
            # exclude_tools=["unwanted_tool"],       # Exclude these tools
        ),

        # Add more servers as needed
        MCPServerConfig(
            name="another_server",
            command="python",
            args=["-m", "another_mcp_server"],

            # Different health check settings for different servers
            health_check_interval=60.0,    # Less frequent checks for stable server
            health_check_timeout=10.0,
            max_reconnect_attempts=5,
        )
    ]

    # Create multi-server MCP manager
    async with TinyMultiMCPTools(server_configs) as mcp_tools:
        logger.info("Connected to MCP servers")

        # Get available tools
        tool_schemas = mcp_tools.get_tool_schemas()
        logger.info(f"Available tools: {list(tool_schemas.keys())}")

        # Demonstrate health checking
        logger.info("\n--- Performing health checks ---")
        health_status = await mcp_tools.health_check_all_servers()
        for server, is_healthy in health_status.items():
            status = "✓ Healthy" if is_healthy else "✗ Unhealthy"
            logger.info(f"Server '{server}': {status}")

        # Example tool calls with automatic error recovery
        logger.info("\n--- Example tool calls ---")

        try:
            # This call will automatically handle connection issues
            result = await mcp_tools.call_tool(
                "example_tool",
                {"parameter": "value"},
                read_timeout_seconds=timedelta(seconds=300)  # 5 minute timeout for this specific call
            )
            logger.info(f"Tool result: {result}")

        except ValueError as e:
            # Tool not found
            logger.warning(f"Tool not available: {e}")

        except RuntimeError as e:
            # Connection or execution error
            logger.error(f"Tool execution failed: {e}")

        # Demonstrate parallel tool execution with error isolation
        logger.info("\n--- Parallel tool execution ---")

        tool_calls = [
            {"name": "tool1", "arguments": {"param": "value1"}},
            {"name": "tool2", "arguments": {"param": "value2"}},
            {"name": "tool3", "arguments": {"param": "value3"}},
        ]

        # Execute tools in parallel - failures in one won't affect others
        results = await mcp_tools.call_tools_parallel(tool_calls)

        for i, result in enumerate(results):
            tool_name = tool_calls[i]["name"]
            if isinstance(result, Exception):
                logger.error(f"Tool '{tool_name}' failed: {result}")
            else:
                logger.info(f"Tool '{tool_name}' succeeded: {result}")

        # Demonstrate manual health management
        logger.info("\n--- Manual health management ---")

        # Manually check and reconnect unhealthy servers
        reconnect_results = await mcp_tools.reconnect_unhealthy_servers()
        for server, success in reconnect_results.items():
            if success:
                logger.info(f"Server '{server}': Connection verified")
            else:
                logger.warning(f"Server '{server}': Reconnection failed")


async def example_with_tinyagent():
    """
    Example of using the enhanced MCP client with TinyAgent.
    """
    logger.info("\n=== TinyAgent with Health-Check MCP ===")

    from tinyagent import TinyAgent

    # Configure MCP servers for TinyAgent
    mcp_configs = [
        MCPServerConfig(
            name="cursor_subagent",
            command="npx",
            args=["-y", "cursor_subagent"],

            # Optimized settings for TinyAgent usage
            timeout=600.0,                 # 10 minutes
            health_check_interval=45.0,    # Check every 45 seconds
            health_check_timeout=8.0,      # Allow longer ping timeout
            max_reconnect_attempts=2,      # Fewer attempts to avoid long delays
            reconnect_backoff_base=1.0,    # Faster initial reconnection
        )
    ]

    # Create TinyAgent with MCP configuration
    agent = TinyAgent(
        model="claude-3-sonnet-20240229",
        # In a real scenario, you'd pass the mcp_configs to TinyAgent
        # This is just an example of how the configuration would look
        tool_call_timeout=300.0,  # 5 minutes for individual tool calls
        # mcp_configs=mcp_configs,  # Would be passed to agent constructor
    )

    logger.info("TinyAgent configured with resilient MCP connections")

    # The agent will now automatically:
    # 1. Perform health checks on MCP servers
    # 2. Attempt reconnection when connections fail
    # 3. Retry tool calls after successful reconnection
    # 4. Provide detailed logging of connection issues


if __name__ == "__main__":
    # Run the basic example
    asyncio.run(example_resilient_mcp_usage())

    # Run the TinyAgent example
    asyncio.run(example_with_tinyagent())