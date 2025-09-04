#!/usr/bin/env python3
"""
Comprehensive tests for the custom instruction system.
"""

import asyncio
import logging
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

import pytest

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class TestCustomInstructionLoader:
    """Test the CustomInstructionLoader class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_content = "These are test custom instructions for the agent."
        
        # Create a test AGENTS.md file
        self.agents_md_path = self.temp_dir / "AGENTS.md"
        with open(self.agents_md_path, 'w') as f:
            f.write(self.test_content)
            
        # Create another test file with different name
        self.custom_file_path = self.temp_dir / "MY_INSTRUCTIONS.md"
        with open(self.custom_file_path, 'w') as f:
            f.write("Custom filename instructions")
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_initialization_enabled(self):
        """Test loader initialization with enabled state."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(enabled=True)
        
        assert loader.is_enabled() is True
        assert loader.auto_detect_agents_md is True
        assert loader.custom_filename == "AGENTS.md"
        assert loader.inherit_to_subagents is True
    
    def test_initialization_disabled(self):
        """Test loader initialization with disabled state."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(enabled=False)
        
        assert loader.is_enabled() is False
        config = loader.get_config()
        assert config["enabled"] is False
    
    def test_load_from_string(self):
        """Test loading instructions from string."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader()
        instructions = "You are a helpful assistant with special instructions."
        
        result = loader.load_instructions(instructions)
        
        assert result == instructions
        assert loader.get_instructions() == instructions
        assert loader.get_instruction_source() == "string"
    
    def test_load_from_file(self):
        """Test loading instructions from file."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader()
        
        result = loader.load_instructions(self.agents_md_path)
        
        assert result == self.test_content
        assert loader.get_instructions() == self.test_content
        assert loader.get_instruction_source() == str(self.agents_md_path)
    
    def test_auto_detect_agents_md(self):
        """Test auto-detection of AGENTS.md file."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(
            execution_directory=self.temp_dir,
            auto_detect_agents_md=True
        )
        
        result = loader.load_instructions()
        
        assert result == self.test_content
        assert loader.get_instruction_source() == str(self.agents_md_path)
    
    def test_auto_detect_custom_filename(self):
        """Test auto-detection with custom filename."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(
            execution_directory=self.temp_dir,
            custom_filename="MY_INSTRUCTIONS.md",
            auto_detect_agents_md=True
        )
        
        result = loader.load_instructions()
        
        assert result == "Custom filename instructions"
        assert loader.get_instruction_source() == str(self.custom_file_path)
    
    def test_no_auto_detect_when_disabled(self):
        """Test that auto-detection is disabled when configured."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(
            execution_directory=self.temp_dir,
            auto_detect_agents_md=False
        )
        
        result = loader.load_instructions()
        
        assert result == ""
        assert loader.get_instruction_source() is None
    
    def test_disabled_loader_returns_empty(self):
        """Test that disabled loader always returns empty string."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(enabled=False)
        
        # Try with string
        result1 = loader.load_instructions("Test instructions")
        assert result1 == ""
        
        # Try with file
        result2 = loader.load_instructions(self.agents_md_path)
        assert result2 == ""
    
    def test_file_not_found_error(self):
        """Test error handling for non-existent files."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader, CustomInstructionError
        
        loader = CustomInstructionLoader()
        nonexistent_path = self.temp_dir / "nonexistent.md"
        
        with pytest.raises(CustomInstructionError, match="File not found"):
            loader.load_instructions(nonexistent_path)
    
    def test_empty_string_instructions(self):
        """Test handling of empty string instructions."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader()
        
        result = loader.load_instructions("")
        
        assert result == ""
        assert loader.get_instruction_source() == "string"
    
    def test_empty_file_instructions(self):
        """Test handling of empty file."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        empty_file = self.temp_dir / "empty.md"
        empty_file.touch()
        
        loader = CustomInstructionLoader()
        
        result = loader.load_instructions(empty_file)
        
        assert result == ""
        assert loader.get_instruction_source() == str(empty_file)
    
    def test_apply_to_system_prompt_with_placeholder(self):
        """Test applying custom instructions to system prompt with placeholder."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader()
        loader.load_instructions("Follow these special rules.")
        
        system_prompt = "You are an assistant. <user_specified_instruction></user_specified_instruction> Help the user."
        
        result = loader.apply_to_system_prompt(system_prompt)
        expected = "You are an assistant. Follow these special rules. Help the user."
        
        assert result == expected
    
    def test_apply_to_system_prompt_without_placeholder(self):
        """Test applying custom instructions to system prompt without placeholder."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader()
        loader.load_instructions("Follow these special rules.")
        
        system_prompt = "You are a helpful assistant."
        
        result = loader.apply_to_system_prompt(system_prompt)
        expected = "You are a helpful assistant.\n\n## Custom Instructions\nFollow these special rules."
        
        assert result == expected
    
    def test_apply_to_system_prompt_disabled(self):
        """Test that disabled loader removes placeholder."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(enabled=False)
        loader.load_instructions("These won't be applied")
        
        system_prompt = "Original prompt <user_specified_instruction></user_specified_instruction>"
        
        result = loader.apply_to_system_prompt(system_prompt)
        
        # When disabled, should remove placeholder but not apply custom instructions
        expected = "Original prompt"
        assert result == expected
        assert "These won't be applied" not in result
    
    def test_apply_to_system_prompt_no_instructions(self):
        """Test applying to system prompt when no custom instructions are loaded."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader()
        
        system_prompt = "You are an assistant. <user_specified_instruction></user_specified_instruction> Help the user."
        
        result = loader.apply_to_system_prompt(system_prompt)
        expected = "You are an assistant.  Help the user."
        
        assert result.strip() == expected.strip()
    
    def test_custom_placeholder(self):
        """Test using custom placeholder."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader()
        loader.load_instructions("Custom rules here")
        
        system_prompt = "Start {{CUSTOM}} End"
        placeholder = "{{CUSTOM}}"
        
        result = loader.apply_to_system_prompt(system_prompt, placeholder)
        expected = "Start Custom rules here End"
        
        assert result == expected
    
    def test_enable_disable_functionality(self):
        """Test enabling and disabling the loader."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(enabled=True)
        
        # Should work when enabled
        result1 = loader.load_instructions("Test")
        assert result1 == "Test"
        
        # Disable
        loader.enable(False)
        assert loader.is_enabled() is False
        
        # Should return empty when disabled
        result2 = loader.load_instructions("Test")
        assert result2 == ""
        
        # Re-enable
        loader.enable(True)
        assert loader.is_enabled() is True
        
        # Should work again
        result3 = loader.load_instructions("Test")
        assert result3 == "Test"
    
    def test_set_execution_directory(self):
        """Test changing execution directory."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader()
        
        # Create different directory with different file
        new_dir = self.temp_dir / "subdir"
        new_dir.mkdir()
        new_agents_file = new_dir / "AGENTS.md"
        with open(new_agents_file, 'w') as f:
            f.write("Different instructions")
        
        # Set new execution directory
        loader.set_execution_directory(new_dir)
        
        result = loader.load_instructions()
        assert result == "Different instructions"
    
    def test_set_custom_filename(self):
        """Test changing custom filename."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(execution_directory=self.temp_dir)
        
        # First try with default filename
        result1 = loader.load_instructions()
        assert result1 == self.test_content  # AGENTS.md content
        
        # Change filename and try again
        loader.set_custom_filename("MY_INSTRUCTIONS.md")
        result2 = loader.load_instructions()
        assert result2 == "Custom filename instructions"
    
    def test_get_config(self):
        """Test getting configuration dictionary."""
        from tinyagent.core.custom_instructions import CustomInstructionLoader
        
        loader = CustomInstructionLoader(
            enabled=True,
            auto_detect_agents_md=False,
            custom_filename="custom.md",
            inherit_to_subagents=False,
            execution_directory=self.temp_dir
        )
        loader.load_instructions("Test")
        
        config = loader.get_config()
        
        assert config["enabled"] is True
        assert config["auto_detect_agents_md"] is False
        assert config["custom_filename"] == "custom.md"
        assert config["inherit_to_subagents"] is False
        assert config["execution_directory"] == str(self.temp_dir)
        assert config["has_instructions"] is True
        assert config["instruction_source"] == "string"
    
    def test_factory_function(self):
        """Test the factory function."""
        from tinyagent.core.custom_instructions import create_custom_instruction_loader
        
        loader = create_custom_instruction_loader(
            enabled=True,
            custom_filename="test.md"
        )
        
        assert loader.is_enabled() is True
        assert loader.custom_filename == "test.md"


