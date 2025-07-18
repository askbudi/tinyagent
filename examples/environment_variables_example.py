#!/usr/bin/env python3
"""
Environment Variables Example for TinyAgent and TinyCodeAgent

This example demonstrates how to pass environment variables when connecting to MCP servers.
Environment variables are useful for:
- Configuring MCP servers with API keys
- Setting debug modes
- Customizing server behavior
- Managing connection settings
"""

import asyncio
import logging
import os
import sys

# Add the parent directory to the path to import tinyagent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tinyagent import TinyAgent
from tinyagent.code_agent import TinyCodeAgent
from tinyagent.hooks.logging_manager import LoggingManager
from tinyagent.hooks.rich_ui_callback import RichUICallback

async def main():
    """Main example function demonstrating environment variable usage."""
    
    # Set up logging
    log_manager = LoggingManager(default_level=logging.INFO)
    log_manager.set_levels({
        'tinyagent.tiny_agent': logging.DEBUG,
        'tinyagent.mcp_client': logging.INFO,
        'tinyagent.code_agent': logging.INFO,
    })
    
    # Configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    
    logger = log_manager.get_logger('environment_variables_example')
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("Please set the OPENAI_API_KEY environment variable")
        return
    
    logger.info("Starting Environment Variables Example")
    
    # Example 1: TinyAgent with environment variables
    logger.info("=== TinyAgent with Environment Variables ===")
    
    agent = TinyAgent(
        model="gpt-4.1-mini",
        api_key=api_key,
        logger=logger
    )
    
    # Add Rich UI callback
    rich_ui = RichUICallback(
        markdown=True,
        show_message=True,
        show_tool_calls=True,
        logger=logger
    )
    agent.add_callback(rich_ui)
    
    try:
        # Connect to MCP servers with different environment variable configurations
        
        # Example 1a: Basic environment variables
        basic_env = {
            "DEBUG": "true",
            "LOG_LEVEL": "info",
            "TIMEOUT": "30"
        }
        
        await agent.connect_to_server(
            "npx", 
            ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
            env=basic_env
        )
        logger.info("Connected to Airbnb MCP server with basic environment variables")
        
        # Example 1b: Environment variables with API configuration
        api_env = {
            "NODE_ENV": "production",
            "API_RATE_LIMIT": "100",
            "CACHE_ENABLED": "false",
            "REQUEST_TIMEOUT": "5000"
        }
        
        await agent.connect_to_server(
            "npx", 
            ["-y", "@modelcontextprotocol/server-sequential-thinking"],
            env=api_env
        )
        logger.info("Connected to Sequential Thinking MCP server with API environment variables")
        
        # Test the agent
        logger.info("Testing TinyAgent with environment variables...")
        response = await agent.run("Plan a 3-day trip to Paris with a budget of $1000", max_turns=5)
        logger.info(f"Agent response: {response}")
        
    except Exception as e:
        logger.error(f"Error in TinyAgent example: {e}")
    finally:
        await agent.close()
    
    # Example 2: TinyCodeAgent with environment variables
    logger.info("\n=== TinyCodeAgent with Environment Variables ===")
    
    code_agent = TinyCodeAgent(
        model="gpt-4.1-mini",
        api_key=api_key,
        provider="modal",
        local_execution=False,
        pip_packages=["requests", "pandas"],
        authorized_imports=["requests", "pandas", "json", "os"]
    )
    
    try:
        # Connect with environment variables specific to code execution
        code_env = {
            "PYTHON_ENV": "production",
            "MAX_EXECUTION_TIME": "300",
            "MEMORY_LIMIT": "1GB",
            "SANDBOX_MODE": "strict"
        }
        
        await code_agent.connect_to_server(
            "npx", 
            ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
            env=code_env
        )
        logger.info("Connected TinyCodeAgent with code execution environment variables")
        
        # Test the code agent
        logger.info("Testing TinyCodeAgent with environment variables...")
        code_response = await code_agent.run(
            "Write a Python script that fetches data from a public API and analyzes it",
            max_turns=5
        )
        logger.info(f"Code agent response: {code_response}")
        
    except Exception as e:
        logger.error(f"Error in TinyCodeAgent example: {e}")
    finally:
        await code_agent.close()
    
    # Example 3: Advanced environment variable patterns
    logger.info("\n=== Advanced Environment Variable Patterns ===")
    
    # Pattern 1: Environment variables from system environment
    system_env = {
        "HOME": os.environ.get("HOME", "/tmp"),
        "PATH": os.environ.get("PATH", ""),
        "USER": os.environ.get("USER", "unknown")
    }
    
    # Pattern 2: Conditional environment variables
    debug_mode = os.environ.get("DEBUG", "false").lower() == "true"
    conditional_env = {
        "DEBUG": str(debug_mode),
        "LOG_LEVEL": "debug" if debug_mode else "info",
        "VERBOSE": "true" if debug_mode else "false"
    }
    
    # Pattern 3: Environment variables with secrets (be careful with logging!)
    secret_env = {
        "API_KEY": os.environ.get("MCP_API_KEY", ""),
        "SECRET_TOKEN": os.environ.get("MCP_SECRET_TOKEN", "")
    }
    
    # Combine all patterns
    combined_env = {**system_env, **conditional_env}
    # Only add secrets if they exist
    if secret_env["API_KEY"]:
        combined_env["API_KEY"] = secret_env["API_KEY"]
    if secret_env["SECRET_TOKEN"]:
        combined_env["SECRET_TOKEN"] = secret_env["SECRET_TOKEN"]
    
    logger.info(f"Combined environment variables: {list(combined_env.keys())}")
    
    # Example 4: Environment variables with filtering
    logger.info("\n=== Environment Variables with Tool Filtering ===")
    
    filter_agent = TinyAgent(
        model="gpt-4.1-mini",
        api_key=api_key,
        logger=logger
    )
    
    try:
        # Connect with environment variables and tool filtering
        filter_env = {
            "ENABLE_SEARCH": "true",
            "ENABLE_BOOKING": "false",
            "RATE_LIMIT": "50"
        }
        
        await filter_agent.connect_to_server(
            "npx", 
            ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"],
            env=filter_env,
            include_tools=["search", "list"],  # Only include search and list tools
            exclude_tools=["book", "payment"]  # Exclude booking and payment tools
        )
        logger.info("Connected with environment variables and tool filtering")
        
    except Exception as e:
        logger.error(f"Error in filtering example: {e}")
    finally:
        await filter_agent.close()
    
    logger.info("Environment Variables Example completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 