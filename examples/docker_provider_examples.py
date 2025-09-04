#!/usr/bin/env python3
"""
Docker Provider Examples for TinyAgent

This script demonstrates various usage patterns and configurations 
for the DockerProvider in TinyAgent.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from tinyagent import TinyAgent
from tinyagent.code_agent import TinyCodeAgent
from tinyagent.hooks.logging_manager import LoggingManager


async def example_basic_docker_usage():
    """
    Basic example using DockerProvider with automatic provider selection.
    Docker will be used as a fallback if no native sandbox is available.
    """
    print("=" * 60)
    print("EXAMPLE 1: Basic Docker Provider Usage")
    print("=" * 60)
    
    # Create agent with automatic provider selection
    # Docker will be selected if available and no native sandbox exists
    agent = TinyCodeAgent(
        model="gpt-4o-mini",  # Use a fast model for examples
        local_execution=True,  # Force local execution to prefer Docker over Modal
        provider="docker",     # Explicitly request Docker provider
    )
    
    # Simple Python execution
    response = await agent.run_async(
        "Calculate the factorial of 10 and display the result."
    )
    print("Agent Response:")
    print(response)
    
    await agent.cleanup()


async def example_docker_with_custom_image():
    """
    Example using Docker with a custom image and configuration.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Docker with Custom Configuration")
    print("=" * 60)
    
    # Docker-specific configuration
    docker_config = {
        "docker_image": "tinyagent-runtime:latest",  # Use optimized image
        "enable_network": True,     # Enable network access
        "memory_limit": "1g",       # Increase memory limit
        "cpu_limit": "2.0",         # Allow more CPU usage
        "timeout": 300,             # 5-minute timeout
        "auto_pull_image": True,    # Automatically pull image if missing
    }
    
    agent = TinyCodeAgent(
        model="gpt-4o-mini",
        provider="docker",
        provider_config=docker_config,
    )
    
    # Task that benefits from network access and more resources
    response = await agent.run_async(
        """
        Download data about Python package statistics and create a simple visualization.
        Use requests to fetch data from https://pypi.org/pypi/requests/json and 
        create a bar chart showing the recent downloads.
        """
    )
    print("Agent Response:")
    print(response)
    
    await agent.cleanup()


async def example_docker_with_environment_variables():
    """
    Example using Docker with custom environment variables.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Docker with Environment Variables")
    print("=" * 60)
    
    # Docker configuration with environment variables
    docker_config = {
        "environment_variables": {
            "API_URL": "https://api.example.com",
            "DEBUG": "true",
            "CUSTOM_PATH": "/opt/custom",
        },
        "enable_network": True,
    }
    
    agent = TinyCodeAgent(
        model="gpt-4o-mini",
        provider="docker",
        provider_config=docker_config,
    )
    
    response = await agent.run_async(
        """
        Read the environment variables API_URL, DEBUG, and CUSTOM_PATH and 
        print their values. Also show all environment variables that start with 'PYTHON'.
        """
    )
    print("Agent Response:")
    print(response)
    
    await agent.cleanup()


async def example_docker_with_volume_mounts():
    """
    Example using Docker with additional volume mounts for file access.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Docker with Volume Mounts")
    print("=" * 60)
    
    # Create temporary directories for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        data_dir = os.path.join(temp_dir, "data")
        output_dir = os.path.join(temp_dir, "output")
        os.makedirs(data_dir)
        os.makedirs(output_dir)
        
        # Create some test data
        test_file = os.path.join(data_dir, "test_data.txt")
        with open(test_file, 'w') as f:
            f.write("Sample data for processing\n" * 100)
        
        # Docker configuration with volume mounts
        docker_config = {
            "additional_read_dirs": [data_dir],     # Read-only access to data
            "additional_write_dirs": [output_dir],  # Write access to output
        }
        
        agent = TinyCodeAgent(
            model="gpt-4o-mini",
            provider="docker",
            provider_config=docker_config,
        )
        
        response = await agent.run_async(
            f"""
            Read the file from {test_file} and process it:
            1. Count the number of lines
            2. Count the number of words
            3. Save a summary to {output_dir}/summary.txt
            4. Display the summary
            """
        )
        print("Agent Response:")
        print(response)
        
        # Check if output file was created
        summary_file = os.path.join(output_dir, "summary.txt")
        if os.path.exists(summary_file):
            print(f"\nOutput file created: {summary_file}")
            with open(summary_file, 'r') as f:
                print("Summary contents:")
                print(f.read())
    
    await agent.cleanup()


