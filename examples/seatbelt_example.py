#!/usr/bin/env python3
"""
Example demonstrating TinyCodeAgent with the seatbelt provider for sandboxed execution.
This example shows how to use an existing seatbelt profile file and configure safety settings.
"""

import os
import asyncio
from tinyagent import tool
from tinyagent.code_agent import TinyCodeAgent
from tinyagent.hooks.logging_manager import LoggingManager
from typing import List, Dict, Any


async def main():
    # Check if seatbelt is supported on this system
    if not TinyCodeAgent.is_seatbelt_supported():
        print("⚠️  Seatbelt provider is not supported on this system.")
        print("    It requires macOS with sandbox-exec.")
        return
    
    print("🔒 Seatbelt provider is supported on this system.")
    
    # Set up logging
    log_manager = LoggingManager()
    
    # Example code tool - available in Python environment
    @tool(name="data_processor", description="Process data arrays")
    def data_processor(data: List[float]) -> Dict[str, Any]:
        """Process a list of numbers and return statistics."""
        return {
            "mean": sum(data) / len(data),
            "max": max(data),
            "min": min(data),
            "count": len(data)
        }
    
    # Path to seatbelt profile file
    # You can use the provided seatbelt.sb file or create your own
    current_dir = os.path.dirname(os.path.abspath(__file__))
    seatbelt_profile_path = os.path.join(current_dir, "..", "seatbelt.sb")
    
    # Check if the seatbelt profile file exists
    if not os.path.exists(seatbelt_profile_path):
        print(f"⚠️  Seatbelt profile file not found at: {seatbelt_profile_path}")
        print("    Creating a default seatbelt profile...")
        
        # Create a simple default profile
        seatbelt_profile = f"""(version 1)

; Default to deny everything
(deny default)

; Allow network connections with proper DNS resolution
(allow network*)
(allow network-outbound)
(allow mach-lookup)

; Allow process execution
(allow process-exec)
(allow process-fork)
(allow signal (target self))

; Restrict file read to current path and system files
(deny file-read* (subpath "/Users"))
(allow file-read*
  (subpath "{os.getcwd()}")
  (subpath "/usr")
  (subpath "/System")
  (subpath "/Library")
  (subpath "/bin")
  (subpath "/sbin")
  (subpath "/opt")
  (subpath "/private/tmp")
  (subpath "/private/var/tmp")
  (subpath "/dev")
  (subpath "/etc")
  (literal "/")
  (literal "/."))

; Allow write access to specified folder and temp directories
(deny file-write* (subpath "/"))
(allow file-write*
  (subpath "{os.getcwd()}")
  (subpath "/private/tmp")
  (subpath "/private/var/tmp")
  (subpath "/dev"))

; Allow standard device operations
(allow file-write-data
  (literal "/dev/null")
  (literal "/dev/dtracehelper")
  (literal "/dev/tty")
  (literal "/dev/stdout")
  (literal "/dev/stderr"))

; Allow iokit operations needed for system functions
(allow iokit-open)

; Allow shared memory operations
(allow ipc-posix-shm)

; Allow basic system operations
(allow file-read-metadata)
(allow process-info-pidinfo)
(allow process-info-setcontrol)
"""
        
        # Create the TinyCodeAgent with seatbelt provider using the profile string
        agent = TinyCodeAgent(
            model="gpt-4.1-mini",
            code_tools=[data_processor],
            user_variables={
                "sample_data": [1, 2, 3, 4, 5, 10, 15, 20]
            },
            provider="seatbelt",
            provider_config={
                "seatbelt_profile": seatbelt_profile,
                # Configure safety settings - more permissive than default
                "authorized_imports": ["*"],  # Allow all imports within the sandbox
                "authorized_functions": ["eval", "exec"],  # Allow potentially dangerous functions
                "check_string_obfuscation": False,  # Don't check for string obfuscation
                
                # Shell safety settings (already enabled by default for seatbelt, but shown here for clarity)
                "bypass_shell_safety": True,  # Bypass shell command safety checks
                "additional_safe_shell_commands": ["*"],  # Allow all shell commands
                # Or specify additional commands:
                # "additional_safe_shell_commands": ["npm", "node", "python", "pip", "git"],
                "additional_safe_control_operators": ["*"]  # Allow all control operators
            },
            local_execution=True,  # Required for seatbelt
            log_manager=log_manager,
            ui="rich"  # Use rich UI for better visualization
        )
    else:
        print(f"✅ Using seatbelt profile from: {seatbelt_profile_path}")
        
        # Optional: Path to Python environment
        # If you have a specific Python environment you want to use
        # For example, if you're using conda or virtualenv
        python_env_path = None
        
        # If you want to use the environment from sandbox_start.sh
        # Uncomment and adjust the path below
        # python_env_path = "/Users/username/miniconda3/envs/your_env_name"
        
        # Create the TinyCodeAgent with seatbelt provider using the profile file
        agent = TinyCodeAgent(
            model="gpt-4.1-mini",
            code_tools=[data_processor],
            user_variables={
                "sample_data": [1, 2, 3, 4, 5, 10, 15, 20]
            },
            provider="seatbelt",
            provider_config={
                "seatbelt_profile_path": seatbelt_profile_path,
                "python_env_path": python_env_path,
                # Configure safety settings - more permissive than default
                "authorized_imports": ["*"],  # Allow all imports within the sandbox
                "authorized_functions": ["eval", "exec"],  # Allow potentially dangerous functions
                "check_string_obfuscation": False,  # Don't check for string obfuscation
                
                # Shell safety settings (already enabled by default for seatbelt, but shown here for clarity)
                "bypass_shell_safety": True,  # Bypass shell command safety checks
                "additional_safe_shell_commands": ["*"],  # Allow all shell commands
                # Or specify additional commands:
                # "additional_safe_shell_commands": ["npm", "node", "python", "pip", "git"],
                "additional_safe_control_operators": ["*"]  # Allow all control operators
            },
            local_execution=True,  # Required for seatbelt
            log_manager=log_manager,
            ui="rich"  # Use rich UI for better visualization
        )
    
    # Connect to MCP servers
    await agent.connect_to_server("npx", ["-y", "@openbnb/mcp-server-airbnb", "--ignore-robots-txt"])
    await agent.connect_to_server("npx", ["-y", "@modelcontextprotocol/server-sequential-thinking"])
    
    # Run the agent with a test prompt
    response = await agent.run("""
    I have some sample data. Please use the data_processor tool in Python to analyze my sample_data
    and show me the results. Then, try to run a shell command to list the files in the current directory.
    """)
    
    print("\n" + "="*80)
    print("Agent Response:")
    print(response)
    
    # Demonstrate stateful execution by running another prompt that uses variables from the previous run
    print("\n" + "="*80)
    print("Testing stateful execution...")
    
    response2 = await agent.run("""
    Create a new variable called 'processed_data' that contains the sample_data with each value doubled.
    Then analyze this new data using the data_processor tool and compare the results with the previous analysis.
    """)
    
    print("\n" + "="*80)
    print("Agent Response (Stateful Execution):")
    print(response2)
    
    # Clean up
    await agent.close()


if __name__ == "__main__":
    asyncio.run(main()) 