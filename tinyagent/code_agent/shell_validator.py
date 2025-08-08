"""
Simple shell command validator inspired by gemini-cli approach.
Focuses on security through blocklists rather than complex command reconstruction.
"""

import re
from typing import Dict, List, Set, Optional, Any, NamedTuple
from dataclasses import dataclass


class ValidationResult(NamedTuple):
    """Result of shell command validation."""
    allowed: bool
    reason: str = ""
    blocked_pattern: Optional[str] = None


@dataclass
class SecurityConfig:
    """Configuration for shell command security patterns."""
    
    # Commands that are always allowed (basic, safe commands)
    allowed_commands: Set[str]
    
    # Commands that are always blocked (dangerous commands)  
    blocked_commands: Set[str]
    
    # Regex patterns that are always blocked (dangerous patterns)
    dangerous_patterns: List[str]
    
    # Whether to enable strict mode (block unknown commands)
    strict_mode: bool = False


class SimpleShellValidator:
    """
    Simple shell command validator based on gemini-cli approach.
    
    Uses allowlists, blocklists, and dangerous pattern detection
    instead of complex command reconstruction.
    """
    
    def __init__(self, config: SecurityConfig):
        """Initialize validator with security configuration."""
        self.config = config
        
        # Compile regex patterns for performance
        self.compiled_patterns = [
            (pattern, re.compile(pattern, re.IGNORECASE))
            for pattern in config.dangerous_patterns
        ]
    
    def validate_command(self, command: str) -> ValidationResult:
        """
        Validate a shell command using simple pattern matching.
        
        Args:
            command: Shell command string to validate
            
        Returns:
            ValidationResult indicating if command is allowed
        """
        if not command or not command.strip():
            return ValidationResult(False, "Empty command")
        
        # Step 1: Check for dangerous patterns (highest priority)
        for pattern_str, compiled_pattern in self.compiled_patterns:
            if compiled_pattern.search(command):
                return ValidationResult(
                    False, 
                    f"Command blocked due to dangerous pattern: {pattern_str}",
                    pattern_str
                )
        
        # Step 2: Extract root command for allowlist/blocklist check
        root_command = self._extract_root_command(command)
        
        if not root_command:
            return ValidationResult(False, "Could not extract root command")
        
        # Step 3: Check blocklist (blocks take precedence)
        if root_command in self.config.blocked_commands:
            return ValidationResult(
                False, 
                f"Command '{root_command}' is explicitly blocked"
            )
        
        # Step 4: Check allowlist
        if root_command in self.config.allowed_commands:
            return ValidationResult(True)
        
        # Step 5: Handle unknown commands based on strict mode
        if self.config.strict_mode:
            return ValidationResult(
                False, 
                f"Command '{root_command}' not in allowlist (strict mode)"
            )
        else:
            # In permissive mode, allow unknown commands
            return ValidationResult(True)
    
    def _extract_root_command(self, command: str) -> Optional[str]:
        """
        Extract the root command from a shell command string.
        
        Uses simple regex matching like gemini-cli.
        """
        # Handle quoted commands
        quoted_match = re.match(r'^"([^"]+)"|^\'([^\']+)\'|^(\S+)', command.strip())
        if quoted_match:
            return quoted_match.group(1) or quoted_match.group(2) or quoted_match.group(3)
        
        # Handle unquoted commands  
        parts = command.strip().split()
        if parts:
            return parts[0]
        
        return None


