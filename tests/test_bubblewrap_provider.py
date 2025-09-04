#!/usr/bin/env python3
"""
Unit tests for BubblewrapProvider.
Tests the core functionality of the Linux bubblewrap sandbox implementation.
"""

import os
import sys
import pytest
import tempfile
import platform
import asyncio
import subprocess
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add the tinyagent module to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tinyagent.code_agent.providers.bubblewrap_provider import BubblewrapProvider
    from tinyagent.hooks.logging_manager import LoggingManager
except ImportError as e:
    pytest.skip(f"Cannot import required modules: {e}", allow_module_level=True)


class TestBubblewrapProvider:
    """Test cases for BubblewrapProvider"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.log_manager = Mock(spec=LoggingManager)
        self.mock_logger = Mock()
        self.log_manager.get_logger.return_value = self.mock_logger
        
    def test_linux_platform_check(self):
        """Test that BubblewrapProvider only works on Linux"""
        with patch('platform.system') as mock_platform:
            # Test non-Linux platform
            mock_platform.return_value = "Darwin"
            with pytest.raises(RuntimeError, match="only works on Linux systems"):
                BubblewrapProvider(log_manager=self.log_manager)
            
            # Test Linux platform (should not raise)
            mock_platform.return_value = "Linux"
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                provider = BubblewrapProvider(log_manager=self.log_manager)
                assert provider is not None
    
    def test_bubblewrap_availability_check(self):
        """Test bubblewrap availability detection"""
        with patch('platform.system', return_value="Linux"):
            # Test bubblewrap not available
            with patch('subprocess.run') as mock_run:
                mock_run.side_effect = FileNotFoundError()
                with pytest.raises(RuntimeError, match="Bubblewrap .* is not available"):
                    BubblewrapProvider(log_manager=self.log_manager)
            
            # Test bubblewrap available
            with patch('subprocess.run') as mock_run:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_run.return_value = mock_result
                provider = BubblewrapProvider(log_manager=self.log_manager)
                assert provider is not None
    
    def test_initialization_with_parameters(self):
        """Test provider initialization with various parameters"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                # Test with additional directories
                additional_read_dirs = ["/tmp/test_read"]
                additional_write_dirs = ["/tmp/test_write"]
                environment_variables = {"TEST_VAR": "test_value"}
                
                provider = BubblewrapProvider(
                    log_manager=self.log_manager,
                    additional_read_dirs=additional_read_dirs,
                    additional_write_dirs=additional_write_dirs,
                    environment_variables=environment_variables
                )
                
                # Check that directories are normalized
                assert len(provider.additional_read_dirs) == 1
                assert len(provider.additional_write_dirs) == 1
                assert provider.environment_variables == environment_variables
    
    def test_sandbox_tmp_dir_creation(self):
        """Test sandbox temporary directory creation"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                with patch('os.makedirs') as mock_makedirs:
                    provider = BubblewrapProvider(log_manager=self.log_manager)
                    # Should have created temp directory
                    mock_makedirs.assert_called()
                    assert provider.sandbox_tmp_dir.startswith("/tmp/tinyagent_bw_")
    
    def test_environment_variable_management(self):
        """Test environment variable management methods"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                provider = BubblewrapProvider(log_manager=self.log_manager)
                
                # Test adding environment variable
                provider.add_environment_variable("TEST_KEY", "test_value")
                assert provider.environment_variables["TEST_KEY"] == "test_value"
                
                # Test setting multiple environment variables
                new_vars = {"VAR1": "value1", "VAR2": "value2"}
                provider.set_environment_variables(new_vars)
                assert provider.environment_variables == new_vars
                
                # Test removing environment variable
                provider.remove_environment_variable("VAR1")
                assert "VAR1" not in provider.environment_variables
                assert "VAR2" in provider.environment_variables
    
    def test_get_sandbox_environment(self):
        """Test sandbox environment generation"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                provider = BubblewrapProvider(log_manager=self.log_manager)
                provider.environment_variables = {"CUSTOM_VAR": "custom_value"}
                
                env = provider._get_sandbox_environment()
                
                # Check essential variables are present
                assert "PATH" in env
                assert "HOME" in env
                assert "USER" in env
                assert "CUSTOM_VAR" in env
                assert env["CUSTOM_VAR"] == "custom_value"
                assert env["HOME"] == provider.sandbox_tmp_dir
    
    def test_build_bubblewrap_command(self):
        """Test bubblewrap command generation"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                with patch('os.path.exists', return_value=True):  # Mock all paths as existing
                    provider = BubblewrapProvider(log_manager=self.log_manager)
                    
                    exec_command = ["python3", "-c", "print('hello')"]
                    bwrap_cmd = provider._build_bubblewrap_command(exec_command)
                    
                    # Check basic bubblewrap structure
                    assert bwrap_cmd[0] == "bwrap"
                    assert "--die-with-parent" in bwrap_cmd
                    assert "--unshare-user" in bwrap_cmd
                    assert "--unshare-pid" in bwrap_cmd
                    assert "--unshare-net" in bwrap_cmd  # Network disabled by default
                    assert exec_command[-3:] == bwrap_cmd[-3:]  # Command at end
    
    def test_build_bubblewrap_command_with_network(self):
        """Test bubblewrap command generation with network enabled"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                with patch('os.path.exists', return_value=True):
                    provider = BubblewrapProvider(log_manager=self.log_manager)
                    
                    exec_command = ["curl", "https://example.com"]
                    bwrap_cmd = provider._build_bubblewrap_command(exec_command, enable_network=True)
                    
                    # Network should be enabled (no --unshare-net)
                    assert "--unshare-net" not in bwrap_cmd
    
    def test_quote_command_for_shell(self):
        """Test shell command quoting"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                provider = BubblewrapProvider(log_manager=self.log_manager)
                
                # Test simple command
                command = ["echo", "hello world"]
                quoted = provider._quote_command_for_shell(command)
                assert quoted == "echo 'hello world'"
                
                # Test command with special characters
                command = ["echo", "hello; rm -rf /"]
                quoted = provider._quote_command_for_shell(command)
                assert "rm -rf /" in quoted and quoted.count("'") >= 2
    
    @pytest.mark.asyncio
    async def test_execute_python_basic(self):
        """Test basic Python execution"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                provider = BubblewrapProvider(log_manager=self.log_manager)
                
                # Mock the subprocess execution
                with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                    # Mock process
                    mock_process = Mock()
                    mock_process.communicate = AsyncMock(return_value=(
                        b'{"printed_output": "Hello World", "return_value": null, "stderr": "", "error_traceback": null}',
                        b''
                    ))
                    mock_process.returncode = 0
                    mock_subprocess.return_value = mock_process
                    
                    # Mock file operations
                    with patch('tempfile.NamedTemporaryFile'):
                        with patch('os.path.exists', return_value=False):  # No state file
                            result = await provider.execute_python(["print('Hello World')"])
                            
                            assert result["printed_output"] == "Hello World"
                            assert result["error_traceback"] is None
    
    @pytest.mark.asyncio
    async def test_execute_python_timeout(self):
        """Test Python execution timeout"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                provider = BubblewrapProvider(log_manager=self.log_manager)
                
                # Mock timeout scenario
                with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                    mock_process = Mock()
                    mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
                    mock_process.kill = Mock()
                    mock_subprocess.return_value = mock_process
                    
                    with patch('tempfile.NamedTemporaryFile'):
                        result = await provider.execute_python(["import time; time.sleep(10)"], timeout=1)
                        
                        assert "timed out" in result["stderr"]
                        assert "timed out" in result["error_traceback"]
                        mock_process.kill.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_shell_basic(self):
        """Test basic shell command execution"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                provider = BubblewrapProvider(log_manager=self.log_manager)
                
                # Mock the subprocess execution
                with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                    mock_process = Mock()
                    mock_process.communicate = AsyncMock(return_value=(b'Hello World\n', b''))
                    mock_process.returncode = 0
                    mock_subprocess.return_value = mock_process
                    
                    result = await provider.execute_shell(["echo", "Hello World"])
                    
                    assert result["stdout"].strip() == "Hello World"
                    assert result["exit_code"] == 0
    
    @pytest.mark.asyncio
    async def test_execute_shell_unsafe_command(self):
        """Test shell command safety checks"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                # Create provider with safety enabled
                provider = BubblewrapProvider(log_manager=self.log_manager, bypass_shell_safety=False)
                
                result = await provider.execute_shell(["rm", "-rf", "/"])
                
                assert result["exit_code"] == 1
                assert "security reasons" in result["stderr"]
    
    @pytest.mark.asyncio
    async def test_execute_shell_git_command(self):
        """Test git command execution with special handling"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                provider = BubblewrapProvider(log_manager=self.log_manager)
                
                with patch.object(provider, '_prepare_git_sandbox_command') as mock_git_prep:
                    mock_git_prep.return_value = ["bwrap", "git", "status"]
                    
                    with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                        mock_process = Mock()
                        mock_process.communicate = AsyncMock(return_value=(b'On branch main\n', b''))
                        mock_process.returncode = 0
                        mock_subprocess.return_value = mock_process
                        
                        result = await provider.execute_shell(["git", "status"])
                        
                        mock_git_prep.assert_called_once_with(["git", "status"])
                        assert result["exit_code"] == 0
    
    def test_is_supported_linux(self):
        """Test is_supported on Linux with bubblewrap"""
        with patch('platform.system', return_value="Linux"):
            with patch('subprocess.run') as mock_run:
                # Bubblewrap available
                mock_run.return_value = Mock()
                assert BubblewrapProvider.is_supported() is True
                
                # Bubblewrap not available
                mock_run.side_effect = subprocess.CalledProcessError(1, 'which')
                assert BubblewrapProvider.is_supported() is False
    
    def test_is_supported_non_linux(self):
        """Test is_supported on non-Linux systems"""
        with patch('platform.system', return_value="Darwin"):
            assert BubblewrapProvider.is_supported() is False
        
        with patch('platform.system', return_value="Windows"):
            assert BubblewrapProvider.is_supported() is False
    
    @pytest.mark.asyncio
    async def test_cleanup(self):
        """Test cleanup functionality"""
        with patch('platform.system', return_value="Linux"):
            with patch.object(BubblewrapProvider, '_check_bubblewrap_availability', return_value=True):
                provider = BubblewrapProvider(log_manager=self.log_manager)
                
                # Set some state
                provider.executed_default_codes = True
                provider._globals_dict = {"test": "value"}
                provider._locals_dict = {"local": "value"}
                
                with patch('shutil.rmtree') as mock_rmtree:
                    with patch('os.path.isdir', return_value=True):
                        await provider.cleanup()
                        
                        # Check state is reset
                        assert provider.executed_default_codes is False
                        assert provider._globals_dict == {}
                        assert provider._locals_dict == {}
                        
                        # Check temp dir cleanup
                        mock_rmtree.assert_called_once()


class AsyncMock:
    """Helper class for mocking async functions in older Python versions"""
    
    def __init__(self, return_value=None, side_effect=None):
        self.return_value = return_value
        self.side_effect = side_effect
    
    async def __call__(self, *args, **kwargs):
        if self.side_effect:
            if isinstance(self.side_effect, Exception):
                raise self.side_effect
            else:
                return self.side_effect(*args, **kwargs)
        return self.return_value


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])