#!/usr/bin/env python3
"""
Example demonstrating how to use progress callbacks with TinyAgent's MCP implementation.

This example shows:
1. How to set up progress callbacks in MCPServerConfig
2. How to use default vs custom progress callbacks
3. How to override progress callbacks per tool call
4. Current limitations and workarounds

Note: Progress callback support is implemented in the client-side TinyAgent MCP integration.
Server-side progress notifications require MCP servers that support progress tokens and context injection.
"""

import asyncio
import logging
from datetime import timedelta
from tinyagent.mcp_client import TinyMultiMCPTools, MCPServerConfig, default_progress_callback
from tinyagent import TinyAgent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# Custom Progress Callbacks
# =============================================================================

async def simple_progress_callback(
    progress: float,
    total: float = None,
    message: str = None
) -> None:
    """Simple progress callback that prints to stdout."""
    if total and total > 0:
        percentage = (progress / total) * 100
        print(f"✨ Progress: {percentage:5.1f}% - {message or 'Working...'}")
    else:
        print(f"✨ Progress: Step {progress} - {message or 'Working...'}")

async def detailed_progress_callback(
    progress: float,
    total: float = None,
    message: str = None
) -> None:
    """Detailed progress callback with timing and ETA."""
    import time
    current_time = time.time()

    if not hasattr(detailed_progress_callback, 'start_time'):
        detailed_progress_callback.start_time = current_time

    elapsed = current_time - detailed_progress_callback.start_time

    if total and total > 0 and progress > 0:
        percentage = (progress / total) * 100
        rate = progress / elapsed if elapsed > 0 else 0
        eta = (total - progress) / rate if rate > 0 else None

        eta_str = f" (ETA: {eta:.1f}s)" if eta else ""
        print(f"📊 [{percentage:5.1f}%] {message or 'Processing...'} - "
              f"Elapsed: {elapsed:.1f}s{eta_str}")
    else:
        print(f"📊 [Step {progress}] {message or 'Processing...'} - "
              f"Elapsed: {elapsed:.1f}s")

class ProgressTracker:
    """Advanced progress tracking class."""

    def __init__(self, name: str = "Task"):
        self.name = name
        self.updates = []
        self.start_time = None

    async def __call__(
        self,
        progress: float,
        total: float = None,
        message: str = None
    ) -> None:
        """Progress callback method."""
        import time
        current_time = time.time()

        if self.start_time is None:
            self.start_time = current_time

        elapsed = current_time - self.start_time

        update = {
            "progress": progress,
            "total": total,
            "message": message,
            "elapsed": elapsed,
            "timestamp": current_time
        }
        self.updates.append(update)

        if total and total > 0:
            percentage = (progress / total) * 100
            print(f"🎯 {self.name}: [{percentage:5.1f}%] {message or 'Processing...'}")
        else:
            print(f"🎯 {self.name}: [Step {progress}] {message or 'Processing...'}")

    def get_summary(self):
        """Get a summary of the progress tracking."""
        if not self.updates:
            return "No progress updates recorded"

        total_time = self.updates[-1]["elapsed"]
        total_updates = len(self.updates)

        return f"""Progress Summary for {self.name}:
- Total updates: {total_updates}
- Total time: {total_time:.2f}s
- Average update interval: {total_time/total_updates:.2f}s
- Final progress: {self.updates[-1]['progress']}/{self.updates[-1]['total']}
"""

# =============================================================================
# Example Usage Functions
# =============================================================================

async def example_1_default_progress_callback():
    """Example 1: Using the default progress callback."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Default Progress Callback")
    print("="*60)

    # Configure MCP server with default progress callback
    config = MCPServerConfig(
        name="example_server",
        command="python",
        args=["test_mcp/slow_tools_server.py"],
        enable_default_progress_callback=True  # Enable default callback
    )

    async with TinyMultiMCPTools([config], logger) as multi_mcp:
        print("Calling task with default progress callback...")
        result = await multi_mcp.call_tool(
            tool_name="task_alpha",
            arguments={"message": "Default progress example"}
        )
        print(f"Result: Task completed successfully")

async def example_2_custom_progress_callback():
    """Example 2: Using a custom progress callback."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Custom Progress Callback")
    print("="*60)

    # Configure MCP server with custom progress callback
    config = MCPServerConfig(
        name="example_server",
        command="python",
        args=["test_mcp/slow_tools_server.py"],
        progress_callback=detailed_progress_callback
    )

    async with TinyMultiMCPTools([config], logger) as multi_mcp:
        print("Calling task with custom progress callback...")
        result = await multi_mcp.call_tool(
            tool_name="task_beta",
            arguments={"message": "Custom progress example"}
        )
        print(f"Result: Task completed successfully")

