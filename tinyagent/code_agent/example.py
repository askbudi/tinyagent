"""
Example usage of TinyCodeAgent with Gradio UI.

This example demonstrates how to initialize and use TinyCodeAgent
following the guidelines from gradio_agent.md and README.md.
"""

import asyncio
import os
import sys
import tempfile
import shutil
import logging
from typing import Dict, Any, Union

from tinyagent.hooks.logging_manager import LoggingManager
from tinyagent.hooks.gradio_callback import GradioCallback
from .tiny_code_agent import TinyCodeAgent
from .tools.example_tools import get_weather, get_traffic


async def run_example():
    """Example usage of TinyCodeAgent with GradioCallback."""
    
    # --- Logging Setup ---
    log_manager = LoggingManager(default_level=logging.INFO)
    log_manager.set_levels({
        'tinyagent.hooks.gradio_callback': logging.DEBUG,
        'tinyagent.tiny_agent': logging.DEBUG,
        'tinyagent.mcp_client': logging.DEBUG,
        'tinyagent.code_agent': logging.DEBUG,
    })
    
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    
    ui_logger = log_manager.get_logger('tinyagent.hooks.gradio_callback')
    agent_logger = log_manager.get_logger('tinyagent.code_agent')
    ui_logger.info("--- Starting TinyCodeAgent Example ---")
    
    # --- Configuration ---
    model = "gpt-5-mini"
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        ui_logger.error("OPENAI_API_KEY environment variable not set.")
        return

    # Create a temporary folder for file uploads
    upload_folder = tempfile.mkdtemp(prefix="gradio_uploads_")
    ui_logger.info(f"Created temporary upload folder: {upload_folder}")
    
    # --- Modal Configuration ---
    modal_secrets: Dict[str, Union[str, None]] = {
        "OPENAI_API_KEY": api_key,
        # Add other secrets as needed
    }
    
    provider_config = {
        "modal_secrets": modal_secrets,
        "pip_packages": ["tinyagent-py[all]", "requests", "cloudpickle"],
        "default_python_codes": [
            "import random",
            "import requests", 
            "import cloudpickle",
            "import tempfile",
            "import shutil",
            "import asyncio",
            "import logging",
            "import time"
        ]
    }
    
    try:
        # --- Initialize TinyCodeAgent ---
        agent = TinyCodeAgent(
            model=model,
            api_key=api_key,
            log_manager=log_manager,
            provider="modal",
            tools=[get_weather, get_traffic],
            provider_config=provider_config
        )
        
        # --- Create Gradio UI ---
        gradio_ui = GradioCallback(
            file_upload_folder=upload_folder,
            show_thinking=True,
            show_tool_calls=True,
            logger=ui_logger
        )
        agent.add_callback(gradio_ui)
        
        # --- Connect to MCP servers (as per contribution guide) ---
        try:
            ui_logger.info("Connecting to MCP servers...")
            await agent.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
            ui_logger.info("Connected to MCP servers.")
        except Exception as e:
            ui_logger.warning(f"Failed to connect to MCP servers: {e}")
            # Continue without servers - we still have the local tools
        
        # --- Launch Gradio Interface ---
        ui_logger.info("Launching Gradio interface...")
        try:
            gradio_ui.launch(
                agent.agent,  # Pass the underlying TinyAgent
                title="TinyCodeAgent Chat Interface",
                description="Chat with TinyCodeAgent. Try asking: 'I need to know the weather and traffic in Toronto, Montreal, New York, Paris and San Francisco.'",
                share=False,
                prevent_thread_lock=True,
                show_error=True,
                mcp_server=True,
            )
            ui_logger.info("Gradio interface launched (non-blocking).")
            
            # Keep the event loop running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            ui_logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            ui_logger.error(f"Failed to launch or run Gradio app: {e}", exc_info=True)
            
    finally:
        # Clean up
        ui_logger.info("Cleaning up resources...")
        if os.path.exists(upload_folder):
            ui_logger.info(f"Removing temporary upload folder: {upload_folder}")
            shutil.rmtree(upload_folder)
        
        if 'agent' in locals():
            await agent.close()
        
        ui_logger.info("--- TinyCodeAgent Example Finished ---")


def simple_example():
    """Simple example without Gradio UI."""
    async def _simple_example():
        # Basic setup
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("OPENAI_API_KEY environment variable not set.")
            return
        
        # Initialize TinyCodeAgent
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            api_key=api_key,
            tools=[get_weather, get_traffic]
        )
        
        try:
            # Run a simple query
            result = await agent.run(
                "I need to check the weather and traffic in Toronto. Can you help me?"
            )
            print(f"\nResult: {result}")
            
        finally:
            await agent.close()
    
    asyncio.run(_simple_example())


if __name__ == "__main__":
    # Run the full example with Gradio
    asyncio.run(run_example())
    
    # Uncomment to run the simple example instead
    # simple_example()