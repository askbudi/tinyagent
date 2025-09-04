"""
Tests for Enhanced DockerProvider with dynamic system context and unified API.
"""
import pytest
import asyncio
import os
import tempfile
import json
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from tinyagent.code_agent.providers.docker_provider import DockerProvider
from tinyagent.code_agent.providers.docker_image_builder import (
    DockerImageBuilder, DockerConfigBuilder, data_science_config
)
from tinyagent.hooks.logging_manager import LoggingManager


class TestDockerImageBuilder:
    """Test the DockerImageBuilder class."""
    
    def test_basic_dockerfile_generation(self):
        """Test basic Dockerfile generation."""
        builder = DockerImageBuilder("python:3.11-slim")
        builder.add_system_packages("git", "curl")
        builder.add_python_packages("pandas", "numpy")
        builder.set_environment(PROJECT_ENV="test")
        
        dockerfile = builder.generate_dockerfile()
        
        assert "FROM python:3.11-slim" in dockerfile
        assert "git curl" in dockerfile
        assert "pandas numpy" in dockerfile
        assert "ENV PROJECT_ENV=test" in dockerfile
        assert "USER tinyagent" in dockerfile
        assert "WORKDIR /workspace" in dockerfile
    
    def test_image_tag_generation(self):
        """Test unique image tag generation."""
        builder1 = DockerImageBuilder("python:3.11-slim")
        builder1.add_python_packages("pandas")
        
        builder2 = DockerImageBuilder("python:3.11-slim")
        builder2.add_python_packages("numpy")
        
        tag1 = builder1.get_image_tag()
        tag2 = builder2.get_image_tag()
        
        assert tag1 != tag2
        assert tag1.startswith("tinyagent-python-")
        assert tag2.startswith("tinyagent-python-")
    
    def test_dockerfile_save(self):
        """Test Dockerfile saving to file."""
        builder = DockerImageBuilder()
        builder.add_python_packages("requests")
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            saved_path = builder.save_dockerfile(tmp.name)
            
            assert saved_path == tmp.name
            
            with open(saved_path, 'r') as f:
                content = f.read()
                assert "requests" in content
            
            os.unlink(saved_path)


class TestDockerConfigBuilder:
    """Test the DockerConfigBuilder class."""
    
    def test_data_science_config(self):
        """Test data science configuration template."""
        config = (DockerConfigBuilder()
                 .for_data_science()
                 .build_config())
        
        assert config["memory_limit"] == "2g"
        assert config["cpu_limit"] == "2.0"
        assert "dockerfile_content" in config
        assert "pandas" in config["dockerfile_content"]
        assert "numpy" in config["dockerfile_content"]
    
    def test_web_development_config(self):
        """Test web development configuration template."""
        config = (DockerConfigBuilder()
                 .for_web_development()
                 .build_config())
        
        assert config["enable_network"] is True
        assert "dockerfile_content" in config
        assert "fastapi" in config["dockerfile_content"]
        assert "nodejs" in config["dockerfile_content"]
    
    def test_custom_configuration(self):
        """Test custom configuration building."""
        config = (DockerConfigBuilder()
                 .with_custom_packages(
                     system_packages=["git", "vim"],
                     python_packages=["requests", "click"]
                 )
                 .with_resources(memory="1g", cpus="2.0")
                 .with_network_access(True)
                 .with_working_directory("/custom/path")
                 .with_environment(API_KEY="test", DEBUG="true")
                 .build_config())
        
        assert config["memory_limit"] == "1g"
        assert config["cpu_limit"] == "2.0"
        assert config["enable_network"] is True
        assert config["working_directory"] == "/custom/path"
        assert config["environment_variables"]["API_KEY"] == "test"
        assert "git vim" in config["dockerfile_content"]
        assert "requests click" in config["dockerfile_content"]