class TestTinyAgentIntegration:
    """Test integration with TinyAgent."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create test AGENTS.md
        self.agents_md_path = self.temp_dir / "AGENTS.md"
        with open(self.agents_md_path, 'w') as f:
            f.write("You are a specialized AI assistant focused on helping users with coding tasks. Always provide detailed explanations.")
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    @patch('tinyagent.TinyAgent._litellm_with_retry')
    async def test_tinyagent_with_custom_instructions_string(self, mock_llm):
        """Test TinyAgent with custom instructions from string."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "I'll help with that!"
        mock_response.choices[0].message.tool_calls = []
        mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        mock_llm.return_value = mock_response
        
        from tinyagent import TinyAgent
        
        custom_instructions = "Always respond with excitement and use emojis!"
        
        agent = TinyAgent(
            model="gpt-5-mini",
            custom_instructions=custom_instructions,
            system_prompt="You are a helpful assistant. <user_specified_instruction></user_specified_instruction>",
            temperature=0.0
        )
        
        # Check that system prompt includes custom instructions
        expected_system_content = "You are a helpful assistant. Always respond with excitement and use emojis!"
        assert agent.messages[0]["content"] == expected_system_content
        
        # Test a simple interaction
        result = await agent.run("Hello!")
        assert "I'll help with that!" in result
        
        # Verify the system prompt was sent to LLM correctly
        mock_llm.assert_called()
        call_args = mock_llm.call_args
        messages_sent = call_args[1]["messages"]
        assert messages_sent[0]["role"] == "system"
        assert "Always respond with excitement and use emojis!" in messages_sent[0]["content"]
        
        await agent.close()
    
    @patch('tinyagent.TinyAgent._litellm_with_retry')
    async def test_tinyagent_with_custom_instructions_file(self, mock_llm):
        """Test TinyAgent with custom instructions from file."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Ready to help with coding!"
        mock_response.choices[0].message.tool_calls = []
        mock_response.usage = {"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23}
        mock_llm.return_value = mock_response
        
        from tinyagent import TinyAgent
        
        agent = TinyAgent(
            model="gpt-5-mini",
            custom_instructions=str(self.agents_md_path),
            system_prompt="Base prompt. <user_specified_instruction></user_specified_instruction>",
            temperature=0.0
        )
        
        # Check system prompt
        expected_content = "Base prompt. You are a specialized AI assistant focused on helping users with coding tasks. Always provide detailed explanations."
        assert agent.messages[0]["content"] == expected_content
        
        await agent.close()
    
    @patch('tinyagent.TinyAgent._litellm_with_retry')  
    async def test_tinyagent_with_auto_detect(self, mock_llm):
        """Test TinyAgent with auto-detection of AGENTS.md."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Auto-detected instructions!"
        mock_response.choices[0].message.tool_calls = []
        mock_response.usage = {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18}
        mock_llm.return_value = mock_response
        
        from tinyagent import TinyAgent
        
        # Change to temp directory so auto-detection finds our AGENTS.md
        original_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            
            agent = TinyAgent(
                model="gpt-5-mini",
                enable_custom_instructions=True,
                system_prompt="Base. <user_specified_instruction></user_specified_instruction>",
                temperature=0.0
            )
            
            # Check system prompt includes auto-detected instructions
            assert "You are a specialized AI assistant focused on helping users with coding tasks" in agent.messages[0]["content"]
            
            await agent.close()
            
        finally:
            os.chdir(original_cwd)
    
    @patch('tinyagent.TinyAgent._litellm_with_retry')
    async def test_tinyagent_disabled_custom_instructions(self, mock_llm):
        """Test TinyAgent with custom instructions disabled."""
        # Mock LLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Standard response"
        mock_response.choices[0].message.tool_calls = []
        mock_response.usage = {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12}
        mock_llm.return_value = mock_response
        
        from tinyagent import TinyAgent
        
        agent = TinyAgent(
            model="gpt-5-mini",
            custom_instructions="This should be ignored",
            enable_custom_instructions=False,
            system_prompt="Original prompt <user_specified_instruction></user_specified_instruction>",
            temperature=0.0
        )
        
        # System prompt should not include custom instructions
        assert agent.messages[0]["content"] == "Original prompt "
        
        await agent.close()
    
    async def test_tinyagent_invalid_instructions_file(self):
        """Test TinyAgent with invalid custom instruction file."""
        from tinyagent import TinyAgent
        from tinyagent.core.custom_instructions import CustomInstructionError
        
        with pytest.raises(CustomInstructionError, match="File not found"):
            TinyAgent(
                model="gpt-5-mini",
                custom_instructions="/nonexistent/path/to/file.md",
                temperature=0.0
            )


