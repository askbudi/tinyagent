"""
Custom instruction system for TinyAgent.

This module provides functionality to load custom instructions from strings, files,
or automatically detect AGENTS.md files in the execution directory.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union, Dict, Any

logger = logging.getLogger(__name__)


class CustomInstructionError(Exception):
    """Base exception for custom instruction errors."""
    pass


class CustomInstructionLoader:
    """
    Handles loading and processing of custom instructions for TinyAgent.
    
    Features:
    - Load from string or file path
    - Auto-detect AGENTS.md files
    - Enable/disable functionality
    - Placeholder support for system prompts
    - Configurable custom filename/path
    - Control subagent inheritance
    """
    
    def __init__(
        self,
        enabled: bool = True,
        auto_detect_agents_md: bool = True,
        custom_filename: Optional[str] = None,
        inherit_to_subagents: bool = True,
        execution_directory: Optional[str] = None
    ):
        """
        Initialize the custom instruction loader.
        
        Args:
            enabled: Whether custom instruction processing is enabled
            auto_detect_agents_md: Whether to auto-detect AGENTS.md files
            custom_filename: Custom filename to look for (default: "AGENTS.md")
            inherit_to_subagents: Whether subagents inherit custom instructions
            execution_directory: Directory to search for auto-detected files (default: cwd)
        """
        self.enabled = enabled
        self.auto_detect_agents_md = auto_detect_agents_md
        self.custom_filename = custom_filename or "AGENTS.md"
        self.inherit_to_subagents = inherit_to_subagents
        self.execution_directory = Path(execution_directory or os.getcwd())
        
        self._custom_instructions = ""
        self._instruction_source = None
        
        # Log initialization
        if self.enabled:
            logger.info("Custom instruction loader initialized and enabled")
            if self.auto_detect_agents_md:
                logger.debug(f"Auto-detection enabled for '{self.custom_filename}' in {self.execution_directory}")
        else:
            # Only log warning if this seems like an unintentional disable
            # (TinyCodeAgent intentionally disables the parent loader)
            logger.debug("Custom instruction loader initialized but disabled")
    
    def load_instructions(
        self,
        instructions: Optional[Union[str, Path]] = None
    ) -> str:
        """
        Load custom instructions from various sources.
        
        Args:
            instructions: String content, file path, or None for auto-detection
            
        Returns:
            The loaded custom instructions as a string
            
        Raises:
            CustomInstructionError: If loading fails or is disabled
        """
        if not self.enabled:
            logger.debug("Custom instructions are disabled - returning empty string")
            return ""
        
        # Reset state
        self._custom_instructions = ""
        self._instruction_source = None
        
        try:
            # Priority 1: Explicit instructions provided
            if instructions is not None:
                return self._load_from_source(instructions)
            
            # Priority 2: Auto-detection if enabled
            if self.auto_detect_agents_md:
                return self._auto_detect_and_load()
            
            # No instructions found or configured
            logger.debug("No custom instructions provided and auto-detection is disabled")
            return ""
            
        except Exception as e:
            logger.error(f"Failed to load custom instructions: {e}")
            if isinstance(e, CustomInstructionError):
                raise
            raise CustomInstructionError(f"Unexpected error loading custom instructions: {e}") from e
    
    def _load_from_source(self, source: Union[str, Path]) -> str:
        """Load instructions from a string or file path."""
        # Handle Path objects directly
        if isinstance(source, Path):
            if source.exists() and source.is_file():
                return self._load_from_file(source)
            else:
                raise CustomInstructionError(f"File not found: {source}")
        
        # Handle string sources
        elif isinstance(source, str):
            # If string contains newlines or is very long, treat as content
            if '\n' in source or len(source) > 255:
                return self._load_from_string(source)
            
            # Try as path first
            source_path = Path(source)
            if source_path.exists() and source_path.is_file():
                return self._load_from_file(source_path)
            
            # Check if it looks like a path
            if str(source_path).startswith(('/', '.', '~')) and source_path != Path('.'):
                # It looks like a path but doesn't exist
                raise CustomInstructionError(f"File not found: {source_path}")
            else:
                # Treat as string content (including empty strings)
                return self._load_from_string(source)
        
        else:
            raise CustomInstructionError(f"Invalid instruction source type: {type(source)}")
    
    def _load_from_string(self, content: str) -> str:
        """Load instructions from a string."""
        self._custom_instructions = content.strip()
        self._instruction_source = "string"
        
        if self._custom_instructions:
            logger.info("Custom instructions loaded from string")
            logger.debug(f"Loaded {len(self._custom_instructions)} characters from string")
        else:
            logger.warning("Empty custom instructions provided as string")
            
        return self._custom_instructions
    
    def _load_from_file(self, file_path: Path) -> str:
        """Load instructions from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            self._custom_instructions = content
            self._instruction_source = str(file_path)
            
            if self._custom_instructions:
                logger.info(f"Custom instructions loaded from file: {file_path}")
                logger.debug(f"Loaded {len(self._custom_instructions)} characters from {file_path}")
            else:
                logger.warning(f"Custom instruction file is empty: {file_path}")
                
            return self._custom_instructions
            
        except IOError as e:
            raise CustomInstructionError(f"Failed to read custom instruction file {file_path}: {e}") from e
        except UnicodeDecodeError as e:
            raise CustomInstructionError(f"Failed to decode custom instruction file {file_path}: {e}") from e
    
    def _auto_detect_and_load(self) -> str:
        """Auto-detect and load custom instruction files."""
        search_path = self.execution_directory / self.custom_filename
        
        if search_path.exists() and search_path.is_file():
            logger.info(f"Auto-detected custom instruction file: {search_path}")
            return self._load_from_file(search_path)
        else:
            logger.debug(f"No custom instruction file found at: {search_path}")
            return ""
    
    def apply_to_system_prompt(
        self,
        system_prompt: str,
        placeholder: str = "<user_specified_instruction></user_specified_instruction>"
    ) -> str:
        """
        Apply custom instructions to a system prompt by replacing placeholders.
        
        Args:
            system_prompt: The original system prompt
            placeholder: The placeholder to replace with custom instructions
            
        Returns:
            The modified system prompt with custom instructions applied
        """
        if not self.enabled:
            logger.debug("Custom instructions disabled - removing placeholder and returning original system prompt")
            # Remove placeholder even when disabled
            return system_prompt.replace(placeholder, "").strip()
            
        if not self._custom_instructions:
            logger.debug("No custom instructions to apply - removing placeholder")
            # Remove placeholder if it exists but no custom instructions
            return system_prompt.replace(placeholder, "").strip()
        
        if placeholder in system_prompt:
            modified_prompt = system_prompt.replace(placeholder, self._custom_instructions)
            logger.info("Applied custom instructions to system prompt via placeholder")
            logger.debug(f"Replaced placeholder '{placeholder}' with {len(self._custom_instructions)} characters")
            return modified_prompt
        else:
            # Append custom instructions if no placeholder found
            logger.info("No placeholder found - appending custom instructions to system prompt")
            return f"{system_prompt}\n\n<user_specified_instruction>\n{self._custom_instructions}\n</user_specified_instruction>"
    
    def get_instructions(self) -> str:
        """Get the current custom instructions."""
        return self._custom_instructions
    
    def get_instruction_source(self) -> Optional[str]:
        """Get the source of the current custom instructions."""
        return self._instruction_source
    
    def is_enabled(self) -> bool:
        """Check if custom instructions are enabled."""
        return self.enabled
    
    def enable(self, enabled: bool = True) -> None:
        """Enable or disable custom instruction processing."""
        old_state = self.enabled
        self.enabled = enabled
        
        if enabled and not old_state:
            logger.info("Custom instruction processing ENABLED")
        elif not enabled and old_state:
            logger.warning("Custom instruction processing DISABLED")
    
    def set_execution_directory(self, directory: Union[str, Path]) -> None:
        """
        Set the execution directory for auto-detection.
        
        Args:
            directory: New execution directory path
        """
        self.execution_directory = Path(directory)
        logger.debug(f"Execution directory set to: {self.execution_directory}")
    
    def set_custom_filename(self, filename: str) -> None:
        """
        Set the custom filename for auto-detection.
        
        Args:
            filename: New filename to search for
        """
        old_filename = self.custom_filename
        self.custom_filename = filename
        logger.debug(f"Custom filename changed from '{old_filename}' to '{filename}'")
    
    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration as a dictionary."""
        return {
            "enabled": self.enabled,
            "auto_detect_agents_md": self.auto_detect_agents_md,
            "custom_filename": self.custom_filename,
            "inherit_to_subagents": self.inherit_to_subagents,
            "execution_directory": str(self.execution_directory),
            "has_instructions": bool(self._custom_instructions),
            "instruction_source": self._instruction_source
        }


def create_custom_instruction_loader(**kwargs) -> CustomInstructionLoader:
    """
    Factory function to create a CustomInstructionLoader with validation.
    
    Args:
        **kwargs: Arguments to pass to CustomInstructionLoader
        
    Returns:
        Configured CustomInstructionLoader instance
    """
    return CustomInstructionLoader(**kwargs)