class TestEnhancedDockerProvider:
    """Test the enhanced DockerProvider functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_manager = LoggingManager()
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('subprocess.run')
    def test_docker_availability_check(self, mock_run):
        """Test Docker availability checking."""
        # Mock successful Docker check
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        assert DockerProvider.is_supported() is True
        
        # Mock failed Docker check
        mock_run.side_effect = [
            Mock(returncode=1)   # docker --version fails
        ]
        
        assert DockerProvider.is_supported() is False
    
    @patch('subprocess.run')
    def test_initialization_with_working_directory(self, mock_run):
        """Test initialization with working directory parameter."""
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        provider = DockerProvider(
            log_manager=self.log_manager,
            working_directory=self.temp_dir,
            environment_variables={"TEST_VAR": "test_value"}
        )
        
        assert provider.working_directory == os.path.abspath(self.temp_dir)
        assert self.temp_dir in provider.additional_read_dirs
        assert self.temp_dir in provider.additional_write_dirs
        assert provider.environment_variables["TEST_VAR"] == "test_value"
    
    @patch('subprocess.run')
    def test_file_path_resolution(self, mock_run):
        """Test file path resolution for unified API."""
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        provider = DockerProvider(
            log_manager=self.log_manager,
            working_directory=self.temp_dir
        )
        
        # Test relative path
        relative_result = provider._resolve_file_path("test.txt")
        assert relative_result == "/workspace/test.txt"
        
        # Test absolute path within working directory
        test_file = os.path.join(self.temp_dir, "test.txt")
        absolute_result = provider._resolve_file_path(test_file)
        assert absolute_result == "/workspace/test.txt"
        
        # Test absolute path outside working directory (should raise ValueError)
        with pytest.raises(ValueError, match="outside allowed directories"):
            provider._resolve_file_path("/some/other/path/file.txt")
    
    @patch('subprocess.run')
    @patch('asyncio.create_subprocess_exec')
    async def test_container_system_info_gathering(self, mock_subprocess, mock_run):
        """Test dynamic system info gathering from container."""
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        # Mock the container execution for system info
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b'SYSTEM_INFO_JSON:{"cwd": "/workspace", "platform": "Linux", "architecture": "x86_64", "python_version": "3.11.5", "user": "tinyagent", "available_commands": ["git", "curl"]}\\n',
            b''
        )
        mock_subprocess.return_value = mock_process
        
        provider = DockerProvider(
            log_manager=self.log_manager,
            working_directory=self.temp_dir
        )
        
        system_info = await provider._get_container_system_info()
        
        assert system_info["platform"] == "Linux"
        assert system_info["architecture"] == "x86_64"
        assert system_info["python_version"] == "3.11.5"
        assert system_info["user"] == "tinyagent"
        assert "git" in system_info["available_commands"]
        assert "curl" in system_info["available_commands"]
    
    @patch('subprocess.run')
    async def test_dynamic_system_prompt_generation(self, mock_run):
        """Test dynamic system prompt generation."""
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        provider = DockerProvider(
            log_manager=self.log_manager,
            working_directory=self.temp_dir,
            enable_network=True,
            memory_limit="1g",
            cpu_limit="2.0"
        )
        
        # Mock system info
        provider.container_system_info = {
            "cwd": "/workspace",
            "platform": "Linux",
            "architecture": "x86_64",
            "python_version": "3.11.5",
            "user": "tinyagent",
            "available_commands": ["git", "curl", "python3"]
        }
        
        system_prompt = await provider.get_dynamic_system_prompt()
        
        assert "🐳 Container Environment" not in system_prompt  # Should be clean prompt
        assert "Platform: Linux x86_64" in system_prompt
        assert "Python version: 3.11.5" in system_prompt
        assert "Available tools: git, curl, python3" in system_prompt
        assert f"Host directory: {provider.working_directory}" in system_prompt
        assert "Container directory: /workspace" in system_prompt
        assert "Network access: enabled" in system_prompt
        assert "Memory 1g, CPU 2.0" in system_prompt
    
    @patch('subprocess.run')
    async def test_unified_file_operations(self, mock_run):
        """Test unified file operations with path resolution."""
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        provider = DockerProvider(
            log_manager=self.log_manager,
            working_directory=self.temp_dir
        )
        
        # Mock the parent class file operation methods
        with patch.object(provider.__class__.__bases__[0], 'read_file', new_callable=AsyncMock) as mock_read:
            mock_read.return_value = {
                "success": True,
                "content": "test content",
                "path": "/workspace/test.txt",
                "size": 12
            }
            
            # Test reading with relative path
            result = await provider.read_file("test.txt")
            mock_read.assert_called_with("/workspace/test.txt")
            assert result["success"] is True
            assert result["content"] == "test content"
            
            # Test reading with absolute host path
            host_file = os.path.join(self.temp_dir, "test.txt")
            result = await provider.read_file(host_file)
            mock_read.assert_called_with("/workspace/test.txt")
    
    @patch('subprocess.run')
    def test_convenience_factory_methods(self, mock_run):
        """Test convenience factory methods."""
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        # Test data science factory
        ds_provider = DockerProvider.for_data_science(
            working_directory=self.temp_dir,
            environment_variables={"JUPYTER_ENABLE_LAB": "yes"}
        )
        
        assert ds_provider.working_directory == os.path.abspath(self.temp_dir)
        assert ds_provider.memory_limit == "2g"
        assert ds_provider.cpu_limit == "2.0"
        
        # Test web development factory
        web_provider = DockerProvider.for_web_development(
            working_directory=self.temp_dir
        )
        
        assert web_provider.enable_network is True
        assert web_provider.working_directory == os.path.abspath(self.temp_dir)
    
    @patch('subprocess.run')
    async def test_error_handling_in_path_resolution(self, mock_run):
        """Test error handling in file operations with invalid paths."""
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        provider = DockerProvider(
            log_manager=self.log_manager,
            working_directory=self.temp_dir
        )
        
        # Test file operation with invalid path
        result = await provider.read_file("/invalid/path/file.txt")
        
        assert result["success"] is False
        assert "outside allowed directories" in result["error"]
        assert result["path"] == "/invalid/path/file.txt"


class TestDockerProviderIntegration:
    """Integration tests that require Docker (marked for conditional execution)."""
    
    @pytest.mark.integration
    @pytest.mark.skipif(not DockerProvider.is_supported(), reason="Docker not available")
    async def test_real_docker_execution(self):
        """Test actual Docker execution (requires Docker)."""
        provider = DockerProvider(
            docker_image="python:3.11-slim",
            enable_network=False,
            memory_limit="256m",
            timeout=60
        )
        
        try:
            # Test Python execution with context injection
            result = await provider.execute_python([
                "print('Testing container execution')",
                "import platform",
                "print(f'Platform: {platform.system()}')"
            ])
            
            assert "Testing container execution" in result.get("printed_output", "")
            assert "Platform: Linux" in result.get("printed_output", "")
            
        finally:
            await provider.cleanup()
    
    @pytest.mark.integration
    @pytest.mark.skipif(not DockerProvider.is_supported(), reason="Docker not available")
    async def test_real_system_info_gathering(self):
        """Test real system info gathering from container."""
        provider = DockerProvider(
            docker_image="python:3.11-slim",
            timeout=60
        )
        
        try:
            system_info = await provider._get_container_system_info()
            
            assert system_info["platform"] == "Linux"
            assert system_info["user"] == "tinyagent"
            assert system_info["cwd"] == "/workspace"
            assert "python_version" in system_info
            
        finally:
            await provider.cleanup()


class TestBackwardCompatibility:
    """Test backward compatibility with existing DockerProvider usage."""
    
    @patch('subprocess.run')
    def test_legacy_parameter_support(self, mock_run):
        """Test that legacy parameters still work."""
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        # Legacy initialization should still work
        provider = DockerProvider(
            docker_image="custom:latest",
            additional_read_dirs=["/legacy/read"],
            additional_write_dirs=["/legacy/write"],
            environment_variables={"LEGACY_VAR": "value"},
            memory_limit="1g",
            cpu_limit="2.0"
        )
        
        assert provider.docker_image == "custom:latest"
        assert "/legacy/read" in provider.additional_read_dirs
        assert "/legacy/write" in provider.additional_write_dirs
        assert provider.environment_variables["LEGACY_VAR"] == "value"
        assert provider.memory_limit == "1g"
        assert provider.cpu_limit == "2.0"
    
    @patch('subprocess.run')
    async def test_legacy_api_methods(self, mock_run):
        """Test that legacy API methods still work."""
        mock_run.side_effect = [
            Mock(returncode=0),  # docker --version
            Mock(returncode=0)   # docker info
        ]
        
        provider = DockerProvider()
        
        # Legacy environment variable methods should work
        provider.set_environment_variables({"NEW_VAR": "new_value"})
        assert provider.get_environment_variables()["NEW_VAR"] == "new_value"
        
        provider.add_environment_variable("ADDED_VAR", "added_value")
        assert provider.get_environment_variables()["ADDED_VAR"] == "added_value"
        
        provider.remove_environment_variable("ADDED_VAR")
        assert "ADDED_VAR" not in provider.get_environment_variables()


# Convenience function tests
def test_data_science_config_function():
    """Test the data_science_config convenience function."""
    config = data_science_config(
        working_directory="/data/project",
        memory_limit="4g"
    )
    
    assert config["working_directory"] == "/data/project"
    assert config["memory_limit"] == "4g"  # Override
    assert config["cpu_limit"] == "2.0"    # Default from template
    assert "dockerfile_content" in config


if __name__ == "__main__":
    # Run tests with: python -m pytest tests/test_docker_provider_enhanced.py -v
    pytest.main([__file__, "-v"])