"""
Real file operation tests for TinyAgent file tools.
Tests actual file read/write/update/search operations with mock LLM responses.
"""

import asyncio
import os
import tempfile
import shutil
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tinyagent.code_agent.tiny_code_agent import TinyCodeAgent
from tinyagent.code_agent.providers.modal_provider import ModalProvider
from tinyagent.code_agent.providers.seatbelt_provider import SeatbeltProvider
from tinyagent.hooks.logging_manager import LoggingManager


class TestFileToolsRealOperations:
    """Test file tools with real file operations."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def dummy_file_path(self, temp_dir):
        """Create path for dummy.txt file."""
        return os.path.join(temp_dir, "dummy.txt")
    
    @pytest.fixture
    def mock_llm_responses(self):
        """Mock LLM responses for different file operations."""
        return {
            "write_file": {
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": '{"file_path": "DUMMY_PATH", "content": "Hello, World!\\nThis is a test file."}'
                        }
                    }
                ]
            },
            "read_file": {
                "tool_calls": [
                    {
                        "id": "call_2", 
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"file_path": "DUMMY_PATH"}'
                        }
                    }
                ]
            },
            "search_files": {
                "tool_calls": [
                    {
                        "id": "call_3",
                        "type": "function", 
                        "function": {
                            "name": "search_files",
                            "arguments": '{"pattern": "test", "directory": "TEMP_DIR"}'
                        }
                    }
                ]
            },
            "update_file": {
                "tool_calls": [
                    {
                        "id": "call_4",
                        "type": "function",
                        "function": {
                            "name": "update_file", 
                            "arguments": '{"file_path": "DUMMY_PATH", "old_content": "Hello, World!", "new_content": "Hello, TinyAgent!"}'
                        }
                    }
                ]
            }
        }
    
    async def create_agent_with_mock_llm(self, provider_type="modal"):
        """Create TinyCodeAgent with mocked LLM."""
        log_manager = LoggingManager()
        
        agent = TinyCodeAgent(
            log_manager=log_manager,
            provider=provider_type,
            local_execution=True,  # Use local execution for testing
            enable_file_tools=True
        )
        return agent
    
    @pytest.mark.asyncio
    async def test_write_file_operation(self, temp_dir, dummy_file_path, mock_llm_responses):
        """Test writing to dummy.txt file."""
        agent = await self.create_agent_with_mock_llm()
        
        # Mock the LLM response for write_file
        mock_response = mock_llm_responses["write_file"]
        # Replace placeholder with actual path
        mock_response["tool_calls"][0]["function"]["arguments"] = mock_response["tool_calls"][0]["function"]["arguments"].replace("DUMMY_PATH", dummy_file_path)
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            # Create proper tool call object structure 
            tool_call_obj = MagicMock()
            tool_call_obj.id = "call_1"
            tool_call_obj.type = "function"
            tool_call_obj.function = MagicMock()
            tool_call_obj.function.name = "write_file"
            tool_call_obj.function.arguments = mock_response["tool_calls"][0]["function"]["arguments"]
            
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll write to the file.",
                tool_calls=[tool_call_obj]
            ))])
            
            # Execute the agent
            result = await agent.run("Write 'Hello, World!' and 'This is a test file.' to dummy.txt")
            
            # Verify file was actually created and contains expected content
            assert os.path.exists(dummy_file_path), "dummy.txt file should be created"
            
            with open(dummy_file_path, 'r') as f:
                content = f.read()
            
            assert "Hello, World!" in content, "File should contain 'Hello, World!'"
            assert "This is a test file." in content, "File should contain test message"
    
    @pytest.mark.asyncio
    async def test_read_file_operation(self, temp_dir, dummy_file_path, mock_llm_responses):
        """Test reading from dummy.txt file."""
        # First create the dummy file
        with open(dummy_file_path, 'w') as f:
            f.write("Hello, World!\nThis is a test file.")
        
        agent = await self.create_agent_with_mock_llm()
        
        # Mock the LLM response for read_file
        mock_response = mock_llm_responses["read_file"]
        mock_response["tool_calls"][0]["function"]["arguments"] = mock_response["tool_calls"][0]["function"]["arguments"].replace("DUMMY_PATH", dummy_file_path)
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll read the file for you.",
                tool_calls=mock_response["tool_calls"]
            ))])
            
            # Execute the agent
            result = await agent.run(f"Read the contents of {dummy_file_path}")
            
            # Verify the result contains file content
            assert "Hello, World!" in str(result), "Result should contain file content"
            assert "test file" in str(result), "Result should contain file content"
    
    @pytest.mark.asyncio
    async def test_search_files_operation(self, temp_dir, dummy_file_path, mock_llm_responses):
        """Test searching for files with pattern."""
        # Create dummy file with searchable content
        with open(dummy_file_path, 'w') as f:
            f.write("Hello, World!\nThis is a test file for searching.")
        
        agent = await self.create_agent_with_mock_llm()
        
        # Mock the LLM response for search_files
        mock_response = mock_llm_responses["search_files"]
        mock_response["tool_calls"][0]["function"]["arguments"] = mock_response["tool_calls"][0]["function"]["arguments"].replace("TEMP_DIR", temp_dir)
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll search for files containing 'test'.",
                tool_calls=mock_response["tool_calls"]
            ))])
            
            # Execute the agent
            result = await agent.run(f"Search for files containing 'test' in {temp_dir}")
            
            # Verify the search found the dummy file
            assert "dummy.txt" in str(result), "Search should find dummy.txt"
            assert "test" in str(result), "Search result should contain the search term"
    
    @pytest.mark.asyncio
    async def test_update_file_operation(self, temp_dir, dummy_file_path, mock_llm_responses):
        """Test updating content in dummy.txt file."""
        # Create dummy file with initial content
        with open(dummy_file_path, 'w') as f:
            f.write("Hello, World!\nThis is a test file.")
        
        agent = await self.create_agent_with_mock_llm()
        
        # Mock the LLM response for update_file
        mock_response = mock_llm_responses["update_file"]
        mock_response["tool_calls"][0]["function"]["arguments"] = mock_response["tool_calls"][0]["function"]["arguments"].replace("DUMMY_PATH", dummy_file_path)
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll update the file content.",
                tool_calls=mock_response["tool_calls"]
            ))])
            
            # Execute the agent
            result = await agent.run(f"In {dummy_file_path}, replace 'Hello, World!' with 'Hello, TinyAgent!'")
            
            # Verify file was actually updated
            with open(dummy_file_path, 'r') as f:
                content = f.read()
            
            assert "Hello, TinyAgent!" in content, "File should contain updated content"
            assert "Hello, World!" not in content, "Old content should be replaced"
            assert "test file" in content, "Other content should remain unchanged"
    
    @pytest.mark.asyncio
    async def test_complete_file_workflow(self, temp_dir, dummy_file_path):
        """Test complete workflow: write -> read -> update -> search."""
        agent = await self.create_agent_with_mock_llm()
        
        # Step 1: Write file
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll write to the file.",
                tool_calls=[{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": f'{{"file_path": "{dummy_file_path}", "content": "Initial content\\nfor testing workflow."}}'
                    }
                }]
            ))])
            
            await agent.run("Write initial content to dummy.txt")
            
            # Verify write
            assert os.path.exists(dummy_file_path)
            with open(dummy_file_path, 'r') as f:
                content = f.read()
            assert "Initial content" in content
        
        # Step 2: Read file
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll read the file.",
                tool_calls=[{
                    "id": "call_2",
                    "type": "function", 
                    "function": {
                        "name": "read_file",
                        "arguments": f'{{"file_path": "{dummy_file_path}"}}'
                    }
                }]
            ))])
            
            result = await agent.run("Read the dummy.txt file")
            assert "Initial content" in str(result)
        
        # Step 3: Update file
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll update the file.",
                tool_calls=[{
                    "id": "call_3",
                    "type": "function",
                    "function": {
                        "name": "update_file",
                        "arguments": f'{{"file_path": "{dummy_file_path}", "old_content": "Initial content", "new_content": "Updated content"}}'
                    }
                }]
            ))])
            
            await agent.run("Update 'Initial content' to 'Updated content' in dummy.txt")
            
            # Verify update
            with open(dummy_file_path, 'r') as f:
                content = f.read()
            assert "Updated content" in content
            assert "Initial content" not in content
        
        # Step 4: Search files
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll search for files.",
                tool_calls=[{
                    "id": "call_4", 
                    "type": "function",
                    "function": {
                        "name": "search_files",
                        "arguments": f'{{"pattern": "Updated", "directory": "{temp_dir}"}}'
                    }
                }]
            ))])
            
            result = await agent.run(f"Search for 'Updated' in {temp_dir}")
            assert "dummy.txt" in str(result)
            assert "Updated" in str(result)
    
    @pytest.mark.asyncio
    async def test_file_tools_with_seatbelt_provider(self, temp_dir, dummy_file_path):
        """Test file tools work with SeatbeltProvider."""
        agent = await self.create_agent_with_mock_llm("seatbelt")
        
        with patch.object(agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                content="I'll write to the file.",
                tool_calls=[{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "write_file", 
                        "arguments": f'{{"file_path": "{dummy_file_path}", "content": "SeatbeltProvider test content"}}'
                    }
                }]
            ))])
            
            await agent.run("Write test content using SeatbeltProvider")
            
            # Verify file was created
            assert os.path.exists(dummy_file_path)
            with open(dummy_file_path, 'r') as f:
                content = f.read()
            assert "SeatbeltProvider test content" in content


if __name__ == "__main__":
    # Run a quick test to verify file tools work out of the box
    async def quick_test():
        """Quick test to verify file tools work in current directory."""
        current_dir = os.getcwd()
        dummy_path = os.path.join(current_dir, "dummy.txt")
        
        try:
            # Test with ModalProvider
            log_manager = LoggingManager()
            modal_agent = TinyCodeAgent(
                log_manager=log_manager,
                provider="modal",
                local_execution=True,
                enable_file_tools=True
            )
            
            print("Testing file tools in current directory...")
            print(f"Current directory: {current_dir}")
            print(f"Dummy file path: {dummy_path}")
            
            # Mock write operation
            with patch.object(modal_agent, '_litellm_with_retry', new_callable=AsyncMock) as mock_llm:
                mock_llm.return_value = MagicMock(choices=[MagicMock(message=MagicMock(
                    content="I'll write to dummy.txt.",
                    tool_calls=[{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": f'{{"file_path": "{dummy_path}", "content": "Test content from file tools\\nThis verifies file tools work out of the box!"}}'
                        }
                    }]
                ))])
                
                result = await modal_agent.run("Write test content to dummy.txt in current directory")
                print(f"Write result: {result}")
                
                # Check if file exists and has correct content
                if os.path.exists(dummy_path):
                    with open(dummy_path, 'r') as f:
                        content = f.read()
                    print(f"File created successfully with content:\n{content}")
                    
                    # Clean up
                    os.remove(dummy_path)
                    print("Test file cleaned up.")
                    print("✅ File tools work out of the box!")
                else:
                    print("❌ File was not created - file tools may not be working correctly")
        
        except Exception as e:
            print(f"❌ Error during test: {e}")
            # Clean up if file exists
            if os.path.exists(dummy_path):
                os.remove(dummy_path)
    
    # Run the quick test
    asyncio.run(quick_test())