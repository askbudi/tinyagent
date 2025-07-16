#!/usr/bin/env python3
"""
Git Checkpoint Example

This example demonstrates how to use the automatic git checkpoint feature
in TinyCodeAgent to track changes made by shell commands.
"""

import os
import asyncio
from tinyagent import TinyCodeAgent
from textwrap import dedent

async def run_example():
    """
    Example demonstrating TinyCodeAgent's automatic git checkpoint feature.
    """
    print("🚀 Testing TinyCodeAgent with automatic git checkpoints")
    
    # Create TinyCodeAgent with auto_git_checkpoint enabled
    agent = TinyCodeAgent(
        model="gpt-4.1-mini",
        auto_git_checkpoint=True,  # Enable automatic git checkpoints
        local_execution=True,      # Use local execution for this example
        default_workdir=os.getcwd()  # Use current directory as working directory
    )
    
    # Connect to MCP servers
    await agent.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    try:
        # Create a test directory for our example
        test_dir = os.path.join(os.getcwd(), "git_checkpoint_test")
        os.makedirs(test_dir, exist_ok=True)
        
        # Set the working directory to our test directory
        agent.set_default_workdir(test_dir)
        
        # Initialize a git repository in the test directory
        print("\n" + "="*80)
        print("🔄 Step 1: Initialize a git repository")
        
        init_prompt = """
        Initialize a new git repository in the current directory.
        Configure git user name as 'TinyAgent' and email as 'tinyagent@example.com'.
        """
        
        response = await agent.run(init_prompt)
        print(response)
        
        # Create a new file
        print("\n" + "="*80)
        print("🔄 Step 2: Create a new file")
        
        file_prompt = """
        Create a new Python file called 'hello.py' with a simple 'Hello, World!' program.
        """
        
        response = await agent.run(file_prompt)
        print(response)
        
        # Modify the file
        print("\n" + "="*80)
        print("🔄 Step 3: Modify the file")
        
        modify_prompt = """
        Modify the 'hello.py' file to add a function that prints the current date and time.
        """
        
        response = await agent.run(modify_prompt)
        print(response)
        
        # Check git history
        print("\n" + "="*80)
        print("🔄 Step 4: Check git history")
        
        history_prompt = """
        Show the git commit history to see the automatic checkpoints that were created.
        """
        
        response = await agent.run(history_prompt)
        print(response)
        
        # Disable git checkpoints and make another change
        print("\n" + "="*80)
        print("🔄 Step 5: Disable git checkpoints and make another change")
        
        # Disable automatic git checkpoints
        agent.enable_auto_git_checkpoint(False)
        print(f"Auto Git Checkpoint disabled: {agent.get_auto_git_checkpoint_status()}")
        
        disable_prompt = """
        Add a new function to 'hello.py' that prints a random number between 1 and 100.
        Then check if a new git checkpoint was created (it shouldn't be since we disabled the feature).
        """
        
        response = await agent.run(disable_prompt)
        print(response)
        
        # Re-enable git checkpoints and make another change
        print("\n" + "="*80)
        print("🔄 Step 6: Re-enable git checkpoints and make another change")
        
        # Re-enable automatic git checkpoints
        agent.enable_auto_git_checkpoint(True)
        print(f"Auto Git Checkpoint enabled: {agent.get_auto_git_checkpoint_status()}")
        
        enable_prompt = """
        Add a new function to 'hello.py' that prints the multiplication table for a given number.
        Then check if a new git checkpoint was created (it should be since we re-enabled the feature).
        """
        
        response = await agent.run(enable_prompt)
        print(response)
        
        print("\n" + "="*80)
        print("✅ Example completed successfully!")
        print("The git_checkpoint_test directory contains a git repository with automatic checkpoints.")
        print("You can explore it to see how the automatic git checkpoints work.")
        
    finally:
        # Clean up resources
        await agent.close()
        
        # Optionally, clean up the test directory
        # import shutil
        # shutil.rmtree(test_dir)

if __name__ == "__main__":
    asyncio.run(run_example()) 