class TestTinyCodeAgentIntegration:
    """Test integration with TinyCodeAgent."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Create coding-specific AGENTS.md
        self.agents_md_path = self.temp_dir / "AGENTS.md"
        with open(self.agents_md_path, 'w') as f:
            f.write("Focus on Python development. Always write clean, well-documented code. Use type hints.")
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_tinycode_agent_with_custom_instructions(self):
        """Test TinyCodeAgent with custom instructions."""
        from tinyagent.code_agent import TinyCodeAgent
        
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            custom_instructions="Always explain your code thoroughly and use best practices.",
            local_execution=True
        )
        
        # Check that system prompt includes custom instructions
        system_content = agent.messages[0]["content"]
        assert "Always explain your code thoroughly and use best practices." in system_content
        
    async def test_tinycode_agent_file_instructions(self):
        """Test TinyCodeAgent with file-based custom instructions."""
        from tinyagent.code_agent import TinyCodeAgent
        
        agent = TinyCodeAgent(
            model="gpt-5-mini",
            custom_instructions=str(self.agents_md_path),
            local_execution=True
        )
        
        # Check system prompt
        system_content = agent.messages[0]["content"]
        assert "Focus on Python development" in system_content
        assert "Always write clean, well-documented code" in system_content
        assert "Use type hints" in system_content
        
        await agent.close()


async def main():
    """Run all tests."""
    logger.info("=== Running Custom Instruction Tests ===")
    
    # Test basic functionality
    test_loader = TestCustomInstructionLoader()
    test_loader.setup_method()
    
    try:
        test_loader.test_initialization_enabled()
        test_loader.test_initialization_disabled()
        test_loader.test_load_from_string()
        test_loader.test_load_from_file()
        test_loader.test_auto_detect_agents_md()
        test_loader.test_auto_detect_custom_filename()
        test_loader.test_no_auto_detect_when_disabled()
        test_loader.test_disabled_loader_returns_empty()
        test_loader.test_empty_string_instructions()
        test_loader.test_empty_file_instructions()
        test_loader.test_apply_to_system_prompt_with_placeholder()
        test_loader.test_apply_to_system_prompt_without_placeholder()
        test_loader.test_apply_to_system_prompt_disabled()
        test_loader.test_apply_to_system_prompt_no_instructions()
        test_loader.test_custom_placeholder()
        test_loader.test_enable_disable_functionality()
        test_loader.test_set_execution_directory()
        test_loader.test_set_custom_filename()
        test_loader.test_get_config()
        test_loader.test_factory_function()
        
        logger.info("✅ All CustomInstructionLoader tests passed!")
        
    except Exception as e:
        logger.error(f"❌ CustomInstructionLoader test failed: {e}")
        raise
    finally:
        test_loader.teardown_method()
    
    # Test error cases
    test_loader2 = TestCustomInstructionLoader()
    test_loader2.setup_method()
    
    try:
        test_loader2.test_file_not_found_error()
        logger.info("✅ Error handling tests passed!")
    except Exception as e:
        logger.error(f"❌ Error handling test failed: {e}")
        raise
    finally:
        test_loader2.teardown_method()
    
    # Test TinyAgent integration (requires import to work)
    try:
        test_integration = TestTinyAgentIntegration()
        test_integration.setup_method()
        
        try:
            await test_integration.test_tinyagent_with_custom_instructions_string()
            await test_integration.test_tinyagent_with_custom_instructions_file()
            await test_integration.test_tinyagent_with_auto_detect()
            await test_integration.test_tinyagent_disabled_custom_instructions()
            await test_integration.test_tinyagent_invalid_instructions_file()
            
            logger.info("✅ TinyAgent integration tests passed!")
            
        finally:
            test_integration.teardown_method()
            
    except ImportError as e:
        logger.warning(f"⚠️  Skipping TinyAgent integration tests (import error): {e}")
    except Exception as e:
        logger.error(f"❌ TinyAgent integration test failed: {e}")
        raise
    
    # Test TinyCodeAgent integration
    try:
        test_code_integration = TestTinyCodeAgentIntegration()
        test_code_integration.setup_method()
        
        try:
            test_code_integration.test_tinycode_agent_with_custom_instructions()
            await test_code_integration.test_tinycode_agent_file_instructions()
            
            logger.info("✅ TinyCodeAgent integration tests passed!")
            
        finally:
            test_code_integration.teardown_method()
            
    except ImportError as e:
        logger.warning(f"⚠️  Skipping TinyCodeAgent integration tests (import error): {e}")
    except Exception as e:
        logger.error(f"❌ TinyCodeAgent integration test failed: {e}")
        raise
    
    logger.info("🎉 All custom instruction tests completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())