async def example_3_per_call_override():
    """Example 3: Override progress callback per tool call."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Per-Call Progress Callback Override")
    print("="*60)

    # Configure MCP server without default progress callback
    config = MCPServerConfig(
        name="example_server",
        command="python",
        args=["test_mcp/slow_tools_server.py"]
        # No default progress callback
    )

    # Create a progress tracker for this specific call
    tracker = ProgressTracker("Task Gamma")

    async with TinyMultiMCPTools([config], logger) as multi_mcp:
        print("Calling task with per-call progress callback override...")
        result = await multi_mcp.call_tool(
            tool_name="task_gamma",
            arguments={"message": "Per-call progress example"},
            progress_callback=tracker  # Override with specific callback
        )
        print(f"Result: Task completed successfully")
        print(tracker.get_summary())

async def example_4_tinyagent_integration():
    """Example 4: Using progress callbacks with TinyAgent."""
    print("\n" + "="*60)
    print("EXAMPLE 4: TinyAgent Integration")
    print("="*60)

    # Create TinyAgent
    agent = TinyAgent(model="gpt-5-mini")

    # Connect to MCP server with progress callback
    # Note: In the current implementation, progress callbacks are set at the server config level
    # Future versions may support per-agent progress callback configuration

    try:
        await agent.connect_to_server(
            command="python",
            args=["test_mcp/slow_tools_server.py"]
        )

        print("Agent connected to MCP server with slow tools")
        print("Available tools:", [tool['function']['name'] for tool in agent.available_tools])

        # Use the agent to call a tool
        # Note: Progress callbacks would need to be configured at the MCP server level
        response = await agent.run("Please run task_alpha with the message 'TinyAgent integration test'")
        print(f"Agent response: {response}")

    finally:
        await agent.close()

async def example_5_parallel_tools_with_progress():
    """Example 5: Parallel tool execution with different progress callbacks."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Parallel Tools with Progress Callbacks")
    print("="*60)

    # Configure MCP server
    config = MCPServerConfig(
        name="example_server",
        command="python",
        args=["test_mcp/slow_tools_server.py"]
    )

    # Create different progress trackers for each task
    tracker_alpha = ProgressTracker("Alpha Task")
    tracker_beta = ProgressTracker("Beta Task")
    tracker_gamma = ProgressTracker("Gamma Task")

    async with TinyMultiMCPTools([config], logger) as multi_mcp:
        print("Running multiple tasks in parallel with different progress callbacks...")

        # Prepare tool calls with different progress callbacks
        tool_calls = [
            {
                "name": "task_alpha",
                "arguments": {"message": "Parallel task Alpha"},
                "progress_callback": tracker_alpha
            },
            {
                "name": "task_beta",
                "arguments": {"message": "Parallel task Beta"},
                "progress_callback": tracker_beta
            },
            {
                "name": "task_gamma",
                "arguments": {"message": "Parallel task Gamma"},
                "progress_callback": tracker_gamma
            }
        ]

        # Execute in parallel
        results = await multi_mcp.call_tools_parallel(tool_calls)

        print("All parallel tasks completed!")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Task {i+1} failed: {result}")
            else:
                print(f"Task {i+1} completed successfully")

        # Print summaries
        print("\nProgress Summaries:")
        print(tracker_alpha.get_summary())
        print(tracker_beta.get_summary())
        print(tracker_gamma.get_summary())

# =============================================================================
# Current Limitations and Notes
# =============================================================================

def print_limitations():
    """Print current limitations and notes about progress callback implementation."""
    print("\n" + "="*60)
    print("CURRENT LIMITATIONS AND NOTES")
    print("="*60)

    limitations = """
1. Server-Side Context Injection:
   - The current MCP SDK version (1.12.2) may not automatically inject RequestContext
   - Server-side progress notifications require proper context injection to work
   - This affects the server's ability to send progress notifications back to the client

2. Progress Token Handling:
   - Progress tokens are generated client-side but may not reach the server properly
   - The server needs to receive the progress token to send progress notifications

3. Workarounds:
   - Progress callbacks are implemented and ready to work when server-side context injection is resolved
   - The infrastructure is in place for both default and custom progress callbacks
   - Per-call progress callback overrides are supported

4. Client-Side Implementation Status:
   ✅ MCPServerConfig supports progress_callback parameter
   ✅ TinyMCPTools supports progress callbacks
   ✅ TinyMultiMCPTools supports progress callbacks
   ✅ Default progress callback implementation
   ✅ Per-call progress callback overrides
   ✅ Parallel tool execution with different callbacks

5. Server-Side Implementation Status:
   ✅ Server code ready to handle progress notifications
   ❌ Context injection not working in current MCP SDK version
   ❌ Progress tokens not reaching server properly

6. Integration with TinyAgent:
   - Progress callbacks can be configured at the MCP server level
   - Future versions may support agent-level progress callback configuration
   - Current integration works with the existing tool call infrastructure

7. Recommendations:
   - Monitor MCP SDK updates for improved context injection support
   - Consider alternative approaches if needed (e.g., custom progress protocols)
   - The current implementation provides a solid foundation for when server-side support improves
"""

    print(limitations)

# =============================================================================
# Main Example Runner
# =============================================================================

async def main():
    """Run all examples."""
    print("Progress Callback Examples for TinyAgent MCP Integration")
    print("=" * 60)

    try:
        # Run all examples
        await example_1_default_progress_callback()
        await example_2_custom_progress_callback()
        await example_3_per_call_override()
        await example_4_tinyagent_integration()
        await example_5_parallel_tools_with_progress()

        # Print limitations
        print_limitations()

        print("\n" + "="*60)
        print("ALL EXAMPLES COMPLETED")
        print("="*60)

    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())