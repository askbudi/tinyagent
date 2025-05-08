# tinyagent
Tiny Agent: 100 lines Agent with MCP

Inspired by:
- [Tiny Agents blog post](https://huggingface.co/blog/tiny-agents)
- [12-factor-agents repository](https://github.com/humanlayer/12-factor-agents)
- Created by chatting to the source code of JS Tiny Agent using [AskDev.ai](https://askdev.ai/search)

## Quick Links
- [Build your own Tiny Agent](https://askdev.ai/github/askbudi/tinyagent)

## Overview
This is a tiny agent that uses MCP and LiteLLM to interact with a model. You have full control over the agent, you can add any tools you like from MCP and extend the agent using its event system.

## Installation

### Using pip
```bash
pip install tinyagent-py
```

### Using uv
```bash
uv pip install tinyagent-py
```

## Usage

```python
from tinyagent import TinyAgent
from textwrap import dedent
import asyncio
import os

async def test_agent(task, model="o4-mini", api_key=None):
    # Initialize the agent with model and API key
    agent = TinyAgent(
        model=model,  # Or any model supported by LiteLLM
        api_key=os.environ.get("OPENAI_API_KEY") if not api_key else api_key  # Set your API key as an env variable
    )
    
    try:
        # Connect to an MCP server
        # Replace with your actual server command and args
        await agent.connect_to_server("npx", ["@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
        
        # Run the agent with a user query
        result = await agent.run(task)
        print("\nFinal result:", result)
        return result
    finally:
        # Clean up resources
        await agent.close()

# Example usage
task = dedent("""
I need accommodation in Toronto between 15th to 20th of May. Give me 5 options for 2 adults.
""")
await test_agent(task, model="gpt-4.1-mini")
```
