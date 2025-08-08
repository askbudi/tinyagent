"""
Direct test of file tools with actual provider to verify core functionality.
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

from tinyagent.code_agent.providers.modal_provider import ModalProvider
from tinyagent.hooks.logging_manager import LoggingManager


async def test_provider_file_operations_directly():
    """Test provider file operations directly to verify they work."""
    
    # Create temp directory for testing
    temp_dir = tempfile.mkdtemp()
    dummy_path = os.path.join(temp_dir, "dummy.txt")
    
    try:
        print("🧪 Testing provider file operations directly...")
        print(f"📁 Test directory: {temp_dir}")
        print(f"📄 Dummy file: {dummy_path}")
        
        # Create provider with local execution
        log_manager = LoggingManager()
        provider = ModalProvider(log_manager=log_manager, local_execution=True)
        
        print("\n1️⃣ Testing provider write_file...")
        write_result = await provider.write_file(dummy_path, "Hello, World!\nThis is a test file.")
        print(f"✅ Write result: {write_result}")
        
        if write_result.get("success"):
            # Verify file exists and has correct content
            assert os.path.exists(dummy_path), "File should exist after write"
            with open(dummy_path, 'r') as f:
                content = f.read()
            assert "Hello, World!" in content, "File should contain written content"
            print(f"✅ File created with content: {repr(content)}")
            
            print("\n2️⃣ Testing provider read_file...")
            read_result = await provider.read_file(dummy_path)
            print(f"✅ Read result: {read_result}")
            assert read_result.get("success"), "Read should succeed"
            assert "Hello, World!" in read_result.get("content", ""), "Read should return file content"
            
            print("\n3️⃣ Testing provider update_file...")
            update_result = await provider.update_file(dummy_path, "Hello, World!", "Hello, TinyAgent!")
            print(f"✅ Update result: {update_result}")
            
            if update_result.get("success"):
                # Verify file was updated
                with open(dummy_path, 'r') as f:
                    updated_content = f.read()
                assert "Hello, TinyAgent!" in updated_content, "File should contain updated content"
                assert "Hello, World!" not in updated_content, "Old content should be replaced"
                print(f"✅ File updated with content: {repr(updated_content)}")
            
            print("\n4️⃣ Testing provider search_files...")
            search_result = await provider.search_files("TinyAgent", temp_dir)
            print(f"✅ Search result: {search_result}")
            assert search_result.get("success"), "Search should succeed"
            
            print("\n🎉 All provider file operations work correctly!")
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


async def test_provider_current_directory():
    """Test provider file operations in current directory."""
    
    current_dir = os.getcwd()
    dummy_path = os.path.join(current_dir, "dummy.txt")
    
    try:
        print("\n🌍 Testing provider file operations in current directory...")
        print(f"📁 Current directory: {current_dir}")
        print(f"📄 Dummy file: {dummy_path}")
        
        # Create provider with local execution
        log_manager = LoggingManager()
        provider = ModalProvider(log_manager=log_manager, local_execution=True)
        
        print("\n1️⃣ Testing provider write_file in current directory...")
        write_result = await provider.write_file(dummy_path, "Test content from file tools\nThis verifies file tools work out of the box!")
        print(f"✅ Write result: {write_result}")
        
        if write_result.get("success"):
            # Verify file exists and has correct content
            assert os.path.exists(dummy_path), "File should exist after write"
            with open(dummy_path, 'r') as f:
                content = f.read()
            assert "Test content" in content, "File should contain written content"
            print(f"✅ File created successfully with content: {repr(content)}")
            
            print("\n2️⃣ Testing provider read_file in current directory...")
            read_result = await provider.read_file(dummy_path)
            print(f"✅ Read result: {read_result}")
            assert read_result.get("success"), "Read should succeed"
            assert "Test content" in read_result.get("content", ""), "Read should return file content"
            
            print("\n🎉 Provider file operations work out of the box in current directory!")
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


async def main():
    """Run all direct provider tests."""
    print("🚀 Starting direct provider file operations tests...")
    
    # Test 1: Direct provider testing
    test1_success = await test_provider_file_operations_directly()
    
    # Test 2: Current directory provider testing (real world scenario)
    test2_success = await test_provider_current_directory()
    
    if test1_success and test2_success:
        print("\n✅ All direct provider tests passed! File operations work at the provider level.")
        print("🎯 Core file operations are functional ✓")
    else:
        print("\n❌ Some direct provider tests failed. File operations need fixing at the provider level.")


if __name__ == "__main__":
    asyncio.run(main())