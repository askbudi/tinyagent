#!/usr/bin/env python3
"""
Environment Variables Example for TinyCodeAgent with SeatbeltProvider

This example demonstrates how to use environment variables with the SeatbeltProvider
to pass configuration and data to the sandboxed execution environment.
"""

import asyncio
import os
import tempfile
import shutil
from tinyagent.code_agent import TinyCodeAgent


async def run_environment_variables_example():
    """
    Example demonstrating environment variable functionality with SeatbeltProvider.
    """
    print("🔧 Environment Variables Example for TinyCodeAgent with SeatbeltProvider")
    print("="*80)
    
    # Check if seatbelt is supported
    if not TinyCodeAgent.is_seatbelt_supported():
        print("⚠️  SeatbeltProvider is not supported on this system. This example requires macOS.")
        return
    
    # Create temporary directories for testing
    test_dir = tempfile.mkdtemp(prefix='tinyagent_env_test_')
    test_read_dir = os.path.join(test_dir, "read_dir")
    test_write_dir = os.path.join(test_dir, "write_dir")
    
    os.makedirs(test_read_dir, exist_ok=True)
    os.makedirs(test_write_dir, exist_ok=True)
    
    # Create a test file in the read directory
    with open(os.path.join(test_read_dir, "config.txt"), "w") as f:
        f.write("database_host=localhost\ndatabase_port=5432\napi_timeout=30")
    
    try:
        # Create TinyCodeAgent with SeatbeltProvider and initial environment variables
        print("🚀 Creating TinyCodeAgent with SeatbeltProvider and environment variables...")
        
        agent = TinyCodeAgent(
            model="gpt-4.1-mini",
            provider="seatbelt",
            provider_config={
                "additional_read_dirs": [test_read_dir],
                "additional_write_dirs": [test_write_dir],
                "environment_variables": {
                    "APP_NAME": "TinyAgent Demo",
                    "VERSION": "1.0.0",
                    "CONFIG_DIR": test_read_dir,
                    "OUTPUT_DIR": test_write_dir,
                    "DEBUG_LEVEL": "INFO"
                }
            },
            local_execution=True,
            check_string_obfuscation=True
        )
        
        print("✅ Agent created successfully!")
        
        # Test 1: Basic environment variable access
        print("\n" + "="*80)
        print("📋 Test 1: Basic Environment Variable Access")
        
        response1 = await agent.run("""
        Test the initial environment variables:
        1. Print all environment variables that start with 'APP', 'VERSION', 'CONFIG', 'OUTPUT', or 'DEBUG'
        2. Use Python to access these variables using os.environ
        3. Use shell commands to echo these variables
        4. Verify that the paths in CONFIG_DIR and OUTPUT_DIR exist and are accessible
        """)
        print("Response:")
        print(response1)
        
        # Test 2: Adding environment variables dynamically
        print("\n" + "="*80)
        print("🔧 Test 2: Adding Environment Variables Dynamically")
        
        agent.add_environment_variable("DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb")
        agent.add_environment_variable("API_KEY", "secret_key_123")
        agent.add_environment_variable("FEATURE_FLAG_NEW_UI", "enabled")
        
        current_vars = agent.get_environment_variables()
        print(f"Current environment variables: {list(current_vars.keys())}")
        
        response2 = await agent.run("""
        Test the newly added environment variables:
        1. Access DATABASE_URL, API_KEY, and FEATURE_FLAG_NEW_UI
        2. Create a simple configuration parser that reads these values
        3. Write a small JSON config file to the OUTPUT_DIR using these values
        """)
        print("Response:")
        print(response2)
        
        # Test 3: Using environment variables for application configuration
        print("\n" + "="*80)
        print("⚙️ Test 3: Application Configuration via Environment Variables")
        
        response3 = await agent.run("""
        Create a configuration management system using environment variables:
        1. Read the config.txt file from CONFIG_DIR
        2. Parse the configuration values and combine them with environment variables
        3. Create a Python class that manages both file-based and environment-based configuration
        4. Demonstrate accessing configuration values with fallbacks
        5. Write the final configuration to OUTPUT_DIR as both JSON and YAML formats
        """)
        print("Response:")
        print(response3)
        
        # Test 4: Updating environment variables in bulk
        print("\n" + "="*80)
        print("🔄 Test 4: Bulk Environment Variable Updates")
        
        # Update multiple environment variables at once
        agent.set_environment_variables({
            "APP_NAME": "TinyAgent Advanced Demo",
            "VERSION": "2.0.0",
            "DEBUG_LEVEL": "DEBUG",
            "NEW_FEATURE": "experimental",
            "CACHE_TTL": "3600",
            "MAX_CONNECTIONS": "100"
        })
        
        response4 = await agent.run("""
        Test the updated environment variables:
        1. Verify that APP_NAME and VERSION have been updated
        2. Check that DEBUG_LEVEL is now 'DEBUG'
        3. Access the new variables: NEW_FEATURE, CACHE_TTL, MAX_CONNECTIONS
        4. Note: DATABASE_URL and API_KEY should no longer be available (removed by set operation)
        5. Create a system status report using these environment variables
        """)
        print("Response:")
        print(response4)
        
        # Test 5: Environment variable security and isolation
        print("\n" + "="*80)
        print("🔒 Test 5: Environment Variable Security and Isolation")
        
        response5 = await agent.run("""
        Test environment variable security and isolation:
        1. Try to access system environment variables like HOME, USER, PATH
        2. Verify that our custom environment variables are properly isolated
        3. Test that sensitive system variables are not accessible or are properly sandboxed
        4. Create a security report showing which environment variables are available
        """)
        print("Response:")
        print(response5)
        
        # Test 6: Removing specific environment variables
        print("\n" + "="*80)
        print("🗑️ Test 6: Removing Environment Variables")
        
        agent.remove_environment_variable("NEW_FEATURE")
        agent.remove_environment_variable("CACHE_TTL")
        
        final_vars = agent.get_environment_variables()
        print(f"Final environment variables: {list(final_vars.keys())}")
        
        response6 = await agent.run("""
        Test that specific environment variables have been removed:
        1. Verify that NEW_FEATURE and CACHE_TTL are no longer available
        2. Confirm that other variables like APP_NAME, VERSION are still accessible
        3. Create a final configuration summary with remaining variables
        4. Write the final state to OUTPUT_DIR for verification
        """)
        print("Response:")
        print(response6)
        
        # Final verification
        print("\n" + "="*80)
        print("🎯 Final Verification")
        
        # List files created in the output directory
        output_files = os.listdir(test_write_dir)
        print(f"Files created in output directory: {output_files}")
        
        # Show final environment variables
        final_env_vars = agent.get_environment_variables()
        print(f"Final environment variables: {final_env_vars}")
        
        await agent.close()
        print("\n✅ Environment Variables Example completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during example execution: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up temporary directories
        try:
            shutil.rmtree(test_dir)
            print(f"🧹 Cleaned up temporary directory: {test_dir}")
        except Exception as e:
            print(f"⚠️ Warning: Failed to clean up temporary directory: {str(e)}")


if __name__ == "__main__":
    asyncio.run(run_environment_variables_example()) 