async def example_docker_with_git_operations():
    """
    Example using Docker for git operations with credentials.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Docker with Git Operations")
    print("=" * 60)
    
    # Docker configuration with git credentials
    docker_config = {
        "enable_network": True,  # Required for git operations
        "environment_variables": {
            "GIT_AUTHOR_NAME": "TinyAgent",
            "GIT_AUTHOR_EMAIL": "tinyagent@example.com",
            # "GITHUB_TOKEN": "your_token_here",  # Uncomment and set for private repos
            # "GITHUB_USERNAME": "your_username",
        },
    }
    
    agent = TinyCodeAgent(
        model="gpt-4o-mini",
        provider="docker",
        provider_config=docker_config,
        enable_shell_tool=True,  # Enable shell commands for git
    )
    
    response = await agent.run_async(
        """
        Demonstrate git operations:
        1. Initialize a new git repository
        2. Create a simple README.md file
        3. Add and commit the file
        4. Show the git log
        5. Show the current git status
        """
    )
    print("Agent Response:")
    print(response)
    
    await agent.cleanup()


async def example_docker_security_features():
    """
    Example demonstrating Docker security features and limitations.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Docker Security Features")
    print("=" * 60)
    
    # Docker configuration with security settings
    docker_config = {
        "enable_network": False,    # Network isolation
        "memory_limit": "256m",     # Memory limit
        "cpu_limit": "0.5",         # CPU limit
        "timeout": 30,              # Short timeout
        "bypass_shell_safety": False,  # Enable shell command filtering
    }
    
    agent = TinyCodeAgent(
        model="gpt-4o-mini",
        provider="docker",
        provider_config=docker_config,
        check_string_obfuscation=True,  # Enable code safety checks
    )
    
    # Test various security aspects
    tasks = [
        "Try to access the filesystem outside the container (should be limited)",
        "Attempt to use network (should fail due to network isolation)",
        "Try to consume excessive resources (should be limited)",
        "Show the current user and permissions",
        "List available system commands",
    ]
    
    for i, task in enumerate(tasks, 1):
        print(f"\nSecurity Test {i}: {task}")
        try:
            response = await agent.run_async(task)
            print("Response:", response.strip()[:200] + "..." if len(response) > 200 else response)
        except Exception as e:
            print(f"Exception (expected for security): {e}")
    
    await agent.cleanup()


async def example_docker_performance_comparison():
    """
    Example comparing Docker provider performance with different configurations.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 7: Docker Performance Comparison")
    print("=" * 60)
    
    import time
    
    # Test task
    test_task = """
    import numpy as np
    import pandas as pd
    
    # Create some test data
    data = np.random.rand(1000, 10)
    df = pd.DataFrame(data)
    
    # Perform some operations
    result = df.mean().sum()
    print(f"Result: {result}")
    """
    
    # Configuration 1: Minimal resources
    config_minimal = {
        "memory_limit": "128m",
        "cpu_limit": "0.5",
        "auto_pull_image": False,
    }
    
    # Configuration 2: More resources
    config_generous = {
        "memory_limit": "512m", 
        "cpu_limit": "2.0",
        "auto_pull_image": False,
    }
    
    for config_name, config in [("Minimal", config_minimal), ("Generous", config_generous)]:
        print(f"\nTesting {config_name} Configuration:")
        print(f"Memory: {config['memory_limit']}, CPU: {config['cpu_limit']}")
        
        agent = TinyCodeAgent(
            model="gpt-4o-mini",
            provider="docker",
            provider_config=config,
        )
        
        start_time = time.time()
        response = await agent.run_async(test_task)
        end_time = time.time()
        
        print(f"Execution time: {end_time - start_time:.2f} seconds")
        print("Response:", response.strip()[:100] + "..." if len(response) > 100 else response)
        
        await agent.cleanup()


async def example_docker_error_handling():
    """
    Example demonstrating error handling with Docker provider.
    """
    print("\n" + "=" * 60)
    print("EXAMPLE 8: Docker Error Handling")
    print("=" * 60)
    
    agent = TinyCodeAgent(
        model="gpt-4o-mini",
        provider="docker",
        provider_config={"timeout": 10},  # Short timeout for testing
    )
    
    # Test various error conditions
    error_tests = [
        ("Syntax Error", "print('missing quote"),
        ("Runtime Error", "raise ValueError('Test error')"),
        ("Import Error", "import nonexistent_module"),
        ("Timeout Error", "import time; time.sleep(15)"),  # Should timeout at 10 seconds
    ]
    
    for test_name, test_code in error_tests:
        print(f"\nTesting {test_name}:")
        response = await agent.run_async(f"Execute this code: {test_code}")
        
        if "error" in response.lower() or "traceback" in response.lower():
            print("✓ Error properly handled")
            print("Error details:", response.strip()[:200] + "..." if len(response) > 200 else response)
        else:
            print("✗ Error not detected")
            print("Response:", response)
    
    await agent.cleanup()


async def main():
    """
    Run all Docker provider examples.
    """
    print("TinyAgent Docker Provider Examples")
    print("=" * 60)
    
    # Check if Docker is available
    from tinyagent.code_agent.providers.docker_provider import DockerProvider
    if not DockerProvider.is_supported():
        print("❌ Docker is not available on this system.")
        print("Please install Docker and ensure it's running to run these examples.")
        return
    
    print("✅ Docker is available. Running examples...\n")
    
    # Run all examples
    examples = [
        example_basic_docker_usage,
        example_docker_with_custom_image,
        example_docker_with_environment_variables,
        example_docker_with_volume_mounts,
        example_docker_with_git_operations,
        example_docker_security_features,
        example_docker_performance_comparison,
        example_docker_error_handling,
    ]
    
    for i, example in enumerate(examples, 1):
        try:
            print(f"\n{'='*20} RUNNING EXAMPLE {i} {'='*20}")
            await example()
        except KeyboardInterrupt:
            print("\n❌ Interrupted by user")
            break
        except Exception as e:
            print(f"❌ Example {i} failed with error: {e}")
            import traceback
            traceback.print_exc()
        
        # Small delay between examples
        await asyncio.sleep(1)
    
    print("\n" + "=" * 60)
    print("All Docker provider examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())