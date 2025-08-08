#!/usr/bin/env python3
"""
Tests for TinyAgent file manipulation tools.
"""

import asyncio
import logging
import sys
import tempfile
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def test_file_tools():
    """Test file manipulation tools with TinyCodeAgent."""
    logger.info("=== Testing File Manipulation Tools ===")
    
    try:
        from tinyagent.code_agent import TinyCodeAgent
        
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Using temporary directory: {temp_dir}")
            
            # Create TinyCodeAgent with file tools enabled
            agent = TinyCodeAgent(
                model="gpt-4o-mini",
                provider="modal",
                local_execution=True,
                enable_file_tools=True,
                enable_python_tool=False,  # Disable to focus on file tools
                enable_shell_tool=False,   # Disable to focus on file tools
                system_prompt="You are a helpful assistant with file manipulation capabilities."
            )
            logger.info("✅ Created TinyCodeAgent with file tools enabled")
            
            # Test 1: Write a file
            logger.info("=== Test 1: Write File ===")
            test_file = os.path.join(temp_dir, "test.txt")
            result = await agent.run(f'Use the write_file tool to create {test_file} with content: print("Hello, World!")')
            logger.info(f"Write result: {result}")
            
            # Verify file was created
            if os.path.exists(test_file):
                logger.info("✅ File was created successfully")
                with open(test_file, 'r') as f:
                    content = f.read()
                    logger.info(f"File content: {content}")
            else:
                logger.error("❌ File was not created")
                return False
            
            # Test 2: Read the file back
            logger.info("=== Test 2: Read File ===")
            result = await agent.run(f"Use the read_file tool to read {test_file}")
            logger.info(f"Read result: {result}")
            
            # Test 3: Update the file
            logger.info("=== Test 3: Update File ===")
            result = await agent.run(f'Use the update_file tool to change "Hello" to "Hi" in {test_file}')
            logger.info(f"Update result: {result}")
            
            # Verify update worked
            with open(test_file, 'r') as f:
                updated_content = f.read()
                if "Hi" in updated_content:
                    logger.info("✅ File was updated successfully")
                    logger.info(f"Updated content: {updated_content}")
                else:
                    logger.error("❌ File update failed")
                    logger.error(f"Content after update: {updated_content}")
                    return False
            
            # Test 4: Create another file for search
            logger.info("=== Test 4: Search Files ===")
            test_file2 = os.path.join(temp_dir, "config.py")
            result = await agent.run(f'Use the write_file tool to create {test_file2} with content: DEBUG = True\\nDATABASE_URL = "sqlite:///test.db"\\nSECRET_KEY = "test-key"')
            logger.info(f"Config file creation result: {result}")
            
            result = await agent.run(f'Use the search_files tool to find files containing "DEBUG" in directory {temp_dir}')
            logger.info(f"Search result: {result}")
            
            # Test 5: Error handling - try to read non-existent file
            logger.info("=== Test 5: Error Handling ===")
            result = await agent.run(f"Use the read_file tool to read {temp_dir}/nonexistent.txt")
            logger.info(f"Error handling result: {result}")
            
            # Test 6: Test binary file detection
            logger.info("=== Test 6: Binary File Detection ===")
            binary_file = os.path.join(temp_dir, "test.bin")
            # Create a binary file
            with open(binary_file, 'wb') as f:
                f.write(b'\x00\x01\x02\x03\x04\x05')
            result = await agent.run(f"Use the read_file tool to read {binary_file}")
            logger.info(f"Binary file read result: {result}")
            
            # Test 7: Test directory handling
            logger.info("=== Test 7: Directory Handling ===")
            result = await agent.run(f"Use the read_file tool to read {temp_dir}")
            logger.info(f"Directory read result: {result}")
            
            logger.info("🎉 All file tool tests completed successfully!")
            return True
            
    except Exception as e:
        logger.error(f"File tools test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_file_tools())
    print(f"\nFile Tools Test {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)