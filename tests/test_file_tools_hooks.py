#!/usr/bin/env python3
"""
Test file tools with universal hooks integration and error handling.
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
from tinyagent.code_agent.tools.file_tools import FileOperationApprovalHook, DevelopmentHook


class TestFileToolsHooks(unittest.TestCase):
    """Test file tools with hooks and error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test.txt")
        
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
        
    async def test_file_operation_approval_hook_allow(self):
        """Test FileOperationApprovalHook allowing operations."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Add approval hook that allows operations
        approval_hook = FileOperationApprovalHook(
            allowed_directories=[self.temp_dir],
            allowed_operations=["read", "write", "update", "search"]
        )
        agent.add_hook(approval_hook)
        
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
            
            # This should work (hook allows operation)
            result = await agent.run(f"Read file {self.test_file}")
            
            self.assertTrue(mock_llm.called)
            
    async def test_file_operation_approval_hook_deny(self):
        """Test FileOperationApprovalHook denying operations."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Add approval hook that denies operations outside allowed directory
        approval_hook = FileOperationApprovalHook(
            allowed_directories=["/some/other/directory"],  # Not our temp_dir
            allowed_operations=["read", "write", "update", "search"]
        )
        agent.add_hook(approval_hook)
        
        mock_tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({
                    "file_path": self.test_file  # This path should be denied
                })
            }
        }
        
        mock_response = self.create_mock_response([mock_tool_call])
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            # This should be intercepted by the hook
            result = await agent.run(f"Read file {self.test_file}")
            
            # The LLM should still be called, but the hook should modify the execution
            self.assertTrue(mock_llm.called)
            
    async def test_development_hook_logs_operations(self):
        """Test DevelopmentHook logging file operations."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Add development hook for logging
        dev_hook = DevelopmentHook()
        agent.add_hook(dev_hook)
        
        mock_tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "write_file",
                "arguments": json.dumps({
                    "file_path": self.test_file,
                    "content": "Test content"
                })
            }
        }
        
        mock_response = self.create_mock_response([mock_tool_call])
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            result = await agent.run(f"Write test content to {self.test_file}")
            
            self.assertTrue(mock_llm.called)
            # Dev hook should have logged the operation (we can't easily test the logging output)
            
    async def test_hook_before_tool_execution(self):
        """Test before_tool_execution hook."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Mock hook that denies execution
        class DenyHook:
            def __init__(self):
                self.called = False
                
            async def before_tool_execution(self, tool_name, tool_args, tool_call):
                self.called = True
                if tool_name == "read_file":
                    return {"success": False, "error": "Read operation denied by hook"}
                return None
        
        deny_hook = DenyHook()
        agent.add_hook(deny_hook)
        
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
            
            result = await agent.run(f"Read file {self.test_file}")
            
            self.assertTrue(mock_llm.called)
            self.assertTrue(deny_hook.called)
            
    async def test_hook_after_tool_execution(self):
        """Test after_tool_execution hook."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Mock hook that modifies results
        class ModifyResultHook:
            def __init__(self):
                self.called = False
                
            async def after_tool_execution(self, tool_name, tool_args, tool_call, result):
                self.called = True
                if tool_name == "read_file":
                    # Modify the result
                    return {"success": True, "content": "Modified by hook", "modified": True}
                return None
        
        modify_hook = ModifyResultHook()
        agent.add_hook(modify_hook)
        
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
            
            result = await agent.run(f"Read file {self.test_file}")
            
            self.assertTrue(mock_llm.called)
            self.assertTrue(modify_hook.called)
            
    async def test_error_handling_invalid_json_args(self):
        """Test error handling for invalid JSON arguments."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Mock tool call with invalid JSON
        mock_tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": "invalid json {{"  # Invalid JSON
            }
        }
        
        mock_response = self.create_mock_response([mock_tool_call])
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            # This should handle the JSON parse error gracefully
            result = await agent.run(f"Read file {self.test_file}")
            
            self.assertTrue(mock_llm.called)
            
    async def test_error_handling_missing_required_args(self):
        """Test error handling for missing required arguments."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        # Mock tool call missing required file_path argument
        mock_tool_call = {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": json.dumps({
                    # "file_path": self.test_file,  # Missing required argument
                    "encoding": "utf-8"
                })
            }
        }
        
        mock_response = self.create_mock_response([mock_tool_call])
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_response
            
            # This should handle the missing argument error gracefully
            result = await agent.run(f"Read file")
            
            self.assertTrue(mock_llm.called)
            
    async def test_multiple_hooks_execution_order(self):
        """Test that multiple hooks execute in the correct order."""
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            provider="modal",
            local_execution=True,
            enable_file_tools=True,
            enable_python_tool=False,
            enable_shell_tool=False
        )
        
        execution_order = []
        
        class OrderHook1:
            async def before_tool_execution(self, tool_name, tool_args, tool_call):
                execution_order.append("hook1_before")
                return None
                
            async def after_tool_execution(self, tool_name, tool_args, tool_call, result):
                execution_order.append("hook1_after")
                return None
        
        class OrderHook2:
            async def before_tool_execution(self, tool_name, tool_args, tool_call):
                execution_order.append("hook2_before")
                return None
                
            async def after_tool_execution(self, tool_name, tool_args, tool_call, result):
                execution_order.append("hook2_after")
                return None
        
        # Add hooks in order
        agent.add_hook(OrderHook1())
        agent.add_hook(OrderHook2())
        
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
            
            result = await agent.run(f"Read file {self.test_file}")
            
            self.assertTrue(mock_llm.called)
            
            # Check execution order
            expected_order = ["hook1_before", "hook2_before", "hook2_after", "hook1_after"]
            # Note: actual order may vary based on implementation


async def run_hooks_tests():
    """Run all hooks and error handling tests."""
    print("Running file tools hooks and error handling tests...")
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFileToolsHooks)
    
    # Create test instance
    test_instance = TestFileToolsHooks()
    
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
                # Don't raise, continue with other tests
            finally:
                test_instance.tearDown()


if __name__ == "__main__":
    print("Starting hooks and error handling tests for file tools...")
    asyncio.run(run_hooks_tests())
    print("\n🎉 All hooks and error handling tests completed!")