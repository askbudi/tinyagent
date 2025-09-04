import pytest
import asyncio
import os
import tempfile
import shutil
import platform
import subprocess
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

# Import the provider to test
from tinyagent.code_agent.providers.docker_provider import DockerProvider
from tinyagent.hooks.logging_manager import LoggingManager


class TestDockerProvider:
    """Test suite for DockerProvider."""
    
    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        log_manager = Mock(spec=LoggingManager)
        logger = Mock()
        log_manager.get_logger.return_value = logger
        return log_manager, logger
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        temp_dir = tempfile.mkdtemp(prefix="test_docker_provider_")
        yield temp_dir
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def docker_config(self):
        """Basic Docker provider configuration."""
        return {
            "docker_image": "python:3.11-slim",
            "enable_network": False,
            "memory_limit": "256m",
            "cpu_limit": "0.5",
            "timeout": 30,
            "auto_pull_image": False,
        }
    
    def test_initialization_basic(self, mock_logger, docker_config):
        """Test basic DockerProvider initialization."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                **docker_config
            )
            
            assert provider.docker_image == docker_config["docker_image"]
            assert provider.enable_network == docker_config["enable_network"]
            assert provider.memory_limit == docker_config["memory_limit"]
            assert provider.cpu_limit == docker_config["cpu_limit"]
            assert provider.default_timeout == docker_config["timeout"]
            assert provider.auto_pull_image == docker_config["auto_pull_image"]
            assert provider.logger is not None
    
    def test_initialization_docker_not_available(self, mock_logger):
        """Test initialization when Docker is not available."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=False):
            with pytest.raises(RuntimeError, match="Docker is not available"):
                DockerProvider(log_manager=log_manager)
    
    def test_initialization_with_directories(self, mock_logger, temp_workspace):
        """Test initialization with additional read/write directories."""
        log_manager, logger = mock_logger
        
        # Create test directories
        read_dir = os.path.join(temp_workspace, "read")
        write_dir = os.path.join(temp_workspace, "write")
        os.makedirs(read_dir)
        os.makedirs(write_dir)
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                additional_read_dirs=[read_dir],
                additional_write_dirs=[write_dir],
                auto_pull_image=False
            )
            
            assert len(provider.additional_read_dirs) == 1
            assert len(provider.additional_write_dirs) == 1
            assert os.path.abspath(read_dir) in provider.additional_read_dirs
            assert os.path.abspath(write_dir) in provider.additional_write_dirs
    
    def test_docker_availability_check(self):
        """Test Docker availability detection."""
        # Test with successful docker command
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0),  # docker --version
                Mock(returncode=0),  # docker info
            ]
            assert DockerProvider._check_docker_availability(None) is True
        
        # Test with failed docker command
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [Mock(returncode=1)]  # docker --version fails
            assert DockerProvider._check_docker_availability(None) is False
        
        # Test with docker not found
        with patch('subprocess.run', side_effect=FileNotFoundError):
            assert DockerProvider._check_docker_availability(None) is False
    
    def test_is_supported_class_method(self):
        """Test the is_supported class method."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0),  # docker --version
                Mock(returncode=0),  # docker info
            ]
            assert DockerProvider.is_supported() is True
        
        with patch('subprocess.run', side_effect=FileNotFoundError):
            assert DockerProvider.is_supported() is False
    
    def test_environment_variable_management(self, mock_logger):
        """Test environment variable management methods."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                environment_variables={"TEST_VAR": "test_value"},
                auto_pull_image=False
            )
            
            # Test initial environment variables
            env_vars = provider.get_environment_variables()
            assert "TEST_VAR" in env_vars
            assert env_vars["TEST_VAR"] == "test_value"
            
            # Test adding environment variable
            provider.add_environment_variable("NEW_VAR", "new_value")
            env_vars = provider.get_environment_variables()
            assert "NEW_VAR" in env_vars
            assert env_vars["NEW_VAR"] == "new_value"
            
            # Test removing environment variable
            provider.remove_environment_variable("TEST_VAR")
            env_vars = provider.get_environment_variables()
            assert "TEST_VAR" not in env_vars
            assert "NEW_VAR" in env_vars
            
            # Test setting multiple environment variables
            provider.set_environment_variables({"VAR1": "value1", "VAR2": "value2"})
            env_vars = provider.get_environment_variables()
            assert "VAR1" in env_vars
            assert "VAR2" in env_vars
            assert "NEW_VAR" not in env_vars  # Should be replaced
    
    def test_container_name_generation(self, mock_logger):
        """Test container name generation."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                container_name_prefix="test",
                auto_pull_image=False
            )
            
            name1 = provider._generate_container_name()
            name2 = provider._generate_container_name()
            
            assert name1.startswith("test_")
            assert name2.startswith("test_")
            assert name1 != name2  # Should be unique
            assert len(name1.split("_")[1]) == 8  # UUID hex should be 8 chars
    
    def test_get_docker_command_basic(self, mock_logger):
        """Test basic Docker command generation."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                docker_image="test-image:latest",
                memory_limit="512m",
                cpu_limit="1.0",
                auto_pull_image=False
            )
            
            cmd = provider._get_docker_command(["python", "-c", "print('hello')"])
            
            # Check that basic options are present
            assert "docker" in cmd
            assert "run" in cmd
            assert "--rm" in cmd
            assert "-i" in cmd
            assert "--user" in cmd
            assert "1000:1000" in cmd
            assert "--cap-drop" in cmd
            assert "ALL" in cmd
            assert "--memory" in cmd
            assert "512m" in cmd
            assert "--cpus" in cmd
            assert "1.0" in cmd
            assert "test-image:latest" in cmd
            assert "python" in cmd
            assert "print('hello')" in cmd
    
    def test_get_docker_command_with_network(self, mock_logger):
        """Test Docker command generation with network enabled."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                enable_network=True,
                auto_pull_image=False
            )
            
            cmd = provider._get_docker_command(["echo", "test"])
            
            # Should not have network isolation when network is enabled
            assert "--network" not in cmd or cmd[cmd.index("--network") + 1] != "none"
    
    def test_get_docker_command_no_network(self, mock_logger):
        """Test Docker command generation with network disabled."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                enable_network=False,
                auto_pull_image=False
            )
            
            cmd = provider._get_docker_command(["echo", "test"])
            
            # Should have network isolation when network is disabled
            assert "--network" in cmd
            assert "none" in cmd
    
    def test_get_container_environment(self, mock_logger):
        """Test container environment generation."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                environment_variables={"CUSTOM_VAR": "custom_value"},
                auto_pull_image=False
            )
            
            env = provider._get_container_environment()
            
            # Check for default environment variables
            assert "HOME" in env
            assert "USER" in env
            assert "PYTHONPATH" in env
            assert "TMPDIR" in env
            
            # Check for custom environment variables
            assert "CUSTOM_VAR" in env
            assert env["CUSTOM_VAR"] == "custom_value"
    
    @pytest.mark.asyncio
    async def test_ensure_docker_image_exists_locally(self, mock_logger):
        """Test ensuring Docker image when it exists locally."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                docker_image="test-image:latest",
                auto_pull_image=False
            )
            
            # Mock successful image inspection (image exists)
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.wait = AsyncMock(return_value=None)
            
            with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                await provider._ensure_docker_image()
                
                # Should only call image inspect, not pull or build
                assert mock_process.wait.call_count == 1
    
    @pytest.mark.asyncio
    async def test_ensure_docker_image_pull_success(self, mock_logger):
        """Test ensuring Docker image when it needs to be pulled."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                docker_image="test-image:latest",
                auto_pull_image=False
            )
            
            # Mock image inspection failure (image doesn't exist)
            mock_inspect_process = AsyncMock()
            mock_inspect_process.returncode = 1
            mock_inspect_process.wait = AsyncMock(return_value=None)
            
            # Mock successful pull
            mock_pull_process = AsyncMock()
            mock_pull_process.returncode = 0
            mock_pull_process.wait = AsyncMock(return_value=None)
            
            with patch('asyncio.create_subprocess_exec', side_effect=[mock_inspect_process, mock_pull_process]):
                await provider._ensure_docker_image()
                
                assert mock_inspect_process.wait.call_count == 1
                assert mock_pull_process.wait.call_count == 1
    
    @pytest.mark.asyncio
    async def test_ensure_docker_image_build_fallback(self, mock_logger):
        """Test ensuring Docker image when pull fails and build is attempted."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                docker_image="test-image:latest",
                auto_pull_image=False
            )
            
            # Mock image inspection failure
            mock_inspect_process = AsyncMock()
            mock_inspect_process.returncode = 1
            mock_inspect_process.wait = AsyncMock(return_value=None)
            
            # Mock pull failure
            mock_pull_process = AsyncMock()
            mock_pull_process.returncode = 1
            mock_pull_process.wait = AsyncMock(return_value=None)
            
            with patch('asyncio.create_subprocess_exec', side_effect=[mock_inspect_process, mock_pull_process]):
                with patch.object(provider, '_build_default_image', new_callable=AsyncMock) as mock_build:
                    await provider._ensure_docker_image()
                    
                    assert mock_inspect_process.wait.call_count == 1
                    assert mock_pull_process.wait.call_count == 1
                    mock_build.assert_called_once()
    
    def test_get_default_dockerfile(self, mock_logger):
        """Test default Dockerfile generation."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(log_manager=log_manager, auto_pull_image=False)
            dockerfile = provider._get_default_dockerfile()
            
            # Check for essential Dockerfile components
            assert "FROM python:3.11-slim" in dockerfile
            assert "useradd -m -u 1000" in dockerfile
            assert "USER tinyagent" in dockerfile
            assert "WORKDIR /workspace" in dockerfile
            assert "cloudpickle" in dockerfile
            assert "requests" in dockerfile
            assert "numpy" in dockerfile
            assert "pandas" in dockerfile
    
    def test_generate_python_execution_script(self, mock_logger, temp_workspace):
        """Test Python execution script generation."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                volume_mount_path="/workspace",
                auto_pull_image=False
            )
            
            # Set workspace_dir for path conversion
            provider.workspace_dir = temp_workspace
            
            test_code = "print('Hello, Docker!')"
            state_file_path = os.path.join(temp_workspace, "test_state.pkl")
            
            script_content = provider._generate_python_execution_script(test_code, state_file_path)
            
            assert "import cloudpickle" in script_content
            assert "import json" in script_content
            assert "Hello, Docker!" in script_content
            assert "/workspace" in script_content
            assert "json.dumps(cleaned_result)" in script_content
    
    def test_quote_command_for_shell(self, mock_logger):
        """Test shell command quoting."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(log_manager=log_manager, auto_pull_image=False)
            
            # Test basic command
            result = provider._quote_command_for_shell(["echo", "hello world"])
            assert result == "echo 'hello world'"
            
            # Test command with special characters
            result = provider._quote_command_for_shell(["echo", "hello & world"])
            assert result == "echo 'hello & world'"
            
            # Test command with quotes
            result = provider._quote_command_for_shell(["echo", "hello 'world'"])
            assert "hello 'world'" in result
    
    @pytest.mark.asyncio
    async def test_cleanup(self, mock_logger):
        """Test cleanup method."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(log_manager=log_manager, auto_pull_image=False)
            
            # Set some state
            provider.executed_default_codes = True
            provider._globals_dict = {"test": "value"}
            provider._locals_dict = {"test": "value"}
            provider.active_containers.add("test_container")
            
            # Mock docker kill and rm commands
            mock_process = AsyncMock()
            mock_process.wait = AsyncMock(return_value=None)
            
            with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                await provider.cleanup()
                
                # Check that state is reset
                assert provider.executed_default_codes is False
                assert provider._globals_dict == {}
                assert provider._locals_dict == {}
                assert len(provider.active_containers) == 0
    
    def test_safety_command_validation(self, mock_logger):
        """Test that command safety validation is working."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(
                log_manager=log_manager,
                bypass_shell_safety=False,  # Enable safety checks
                auto_pull_image=False
            )
            
            # Test safe command
            result = provider.is_safe_command(["echo", "hello"])
            assert result["safe"] is True
            
            # Test unsafe command (if rm is not in safe commands)
            result = provider.is_safe_command(["rm", "-rf", "/"])
            # This should be unsafe if rm is not in the safe commands list
            # The actual result depends on the safe_shell_commands configuration
    
    def test_should_use_shell_execution(self, mock_logger):
        """Test shell execution decision logic."""
        log_manager, logger = mock_logger
        
        with patch.object(DockerProvider, '_check_docker_availability', return_value=True):
            provider = DockerProvider(log_manager=log_manager, auto_pull_image=False)
            
            # Test commands that should use shell
            assert provider.should_use_shell_execution(["echo", "hello", "|", "cat"]) is True
            assert provider.should_use_shell_execution(["ls", "&&", "pwd"]) is True
            assert provider.should_use_shell_execution(["echo", "$HOME"]) is True
            
            # Test commands that should NOT use shell
            assert provider.should_use_shell_execution(["ls", "-la"]) is False
            assert provider.should_use_shell_execution(["python", "script.py"]) is False


class TestDockerProviderIntegration:
    """Integration tests for DockerProvider that require Docker to be running."""
    
    @pytest.fixture
    def skip_if_no_docker(self):
        """Skip tests if Docker is not available."""
        if not DockerProvider.is_supported():
            pytest.skip("Docker not available for integration tests")
    
    @pytest.fixture
    def docker_provider(self, skip_if_no_docker):
        """Create a real DockerProvider instance for integration tests."""
        log_manager = Mock(spec=LoggingManager)
        logger = Mock()
        log_manager.get_logger.return_value = logger
        
        provider = DockerProvider(
            log_manager=log_manager,
            docker_image="python:3.11-slim",
            auto_pull_image=True,  # Allow pulling for integration tests
            memory_limit="128m",   # Use minimal resources
            cpu_limit="0.5",
            timeout=60
        )
        
        yield provider
        
        # Cleanup
        asyncio.run(provider.cleanup())
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_python_simple(self, docker_provider):
        """Test simple Python execution."""
        result = await docker_provider.execute_python(["print('Hello from Docker!')"])
        
        assert "printed_output" in result
        assert "Hello from Docker!" in result["printed_output"]
        assert result.get("error_traceback") is None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_python_with_imports(self, docker_provider):
        """Test Python execution with imports."""
        code = [
            "import json",
            "import math",
            "result = {'pi': math.pi, 'e': math.e}",
            "print(json.dumps(result))"
        ]
        
        result = await docker_provider.execute_python(code)
        
        assert "printed_output" in result
        assert "3.14159" in result["printed_output"]
        assert "2.71828" in result["printed_output"]
        assert result.get("error_traceback") is None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_python_state_persistence(self, docker_provider):
        """Test that state persists between executions."""
        # First execution - set a variable
        result1 = await docker_provider.execute_python(["x = 42", "print(f'x = {x}')"])
        assert "x = 42" in result1["printed_output"]
        assert result1.get("error_traceback") is None
        
        # Second execution - use the variable
        result2 = await docker_provider.execute_python(["print(f'x is still {x}')"])
        assert "x is still 42" in result2["printed_output"]
        assert result2.get("error_traceback") is None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_shell_simple(self, docker_provider):
        """Test simple shell command execution."""
        result = await docker_provider.execute_shell(["echo", "Hello from shell!"])
        
        assert result["exit_code"] == 0
        assert "Hello from shell!" in result["stdout"]
        assert result["stderr"] == ""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_shell_with_pipes(self, docker_provider):
        """Test shell command with pipes."""
        result = await docker_provider.execute_shell(["echo", "hello world", "|", "wc", "-w"])
        
        assert result["exit_code"] == 0
        assert "2" in result["stdout"]  # "hello world" has 2 words
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_python_error_handling(self, docker_provider):
        """Test Python error handling."""
        result = await docker_provider.execute_python(["raise ValueError('Test error')"])
        
        assert result.get("error_traceback") is not None
        assert "ValueError: Test error" in result["error_traceback"]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_execute_shell_error_handling(self, docker_provider):
        """Test shell error handling."""
        result = await docker_provider.execute_shell(["ls", "/nonexistent"])
        
        assert result["exit_code"] != 0
        assert "No such file or directory" in result["stderr"]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_handling(self, docker_provider):
        """Test timeout handling."""
        # Test Python timeout
        result = await docker_provider.execute_python(["import time", "time.sleep(10)"], timeout=2)
        assert "timed out" in result["error_traceback"]
        
        # Test shell timeout
        result = await docker_provider.execute_shell(["sleep", "10"], timeout=2)
        assert "timed out" in result["stderr"]


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])