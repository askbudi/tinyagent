"""
Docker Image Builder for TinyAgent

Provides flexible Docker image configuration with builder patterns for custom environments.
"""
import os
import tempfile
import hashlib
from typing import Dict, List, Optional, Union, Any
from pathlib import Path


class DockerImageBuilder:
    """
    Builder for creating custom Docker images with user specifications.
    
    Provides a fluent API for configuring Docker images with system packages,
    Python packages, custom commands, and environment variables.
    """
    
    def __init__(self, base_image: str = "python:3.11-slim"):
        """
        Initialize the Docker image builder.
        
        Args:
            base_image: Base Docker image to build from
        """
        self.base_image = base_image
        self.system_packages = []
        self.pip_packages = []
        self.custom_commands = []
        self.environment_vars = {}
        self.working_directory = "/workspace"
        self.user_id = 1000
        self.user_name = "tinyagent"
        self.copy_files = {}  # source_path -> container_path
        self.expose_ports = []
        self.volumes = []
        
    def add_system_packages(self, *packages: str) -> 'DockerImageBuilder':
        """
        Add system packages to be installed via apt-get.
        
        Args:
            *packages: Package names to install
            
        Returns:
            Self for method chaining
        """
        self.system_packages.extend(packages)
        return self
    
    def add_python_packages(self, *packages: str) -> 'DockerImageBuilder':
        """
        Add Python packages to be installed via pip.
        
        Args:
            *packages: Package names to install
            
        Returns:
            Self for method chaining
        """
        self.pip_packages.extend(packages)
        return self
    
    def add_custom_command(self, command: str) -> 'DockerImageBuilder':
        """
        Add a custom RUN command to the Dockerfile.
        
        Args:
            command: Shell command to execute during build
            
        Returns:
            Self for method chaining
        """
        self.custom_commands.append(command)
        return self
    
    def set_environment(self, **env_vars: str) -> 'DockerImageBuilder':
        """
        Set environment variables in the container.
        
        Args:
            **env_vars: Environment variables as key-value pairs
            
        Returns:
            Self for method chaining
        """
        self.environment_vars.update(env_vars)
        return self
    
    def set_working_directory(self, path: str) -> 'DockerImageBuilder':
        """
        Set the working directory in the container.
        
        Args:
            path: Working directory path
            
        Returns:
            Self for method chaining
        """
        self.working_directory = path
        return self
    
    def set_user(self, user_id: int = 1000, user_name: str = "tinyagent") -> 'DockerImageBuilder':
        """
        Set the user for container execution.
        
        Args:
            user_id: User ID number
            user_name: Username
            
        Returns:
            Self for method chaining
        """
        self.user_id = user_id
        self.user_name = user_name
        return self
    
    def copy_file(self, source_path: str, container_path: str) -> 'DockerImageBuilder':
        """
        Copy a file or directory into the container during build.
        
        Args:
            source_path: Path on host system
            container_path: Destination path in container
            
        Returns:
            Self for method chaining
        """
        self.copy_files[source_path] = container_path
        return self
    
    def expose_port(self, port: int) -> 'DockerImageBuilder':
        """
        Expose a port in the container.
        
        Args:
            port: Port number to expose
            
        Returns:
            Self for method chaining
        """
        self.expose_ports.append(port)
        return self
    
    def add_volume(self, path: str) -> 'DockerImageBuilder':
        """
        Add a volume mount point.
        
        Args:
            path: Path to create as volume mount point
            
        Returns:
            Self for method chaining
        """
        self.volumes.append(path)
        return self
    
    def generate_dockerfile(self) -> str:
        """
        Generate Dockerfile content based on configuration.
        
        Returns:
            Dockerfile content as string
        """
        lines = []
        
        # Base image
        lines.append(f"FROM {self.base_image}")
        lines.append("")
        
        # System packages installation
        if self.system_packages:
            lines.append("# Install system packages")
            packages_str = " \\\n    ".join(self.system_packages)
            lines.append(f"RUN apt-get update && apt-get install -y \\")
            lines.append(f"    {packages_str} \\")
            lines.append("    && rm -rf /var/lib/apt/lists/*")
            lines.append("")
        
        # Python packages installation
        if self.pip_packages:
            lines.append("# Install Python packages")
            packages_str = " \\\n    ".join(self.pip_packages)
            lines.append(f"RUN pip install --no-cache-dir \\")
            lines.append(f"    {packages_str}")
            lines.append("")
        
        # Environment variables
        if self.environment_vars:
            lines.append("# Set environment variables")
            for key, value in self.environment_vars.items():
                lines.append(f"ENV {key}={value}")
            lines.append("")
        
        # Copy files
        if self.copy_files:
            lines.append("# Copy files")
            for source, dest in self.copy_files.items():
                lines.append(f"COPY {source} {dest}")
            lines.append("")
        
        # Custom commands
        if self.custom_commands:
            lines.append("# Custom commands")
            for command in self.custom_commands:
                lines.append(f"RUN {command}")
            lines.append("")
        
        # Create user and set permissions
        lines.append("# Create non-root user")
        lines.append(f"RUN useradd -m -u {self.user_id} {self.user_name}")
        
        # Create working directory and set permissions
        lines.append(f"RUN mkdir -p {self.working_directory}")
        lines.append(f"RUN chown -R {self.user_name}:{self.user_name} {self.working_directory}")
        
        # Create volume mount points
        for volume in self.volumes:
            lines.append(f"RUN mkdir -p {volume}")
            lines.append(f"RUN chown -R {self.user_name}:{self.user_name} {volume}")
        
        lines.append("")
        
        # Expose ports
        if self.expose_ports:
            lines.append("# Expose ports")
            for port in self.expose_ports:
                lines.append(f"EXPOSE {port}")
            lines.append("")
        
        # Volume declarations
        if self.volumes:
            lines.append("# Volume mount points")
            for volume in self.volumes:
                lines.append(f"VOLUME {volume}")
            lines.append("")
        
        # Switch to non-root user
        lines.append(f"USER {self.user_name}")
        lines.append(f"WORKDIR {self.working_directory}")
        lines.append("")
        
        # Health check
        lines.append("# Health check")
        lines.append("HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\")
        lines.append('    CMD python3 -c "print(\'Container healthy\')" || exit 1')
        lines.append("")
        
        # Default command
        lines.append('CMD ["python3"]')
        
        return "\n".join(lines)
    
    def get_image_tag(self) -> str:
        """
        Generate a unique image tag based on configuration.
        
        Returns:
            Docker image tag
        """
        # Create a hash of the configuration for uniqueness
        config_str = (
            f"{self.base_image}|"
            f"{'|'.join(sorted(self.system_packages))}|"
            f"{'|'.join(sorted(self.pip_packages))}|"
            f"{'|'.join(self.custom_commands)}|"
            f"{'|'.join(f'{k}={v}' for k, v in sorted(self.environment_vars.items()))}|"
            f"{self.working_directory}|{self.user_id}|{self.user_name}"
        )
        
        config_hash = hashlib.md5(config_str.encode()).hexdigest()[:12]
        
        # Create a readable tag
        base_name = self.base_image.split(':')[0].replace('/', '-')
        return f"tinyagent-{base_name}-{config_hash}"
    
    def save_dockerfile(self, path: Optional[str] = None) -> str:
        """
        Save the generated Dockerfile to a file.
        
        Args:
            path: Optional path to save the Dockerfile. If None, creates a temporary file.
            
        Returns:
            Path to the saved Dockerfile
        """
        dockerfile_content = self.generate_dockerfile()
        
        if path is None:
            # Create temporary file
            fd, path = tempfile.mkstemp(suffix='.Dockerfile', prefix='tinyagent_')
            with os.fdopen(fd, 'w') as f:
                f.write(dockerfile_content)
        else:
            # Save to specified path
            with open(path, 'w') as f:
                f.write(dockerfile_content)
        
        return path


class DockerConfigBuilder:
    """
    Builder for creating DockerProvider configuration with high-level options.
    
    Provides an easy-to-use interface for common Docker configuration scenarios
    without requiring detailed Docker knowledge.
    """
    
    def __init__(self):
        """Initialize the configuration builder."""
        self.image_builder = DockerImageBuilder()
        self.docker_config = {
            "memory_limit": "512m",
            "cpu_limit": "1.0",
            "enable_network": False,
            "auto_pull_image": True,
            "timeout": 300,
        }
        self.working_directory = None
        self.environment_vars = {}
        self.volume_mounts = {}
    
    def for_data_science(self) -> 'DockerConfigBuilder':
        """
        Configure for data science workloads.
        
        Returns:
            Self for method chaining
        """
        self.image_builder.add_python_packages(
            "numpy", "pandas", "matplotlib", "seaborn", "jupyter",
            "scikit-learn", "scipy", "plotly"
        )
        self.image_builder.add_system_packages("git", "curl")
        self.docker_config["memory_limit"] = "2g"
        self.docker_config["cpu_limit"] = "2.0"
        return self
    
    def for_web_development(self) -> 'DockerConfigBuilder':
        """
        Configure for web development workloads.
        
        Returns:
            Self for method chaining
        """
        self.image_builder.add_python_packages(
            "fastapi", "flask", "django", "requests", "aiohttp"
        )
        self.image_builder.add_system_packages("git", "curl", "nodejs", "npm")
        self.docker_config["enable_network"] = True
        self.image_builder.expose_port(8000)
        return self
    
    def for_machine_learning(self) -> 'DockerConfigBuilder':
        """
        Configure for machine learning workloads.
        
        Returns:
            Self for method chaining
        """
        self.image_builder.add_python_packages(
            "torch", "tensorflow", "numpy", "pandas", "scikit-learn",
            "matplotlib", "seaborn", "jupyter"
        )
        self.image_builder.add_system_packages("git", "curl")
        self.docker_config["memory_limit"] = "4g"
        self.docker_config["cpu_limit"] = "4.0"
        return self
    
    def for_system_administration(self) -> 'DockerConfigBuilder':
        """
        Configure for system administration tasks.
        
        Returns:
            Self for method chaining
        """
        self.image_builder.add_python_packages(
            "paramiko", "fabric", "ansible", "docker", "kubernetes"
        )
        self.image_builder.add_system_packages(
            "git", "curl", "wget", "vim", "nano", "htop", "jq"
        )
        self.docker_config["enable_network"] = True
        return self
    
    def with_custom_packages(self, system_packages: List[str] = None, 
                           python_packages: List[str] = None) -> 'DockerConfigBuilder':
        """
        Add custom packages.
        
        Args:
            system_packages: System packages to install
            python_packages: Python packages to install
            
        Returns:
            Self for method chaining
        """
        if system_packages:
            self.image_builder.add_system_packages(*system_packages)
        if python_packages:
            self.image_builder.add_python_packages(*python_packages)
        return self
    
    def with_resources(self, memory: str = "512m", cpus: str = "1.0") -> 'DockerConfigBuilder':
        """
        Set resource limits.
        
        Args:
            memory: Memory limit (e.g., "1g", "512m")
            cpus: CPU limit (e.g., "1.0", "0.5")
            
        Returns:
            Self for method chaining
        """
        self.docker_config["memory_limit"] = memory
        self.docker_config["cpu_limit"] = cpus
        return self
    
    def with_network_access(self, enabled: bool = True) -> 'DockerConfigBuilder':
        """
        Enable or disable network access.
        
        Args:
            enabled: Whether to enable network access
            
        Returns:
            Self for method chaining
        """
        self.docker_config["enable_network"] = enabled
        return self
    
    def with_working_directory(self, path: str) -> 'DockerConfigBuilder':
        """
        Set the working directory.
        
        Args:
            path: Host path to use as working directory
            
        Returns:
            Self for method chaining
        """
        self.working_directory = path
        return self
    
    def with_environment(self, **env_vars: str) -> 'DockerConfigBuilder':
        """
        Set environment variables.
        
        Args:
            **env_vars: Environment variables as key-value pairs
            
        Returns:
            Self for method chaining
        """
        self.environment_vars.update(env_vars)
        self.image_builder.set_environment(**env_vars)
        return self
    
    def build_config(self) -> Dict[str, Any]:
        """
        Build the final configuration dictionary.
        
        Returns:
            Configuration dictionary for DockerProvider
        """
        config = self.docker_config.copy()
        
        # Build custom image if needed
        if (self.image_builder.system_packages or 
            self.image_builder.pip_packages or 
            self.image_builder.custom_commands or
            self.image_builder.environment_vars):
            
            # Generate custom image
            config["docker_image"] = self.image_builder.get_image_tag()
            config["dockerfile_content"] = self.image_builder.generate_dockerfile()
            config["build_image"] = True
        
        # Add working directory if specified
        if self.working_directory:
            config["working_directory"] = self.working_directory
        
        # Add environment variables
        if self.environment_vars:
            config["environment_variables"] = self.environment_vars
        
        return config


# Convenience functions for common configurations
def data_science_config(working_directory: str = None, **kwargs) -> Dict[str, Any]:
    """
    Create a data science configuration.
    
    Args:
        working_directory: Working directory path
        **kwargs: Additional configuration options
        
    Returns:
        Configuration dictionary
    """
    builder = DockerConfigBuilder().for_data_science()
    if working_directory:
        builder.with_working_directory(working_directory)
    
    config = builder.build_config()
    config.update(kwargs)
    return config


def web_development_config(working_directory: str = None, **kwargs) -> Dict[str, Any]:
    """
    Create a web development configuration.
    
    Args:
        working_directory: Working directory path
        **kwargs: Additional configuration options
        
    Returns:
        Configuration dictionary
    """
    builder = DockerConfigBuilder().for_web_development()
    if working_directory:
        builder.with_working_directory(working_directory)
    
    config = builder.build_config()
    config.update(kwargs)
    return config


def machine_learning_config(working_directory: str = None, **kwargs) -> Dict[str, Any]:
    """
    Create a machine learning configuration.
    
    Args:
        working_directory: Working directory path
        **kwargs: Additional configuration options
        
    Returns:
        Configuration dictionary
    """
    builder = DockerConfigBuilder().for_machine_learning()
    if working_directory:
        builder.with_working_directory(working_directory)
    
    config = builder.build_config()
    config.update(kwargs)
    return config