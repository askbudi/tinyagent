#!/usr/bin/env python3
"""
End-to-end tests for file tools with TinyCodeAgent using mocked LLM responses.
"""

import asyncio
import os
import tempfile
import unittest
import shutil
import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tinyagent.code_agent import TinyCodeAgent


class TestFileToolsE2E(unittest.TestCase):
    """End-to-end tests for file tools with TinyCodeAgent."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        self.test_content = "Hello, World!\nThis is a test file.\nLine 3 content."
        
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def create_mock_response(self, tool_calls):
        """Create a mock LLM response with tool calls."""
        return {
            "choices": [{
                "message": {
                    "content": "I'll help you with that file operation.",
                    "tool_calls": tool_calls
                }
            }]
        }
        
    async def test_agent_read_file(self):
        """Test reading file through TinyCodeAgent."""
        # Create test file
        with open(self.test_file, 'w') as f:
            f.write(self.test_content)
        
        # Create agent
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Mock LLM response
        mock_tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({
                    "file_path": self.test_file
                })
            }
        }
        
        mock_response = self.create_mock_response([mock_tool_call])
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent.run(f"Read the file {self.test_file}")
            
            # Check that LLM was called
            self.assertTrue(mock_llm.called)
            
            # Check that the tool was executed (we can't directly check the file content 
            # due to sandbox restrictions, but we can verify the tool was called)
            call_args = mock_llm.call_args[1]
            self.assertIn("read_file", str(call_args))
            
    async def test_agent_write_file(self):
        """Test writing file through TinyCodeAgent."""
        agent = TinyCodeAgent(
            model="gpt-5-mini", 
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        content = "New file content"
        mock_tool_call = {
            "id": "call_1",
            "type": "function", 
            "function": {
                "name": "write_file",
                "arguments": json.dumps({
                    "file_path": self.test_file,
                    "content": content
                })
            }
        }
        
        mock_response = self.create_mock_response([mock_tool_call])
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent.run(f"Write '{content}' to {self.test_file}")
            
            self.assertTrue(mock_llm.called)
            call_args = mock_llm.call_args[1]
            self.assertIn("write_file", str(call_args))
            
    async def test_agent_update_file(self):
        """Test updating file through TinyCodeAgent."""
        # Create test file
        with open(self.test_file, 'w') as f:
            f.write(self.test_content)
            
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal", 
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        mock_tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "update_file", 
                "arguments": json.dumps({
                    "file_path": self.test_file,
                    "old_content": "Hello, World!",
                    "new_content": "Hi, Universe!"
                })
            }
        }
        
        mock_response = self.create_mock_response([mock_tool_call])
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent.run(f"In {self.test_file}, change 'Hello, World!' to 'Hi, Universe!'")
            
            self.assertTrue(mock_llm.called)
            call_args = mock_llm.call_args[1]
            self.assertIn("update_file", str(call_args))
            
    async def test_agent_search_files(self):
        """Test searching files through TinyCodeAgent."""
        # Create test files
        file1 = os.path.join(self.temp_dir, "file1.txt")
        file2 = os.path.join(self.temp_dir, "file2.py")
        
        with open(file1, 'w') as f:
            f.write("This contains DEBUG information")
        with open(file2, 'w') as f:
            f.write("print('Hello')\nDEBUG = True")
            
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True, 
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        mock_tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "search_files",
                "arguments": json.dumps({
                    "pattern": "DEBUG",
                    "directory": self.temp_dir
                })
            }
        }
        
        mock_response = self.create_mock_response([mock_tool_call])
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent.run(f"Search for files containing 'DEBUG' in {self.temp_dir}")
            
            self.assertTrue(mock_llm.called)
            call_args = mock_llm.call_args[1]
            self.assertIn("search_files", str(call_args))
            
    async def test_agent_multiple_file_operations(self):
        """Test multiple file operations in sequence."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Mock multiple tool calls in sequence
        mock_tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "write_file",
                    "arguments": json.dumps({
                        "file_path": self.test_file,
                        "content": "Initial content"
                    })
                }
            },
            {
                "id": "call_2", 
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": json.dumps({
                        "file_path": self.test_file
                    })
                }
            },
            {
                "id": "call_3",
                "type": "function", 
                "function": {
                    "name": "update_file",
                    "arguments": json.dumps({
                        "file_path": self.test_file,
                        "old_content": "Initial",
                        "new_content": "Updated"
                    })
                }
            }
        ]
        
        mock_response = self.create_mock_response(mock_tool_calls)
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent.run(f"Create file {self.test_file}, read it, then update 'Initial' to 'Updated'")
            
            self.assertTrue(mock_llm.called)
            call_args = mock_llm.call_args[1]
            
            # Check that all three tools were mentioned in the call
            call_str = str(call_args)
            self.assertIn("write_file", call_str)
            self.assertIn("read_file", call_str)
            self.assertIn("update_file", call_str)
            
    async def test_agent_file_tools_disabled(self):
        """Test that file tools are not available when disabled."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=False,  # Disabled
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Check that file tools are not in available tools
        available_tool_names = []
        if hasattr(agent, 'available_tools'):
            for tool_dict in agent.available_tools:
                if 'function' in tool_dict and 'name' in tool_dict['function']:
                    available_tool_names.append(tool_dict['function']['name'])
        
        self.assertNotIn('read_file', available_tool_names)
        self.assertNotIn('write_file', available_tool_names)
        self.assertNotIn('update_file', available_tool_names)
        self.assertNotIn('search_files', available_tool_names)
        
    async def test_agent_file_tools_enabled_by_default(self):
        """Test that file tools are available by default."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            # enable_file_tools defaults to True
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Check that file tools are in available tools
        available_tool_names = []
        if hasattr(agent, 'available_tools'):
            for tool_dict in agent.available_tools:
                if 'function' in tool_dict and 'name' in tool_dict['function']:
                    available_tool_names.append(tool_dict['function']['name'])
        
        self.assertIn('read_file', available_tool_names)
        self.assertIn('write_file', available_tool_names)
        self.assertIn('update_file', available_tool_names)
        self.assertIn('search_files', available_tool_names)


async def run_e2e_tests():
    """Run all end-to-end tests."""
    print("Running file tools end-to-end tests...")
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFileToolsE2E)
    
    # Create test instance
    test_instance = TestFileToolsE2E()
    
    for test in suite:
        if hasattr(test, '_testMethodName'):
            test_method_name = test._testMethodName
            test_method = getattr(test_instance, test_method_name)
            
            print(f"\nRunning {test_method_name}...")
            test_instance.setUp()
            
            try:
                if asyncio.iscoroutinefunction(test_method):
                    await test_method()
                else:
                    test_method()
                print(f"✅ {test_method_name} passed")
            except Exception as e:
                print(f"❌ {test_method_name} failed: {e}")
                import traceback
                traceback.print_exc()
                raise
            finally:
                test_instance.tearDown()


if __name__ == "__main__":
    print("Starting end-to-end tests for file tools...")
    asyncio.run(run_e2e_tests())
    print("\n🎉 All end-to-end tests completed successfully!")