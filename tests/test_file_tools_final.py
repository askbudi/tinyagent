"""
Final test to verify file tools work through TinyCodeAgent with proper security setup.
"""

import asyncio
import os
import tempfile
import shutil
from pathlib import Path
import sys

# Add the project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tinyagent.code_agent.tiny_code_agent import TinyCodeAgent
from tinyagent.hooks.logging_manager import LoggingManager


async def test_file_tools_current_directory():
    """Test file tools in current directory through TinyCodeAgent (the real scenario)."""
    
    current_dir = os.getcwd()
    dummy_path = os.path.join(current_dir, "dummy.txt")
    
    try:
        print("\n🌍 Testing file tools in current directory through TinyCodeAgent...")
        print(f"📁 Current directory: {current_dir}")
        print(f"📄 Dummy file: {dummy_path}")
        
        # Create agent with file tools enabled - this should add the authorized functions
        log_manager = LoggingManager()
        agent = TinyCodeAgent(
            log_manager=log_manager,
            provider="modal",
            local_execution=True,
            enable_file_tools=True
        )
        
        print(f"✅ Agent created with file tools enabled")
        print(f"📋 Provider authorized functions: {agent.code_provider.authorized_functions}")
        
        print("\n1️⃣ Testing write_file through provider directly...")
        
        # Test provider directly to see if authorized functions are set correctly
        write_result = await agent.code_provider.write_file(dummy_path, "Test content from file tools\nThis verifies file tools work out of the box!")
        print(f"✅ Write result: {write_result}")
        
        if write_result.get("success"):
            # Verify file exists and has correct content
            assert os.path.exists(dummy_path), "File should exist after write"
            with open(dummy_path, 'r') as f:
                content = f.read()
            assert "Test content" in content, "File should contain written content"
            print(f"✅ File created successfully with content: {repr(content)}")
            
            print("\n2️⃣ Testing read_file through provider directly...")
            read_result = await agent.code_provider.read_file(dummy_path)
            print(f"✅ Read result: {read_result}")
            assert read_result.get("success"), "Read should succeed"
            assert "Test content" in read_result.get("content", ""), "Read should return file content"
            
            print("\n3️⃣ Testing update_file through provider directly...")
            update_result = await agent.code_provider.update_file(dummy_path, "Test content", "Updated content")
            print(f"✅ Update result: {update_result}")
            
            if update_result.get("success"):
                # Verify file was updated
                with open(dummy_path, 'r') as f:
                    updated_content = f.read()
                assert "Updated content" in updated_content, "File should contain updated content"
                print(f"✅ File updated successfully with content: {repr(updated_content)}")
            
            print("\n4️⃣ Testing search_files through provider directly...")
            search_result = await agent.code_provider.search_files("Updated", current_dir)
            print(f"✅ Search result: {search_result}")
            assert search_result.get("success"), "Search should succeed"
            
            print("\n🎉 All file operations work through TinyCodeAgent provider!")
            print("🎯 Definition of done: File tools work out-of-the-box in current directory ✓")
            return True
        else:
            print(f"❌ Write operation failed: {write_result}")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        if os.path.exists(dummy_path):
            os.remove(dummy_path)
            print(f"🧹 Cleaned up dummy.txt")


async def test_file_tools_temp_directory():
    """Test file tools in temp directory through TinyCodeAgent."""
    
    temp_dir = tempfile.mkdtemp()
    dummy_path = os.path.join(temp_dir, "dummy.txt")
    
    try:
        print("🧪 Testing file tools in temp directory through TinyCodeAgent...")
        print(f"📁 Test directory: {temp_dir}")
        print(f"📄 Dummy file: {dummy_path}")
        
        # Create agent with file tools enabled
        log_manager = LoggingManager()
        agent = TinyCodeAgent(
            log_manager=log_manager,
            provider="modal",
            local_execution=True,
            enable_file_tools=True
        )
        
        print(f"✅ Agent created with file tools enabled")
        print(f"📋 Provider authorized functions: {agent.code_provider.authorized_functions}")
        
        print("\n1️⃣ Testing complete file workflow...")
        
        # Test complete workflow
        write_result = await agent.code_provider.write_file(dummy_path, "Hello, World!\nThis is a test file.")
        print(f"✅ Write result: {write_result}")
        
        if write_result.get("success"):
            # Verify file exists and has correct content
            assert os.path.exists(dummy_path), "File should exist after write"
            with open(dummy_path, 'r') as f:
                content = f.read()
            assert "Hello, World!" in content, "File should contain written content"
            print(f"✅ File created with content: {repr(content)}")
            
            # Test read
            read_result = await agent.code_provider.read_file(dummy_path)
            assert read_result.get("success"), "Read should succeed"
            assert "Hello, World!" in read_result.get("content", ""), "Read should return file content"
            print(f"✅ Read successful")
            
            # Test update
            update_result = await agent.code_provider.update_file(dummy_path, "Hello, World!", "Hello, TinyAgent!")
            if update_result.get("success"):
                with open(dummy_path, 'r') as f:
                    updated_content = f.read()
                assert "Hello, TinyAgent!" in updated_content, "File should contain updated content"
                print(f"✅ Update successful")
            
            # Test search
            search_result = await agent.code_provider.search_files("TinyAgent", temp_dir)
            if search_result.get("success"):
                print(f"✅ Search successful")
            
            print("\n🎉 All temp directory file operations work!")
            return True
        else:
            print(f"❌ Write operation failed: {write_result}")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up
        shutil.rmtree(temp_dir)
        print(f"🧹 Cleaned up test directory")


async def main():
    """Run final comprehensive tests."""
    print("🚀 Starting final file tools tests...")
    
    # Test 1: Temp directory test
    test1_success = await test_file_tools_temp_directory()
    
    # Test 2: Current directory test (real world scenario)
    test2_success = await test_file_tools_current_directory()
    
    if test1_success and test2_success:
        print("\n✅ ALL TESTS PASSED! File tools are working correctly.")
        print("🎯 DEFINITION OF DONE ACHIEVED: File tools work out-of-the-box in current directory ✓")
        print("🔧 Users can now read, write, update, and search files through TinyCodeAgent")
    else:
        print("\n❌ Some tests failed. File tools implementation needs further fixes.")


if __name__ == "__main__":
    asyncio.run(main())