def create_default_security_config(provider_type: str = "seatbelt") -> SecurityConfig:
    """Create default security configuration based on provider type."""
    
    # Basic safe commands that are generally allowed
    base_allowed_commands = {
        "ls", "cat", "head", "tail", "wc", "sort", "uniq", "grep", "find",
        "pwd", "echo", "date", "whoami", "which", "type",
        "git", "python", "python3", "pip", "npm", "node", "curl", "wget",
        "rg", "fd", "bat", "exa", "tree", "du", "df"
    }
    
    # Commands that should be blocked for security
    base_blocked_commands = {
        "rm", "sudo", "su", "chmod", "chown", "chgrp", 
        "mount", "umount", "fdisk", "mkfs", "dd", "format",
        "passwd", "useradd", "userdel", "usermod", "groupadd",
        "systemctl", "service", "init", "reboot", "shutdown", "halt"
    }
    
    # Dangerous patterns that should always be blocked
    base_dangerous_patterns = [
        # Command substitution (high risk)
        r'\$\(',                    # $(command)
        r'<\(',                     # <(command) 
        r'`[^`]*`',                 # `command`
        
        # Dangerous redirects
        r'>\s*/dev/',               # > /dev/...
        r'>\s*/etc/',               # > /etc/...
        r'>\s*/usr/',               # > /usr/...
        r'>\s*/bin/',               # > /bin/...
        r'>\s*/sbin/',              # > /sbin/...
        
        # Shell injection patterns
        r'\|\s*(sh|bash|zsh|fish)', # | sh, | bash, etc.
        r';\s*(sh|bash|zsh|fish)',  # ; sh, ; bash, etc.
        r'&&\s*(sh|bash|zsh|fish)', # && sh, && bash, etc.
        
        # Network/privilege escalation
        r'sudo\s+',                 # sudo commands
        r'su\s+',                   # su commands  
        r'curl.*\|\s*(sh|bash)',    # curl ... | sh
        r'wget.*\|\s*(sh|bash)',    # wget ... | sh
        
        # File system manipulation
        r'rm\s+.*-rf',              # rm -rf commands
        r'chmod\s+777',             # chmod 777 (dangerous permissions)
        
        # Process manipulation
        r'kill\s+-9',               # kill -9 (force kill)
        r'killall',                 # killall command
        
        # Dangerous heredoc patterns
        r'<<.*EOF.*rm\s+',          # Heredoc with rm commands
        r'<<.*EOF.*sudo\s+',        # Heredoc with sudo
    ]
    
    # Provider-specific configurations
    if provider_type.lower() == "seatbelt":
        # Seatbelt has additional OS-level protections, so we can be more permissive
        allowed_commands = base_allowed_commands | {
            "open", "pbcopy", "pbpaste", "say", "osascript",  # macOS specific
            "brew", "port", "softwareupdate"  # Package managers
        }
        strict_mode = False
        
    elif provider_type.lower() == "modal":
        # Modal is remote execution, so be more restrictive
        allowed_commands = base_allowed_commands.copy()
        # Remove potentially problematic commands in remote environment
        allowed_commands.discard("curl")
        allowed_commands.discard("wget") 
        strict_mode = True
        
    else:
        # Default configuration
        allowed_commands = base_allowed_commands
        strict_mode = False
    
    return SecurityConfig(
        allowed_commands=allowed_commands,
        blocked_commands=base_blocked_commands,
        dangerous_patterns=base_dangerous_patterns,
        strict_mode=strict_mode
    )


def create_validator_from_provider_config(provider_config: Dict[str, Any]) -> SimpleShellValidator:
    """
    Create a shell validator from provider configuration.
    
    Args:
        provider_config: Provider configuration dict with 'provider_type' key
        
    Returns:
        Configured SimpleShellValidator
    """
    provider_type = provider_config.get('provider_type', 'seatbelt')
    
    # Start with default configuration
    security_config = create_default_security_config(provider_type)
    
    # Apply user customizations from provider config
    if 'shell_security' in provider_config:
        shell_config = provider_config['shell_security']
        
        # Add user-specified allowed commands
        if 'additional_allowed_commands' in shell_config:
            security_config.allowed_commands.update(shell_config['additional_allowed_commands'])
        
        # Add user-specified blocked commands  
        if 'additional_blocked_commands' in shell_config:
            security_config.blocked_commands.update(shell_config['additional_blocked_commands'])
        
        # Add user-specified dangerous patterns
        if 'additional_dangerous_patterns' in shell_config:
            security_config.dangerous_patterns.extend(shell_config['additional_dangerous_patterns'])
        
        # Override strict mode if specified
        if 'strict_mode' in shell_config:
            security_config.strict_mode = shell_config['strict_mode']
    
    # Legacy support for existing provider config keys
    if 'additional_safe_shell_commands' in provider_config:
        security_config.allowed_commands.update(provider_config['additional_safe_shell_commands'])
    
    return SimpleShellValidator(security_config)


# Example configurations for different use cases
def create_development_config() -> SecurityConfig:
    """Create a permissive configuration suitable for development."""
    config = create_default_security_config("seatbelt")
    
    # Add development tools
    config.allowed_commands.update({
        "make", "cmake", "gcc", "clang", "rustc", "cargo", "go",
        "docker", "docker-compose", "kubectl", "helm",
        "yarn", "pnpm", "bun", "deno", "pytest", "jest", "mvn", "gradle"
    })
    
    # Remove some restrictions for development
    config.strict_mode = False
    
    return config


def create_production_config() -> SecurityConfig:
    """Create a restrictive configuration suitable for production."""
    config = create_default_security_config("modal")
    
    # Very restrictive - only basic commands allowed
    config.allowed_commands = {
        "ls", "cat", "head", "tail", "wc", "grep", "find", "pwd", "echo", "date"
    }
    
    # Add more dangerous patterns for production
    config.dangerous_patterns.extend([
        r'wget',                    # Block all wget
        r'curl',                    # Block all curl
        r'python.*-c',              # Block python -c execution
        r'eval',                    # Block eval commands
        r'exec',                    # Block exec commands
    ])
    
    config.strict_mode = True
    
    return config