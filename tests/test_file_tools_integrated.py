"""
Test file tools integration with TinyCodeAgent.
"""

import asyncio
import os
import tempfile
import shutil
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock, AsyncMock

# Add the project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tinyagent.code_agent.tiny_code_agent import TinyCodeAgent
from tinyagent.hooks.logging_manager import LoggingManager


async def test_file_tools_through_agent():
    """Test file tools through TinyCodeAgent (proper integration)."""
    
    # Create temp directory for testing
    temp_dir = tempfile.mkdtemp()
    dummy_path = os.path.join(temp_dir, "dummy.txt")
    
    try:
        print("🧪 Testing file tools through TinyCodeAgent...")
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
        
        print("\n1️⃣ Testing write_file through agent...")
        
        # Create mock LLM response for write_file
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            # Create proper tool call object structure 
            tool_call_obj = MagicMock()
            tool_call_obj.id = "call_1"
            tool_call_obj.type = "function"
            tool_call_obj.function = MagicMock()
            tool_call_obj.function.name = "write_file"
            tool_call_obj.function.arguments = f'{{"file_path": "{dummy_path}", "content": "Hello, World!\\nThis is a test file."}}'
            
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll write to the file.",
                tool_calls=[tool_call_obj]
            ))])
            
            # Execute the agent
            result = await agent.run("Write 'Hello, World!' and 'This is a test file.' to dummy.txt")
            print(f"✅ Agent response: {result}")
            
            # Verify file was actually created and contains expected content
            if os.path.exists(dummy_path):
                with open(dummy_path, 'r') as f:
                    content = f.read()
                print(f"✅ File created with content: {repr(content)}")
                assert "Hello, World!" in content, "File should contain written content"
                return True
            else:
                print("❌ File was not created")
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


async def test_file_tools_current_directory_integration():
    """Test file tools in current directory through proper agent integration."""
    
    current_dir = os.getcwd()
    dummy_path = os.path.join(current_dir, "dummy.txt")
    
    try:
        print("\n🌍 Testing file tools in current directory through TinyCodeAgent...")
        print(f"📁 Current directory: {current_dir}")
        print(f"📄 Dummy file: {dummy_path}")
        
        # Create agent with file tools enabled
        log_manager = LoggingManager()
        agent = TinyCodeAgent(
            log_manager=log_manager,
            provider="modal",
            local_execution=True,
            enable_file_tools=True
        )
        
        print("\n1️⃣ Testing write_file in current directory...")
        
        # Create mock LLM response for write_file
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            # Create proper tool call object structure 
            tool_call_obj = MagicMock()
            tool_call_obj.id = "call_1"
            tool_call_obj.type = "function"
            tool_call_obj.function = MagicMock()
            tool_call_obj.function.name = "write_file"
            tool_call_obj.function.arguments = f'{{"file_path": "{dummy_path}", "content": "Test content from file tools\\nThis verifies file tools work out of the box!"}}'
            
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll write to the file.",
                tool_calls=[tool_call_obj]
            ))])
            
            # Execute the agent
            result = await agent.run("Write test content to dummy.txt in current directory")
            print(f"✅ Agent response: {result}")
            
            # Verify file was actually created and contains expected content
            if os.path.exists(dummy_path):
                with open(dummy_path, 'r') as f:
                    content = f.read()
                print(f"✅ File created successfully with content: {repr(content)}")
                assert "Test content" in content, "File should contain written content"
                
                print("\n2️⃣ Testing read_file in current directory...")
                
                # Create mock LLM response for read_file
                tool_call_obj2 = MagicMock()
                tool_call_obj2.id = "call_2"
                tool_call_obj2.type = "function"
                tool_call_obj2.function = MagicMock()
                tool_call_obj2.function.name = "read_file"
                tool_call_obj2.function.arguments = f'{{"file_path": "{dummy_path}"}}'
                
                mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                    content="I'll read the file.",
                    tool_calls=[tool_call_obj2]
                ))])
                
                result2 = await agent.run(f"Read the contents of {dummy_path}")
                print(f"✅ Read result: {result2}")
                assert "Test content" in str(result2), "Read should return file content"
                
                print("\n3️⃣ Testing update_file in current directory...")
                
                # Create mock LLM response for update_file
                tool_call_obj3 = MagicMock()
                tool_call_obj3.id = "call_3"
                tool_call_obj3.type = "function"
                tool_call_obj3.function = MagicMock()
                tool_call_obj3.function.name = "update_file"
                tool_call_obj3.function.arguments = f'{{"file_path": "{dummy_path}", "old_content": "Test content", "new_content": "Updated content"}}'
                
                mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                    content="I'll update the file.",
                    tool_calls=[tool_call_obj3]
                ))])
                
                result3 = await agent.run(f"In {dummy_path}, replace 'Test content' with 'Updated content'")
                print(f"✅ Update result: {result3}")
                
                # Verify file was updated
                with open(dummy_path, 'r') as f:
                    updated_content = f.read()
                assert "Updated content" in updated_content, "File should contain updated content"
                print(f"✅ File updated successfully with content: {repr(updated_content)}")
                
                print("\n🎉 File tools work out of the box in current directory!")
                return True
            else:
                print("❌ File was not created")
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
    """Run all integration tests."""
    print("🚀 Starting file tools integration tests...")
    
    # Test 1: Basic integration test
    test1_success = await test_file_tools_through_agent()
    
    # Test 2: Current directory integration test (real world scenario)
    test2_success = await test_file_tools_current_directory_integration()
    
    if test1_success and test2_success:
        print("\n✅ All integration tests passed! File tools are working correctly.")
        print("🎯 Definition of done: File tools work out-of-the-box in current directory ✓")
    else:
        print("\n❌ Some integration tests failed. File tools need fixing.")


if __name__ == "__main__":
    asyncio.run(main())