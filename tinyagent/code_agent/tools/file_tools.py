"""
File manipulation tools for TinyAgent with sandbox-first, universal hooks approach.

This module provides native file manipulation tools (Read, Write, Update, Search)
that execute within provider sandbox boundaries and integrate with the universal
hook system for tool execution control.
"""

import os
import re
import mimetypes
import fnmatch
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from tinyagent import tool


def sanitize_path(file_path: str) -> str:
    """Normalize a file path to absolute form."""
    return os.path.abspath(file_path)


def _get_current_agent():
    """Best-effort retrieval of the current TinyCodeAgent from the call stack."""
    import inspect
    for frame_info in inspect.stack():
        frame_locals = frame_info.frame.f_locals
        if 'self' in frame_locals:
            obj = frame_locals['self']
            if hasattr(obj, 'code_provider'):
                return obj
    return None


def _extract_match_paths(matches: List[Dict[str, Any]], base_dir: str) -> List[str]:
    """Extract absolute file paths from provider search match structures."""
    paths: List[str] = []
    for m in matches:
        # Seatbelt uses 'file_path', Modal may use 'file' (relative to directory)
        rel = m.get('file_path') or m.get('file') or m.get('full_path') or m.get('path')
        if not rel:
            continue
        # If rel is absolute, keep; else join with base_dir
        abs_path = rel if os.path.isabs(rel) else os.path.join(base_dir, rel)
        # Normalize
        paths.append(os.path.abspath(abs_path))
    # De-duplicate preserving order
    seen = set()
    unique = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def get_logger():
    """Get the logger from the current agent context."""
    import inspect
    
    # Look up the call stack to find a TinyCodeAgent instance with log_manager
    for frame_info in inspect.stack():
        frame_locals = frame_info.frame.f_locals
        if 'self' in frame_locals:
            obj = frame_locals['self']
            if hasattr(obj, 'log_manager') and obj.log_manager:
                return obj.log_manager.get_logger('tinyagent.code_agent.tools.file_tools')
    
    # Fallback to None if no logger found
    return None


def is_text_file(file_path: str) -> bool:
    """
    Check if a file is a text file based on MIME type and content inspection.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if the file appears to be a text file
    """
    try:
        # Check MIME type first
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith('text/'):
            return True
        
        # Check for common text file extensions
        text_extensions = {
            '.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml',
            '.md', '.rst', '.csv', '.sql', '.sh', '.bash', '.zsh', '.fish',
            '.c', '.cpp', '.h', '.java', '.go', '.rs', '.php', '.rb', '.pl',
            '.ts', '.jsx', '.tsx', '.vue', '.svelte', '.ini', '.cfg', '.conf',
            '.log', '.dockerfile', '.gitignore', '.env'
        }
        
        if Path(file_path).suffix.lower() in text_extensions:
            return True
        
        # If no extension or unknown MIME type, check first few bytes
        if os.path.exists(file_path):
            try:
                with open(file_path, 'rb') as f:
                    sample = f.read(1024)
                
                # Check for null bytes (common in binary files)
                if b'\0' in sample:
                    return False
                
                # Try to decode as UTF-8
                try:
                    sample.decode('utf-8')
                    return True
                except UnicodeDecodeError:
                    # Try other common encodings
                    for encoding in ['latin-1', 'ascii', 'cp1252']:
                        try:
                            sample.decode(encoding)
                            return True
                        except UnicodeDecodeError:
                            continue
                    return False
            except (IOError, OSError):
                return False
        
        return False
    except Exception:
        return False


def get_friendly_error_message(error_type: str, file_path: str, additional_info: str = "") -> str:
    """
    Generate LLM-friendly error messages for file operations.
    
    Args:
        error_type: Type of error
        file_path: Path that caused the error
        additional_info: Additional context information
        
    Returns:
        Human-readable error message with suggestions
    """
    error_messages = {
        "binary_file": f"The file '{file_path}' appears to be binary (contains non-text data). I can only read text-based files like source code, configuration files, and documentation. {additional_info}",
        "permission_denied": f"Access denied by sandbox policy. The file '{file_path}' is outside the allowed working directory. {additional_info}",
        "file_not_found": f"The file '{file_path}' was not found. Please check the file path and ensure it exists within the sandbox boundaries. {additional_info}",
        "file_too_large": f"The file '{file_path}' is too large to process. {additional_info} Try reading specific sections using start_line and max_lines parameters.",
        "invalid_path": f"Invalid file path: '{file_path}'. Please use paths relative to the working directory or absolute paths within the sandbox. {additional_info}",
        "encoding_error": f"Could not decode the file '{file_path}' with the specified encoding. {additional_info} Try using a different encoding or check if the file is corrupted.",
        "write_error": f"Failed to write to file '{file_path}'. {additional_info} Check permissions and available disk space.",
        "update_error": f"Failed to update file '{file_path}'. {additional_info} Ensure the old_content matches exactly."
    }
    
    return error_messages.get(error_type, f"An error occurred with file '{file_path}': {additional_info}")


@tool(name="read_file", description="""
Read text file content safely within sandbox boundaries. This tool can only read text-based files and provides helpful error messages for other file types.

Use this tool to:
- Examine source code, configuration files, documentation
- Read log files, data files, and text-based content
- Inspect file contents before making changes
- Understand project structure and file relationships

Options:
- show_line_numbers (bool, optional): If true, prefixes each returned line with its line number. Defaults to true.

The tool respects sandbox security policies and can only access files within allowed directories.
""")
async def read_file(
    file_path: str,
    start_line: int = 1,
    max_lines: Optional[int] = None,
    encoding: str = "utf-8",
    show_line_numbers: bool = True
) -> str:
    """Read text file content via provider sandbox."""
    logger = get_logger()
    
    try:
        if logger:
            logger.debug(f"read_file called with: file_path='{file_path}', start_line={start_line}, max_lines={max_lines}, encoding='{encoding}'")
        
        agent = _get_current_agent()
        if not agent or not hasattr(agent, 'code_provider'):
            return "Error: Code provider not available for sandboxed file operations."

        resp = await agent.code_provider.read_file(
            file_path=file_path,
            start_line=start_line,
            max_lines=max_lines,
            encoding=encoding,
        )

        if resp.get("success"):
            content = resp.get("content", "")
            if show_line_numbers:
                try:
                    lines = content.splitlines()
                    # Determine starting number based on requested start_line
                    starting_number = start_line if (max_lines is not None or start_line > 1) else 1
                    numbered_lines = []
                    for idx, line in enumerate(lines, start=starting_number):
                        numbered_lines.append(f"{idx}→{line}")
                    content = "\n".join(numbered_lines)
                except Exception as _e:
                    # If numbering fails, fall back to raw content
                    if logger:
                        logger.debug(f"Line numbering failed: {_e}")
            if logger:
                logger.debug(f"read_file success: Read {len(content)} characters from '{file_path}'")
            return content
        else:
            error_msg = resp.get("error") or "Unknown error"
            return f"Error: {error_msg}"
            
    except Exception as e:
        if logger:
            logger.debug(f"read_file unexpected error: {str(e)}", exc_info=True)
        return f"Error reading file: {str(e)}"


@tool(name="write_file", description="""
Write content to text files safely within sandbox boundaries. Creates or overwrites files with the specified content. May trigger user review workflows depending on configuration.
""")
async def write_file(
    file_path: str,
    content: str,
    create_dirs: bool = True,
    encoding: str = "utf-8"
) -> str:
    """Write file via provider sandbox."""
    logger = get_logger()
    
    try:
        if logger:
            logger.debug(f"write_file called with: file_path='{file_path}', content_length={len(content)}, create_dirs={create_dirs}, encoding='{encoding}'")
        
        agent = _get_current_agent()
        if not agent or not hasattr(agent, 'code_provider'):
            return "Error: Code provider not available for sandboxed file operations."

        resp = await agent.code_provider.write_file(
            file_path=file_path,
            content=content,
            create_dirs=create_dirs,
            encoding=encoding,
        )

        if resp.get("success"):
            try:
                bytes_written = resp.get("bytes_written") or len(content.encode(encoding))
                lines_written = len(content.splitlines())
                return f"Successfully wrote {lines_written} lines ({bytes_written} bytes) to {sanitize_path(file_path)}"
            except Exception:
                return f"Successfully wrote content to {sanitize_path(file_path)}"
        else:
            error_msg = get_friendly_error_message("write_error", file_path, resp.get("error", ""))
            return f"Error: {error_msg}"
            
    except Exception as e:
        if logger:
            logger.debug(f"write_file unexpected error: {str(e)}", exc_info=True)
        return f"Error writing file: {str(e)}"


@tool(name="update_file", description="""
Update existing text files by replacing specific content within sandbox boundaries. Performs precise string replacements and may trigger user review workflows. Requires exact string matching for safety.
""")
async def update_file(
    file_path: str,
    old_content: str,
    new_content: str,
    expected_matches: int = 1
) -> str:
    """Update file content via provider sandbox using exact string replacement."""
    logger = get_logger()
    
    try:
        if logger:
            logger.debug(f"update_file called with: file_path='{file_path}', old_content_length={len(old_content)}, new_content_length={len(new_content)}, expected_matches={expected_matches}")
        
        agent = _get_current_agent()
        if not agent or not hasattr(agent, 'code_provider'):
            return "Error: Code provider not available for sandboxed file operations."

        resp = await agent.code_provider.update_file(
            file_path=file_path,
            old_content=old_content,
            new_content=new_content,
            expected_matches=expected_matches,
        )

        if resp.get("success"):
            bytes_written = resp.get("bytes_written")
            if bytes_written is not None:
                return f"Successfully updated {sanitize_path(file_path)}. Wrote {bytes_written} bytes."
            return f"Successfully updated {sanitize_path(file_path)}."
        else:
            error_msg = get_friendly_error_message("update_error", file_path, resp.get("error", ""))
            return f"Error: {error_msg}"
            
    except Exception as e:
        if logger:
            logger.debug(f"update_file unexpected error: {str(e)}", exc_info=True)
        return f"Error updating file: {str(e)}"


@tool(name="glob", description="""
- Fast file pattern matching tool executed within provider sandbox
- Returns absolute file paths matching the pattern (alphabetically sorted)

Requirements:
- You MUST provide an absolute directory via `absolute_path`. Relative paths are rejected.
- Supports glob patterns like "**/*.js" or "src/**/*.ts"

Args:
- pattern (str): Glob pattern to match (applied to file paths)
- absolute_path (str): Absolute directory to search within. Must exist in the sandbox.
""")
async def glob_tool(
    pattern: str,
    absolute_path: str
) -> str:
    """File pattern matching via provider sandbox search."""
    logger = get_logger()
    
    try:
        if logger:
            logger.debug(f"glob called with: pattern='{pattern}', absolute_path={absolute_path}")
        
        # Validate absolute path requirement
        if not absolute_path or not os.path.isabs(absolute_path):
            error_msg = "You must provide an absolute_path (absolute directory)."
            if logger:
                logger.debug(error_msg)
            return f"Error: {error_msg}"
        
        # Use provider sandbox search_files to list files, then filter client-side by glob
        agent = _get_current_agent()
        if not agent or not hasattr(agent, 'code_provider'):
            return "Error: Code provider not available for sandboxed file operations."

        directory = sanitize_path(absolute_path)
        # Broad search: empty pattern to collect all text files; we will filter by glob
        resp = await agent.code_provider.search_files(pattern="", directory=directory, regex=False)

        if not resp.get("success"):
            return f"Error: {resp.get('error', 'Search failed')}"

        matches = resp.get("matches", [])
        all_paths = _extract_match_paths(matches, base_dir=directory)

        # Apply glob filtering to relative paths from directory
        rel_paths = [os.path.relpath(p, directory) for p in all_paths]
        filtered = [p for p in rel_paths if fnmatch.fnmatch(p, pattern)]
        abs_filtered = [os.path.join(directory, p) for p in filtered]

        if not abs_filtered:
            return f"No files found matching pattern '{pattern}' in directory '{absolute_path}'"

        abs_filtered.sort()
        return "\n".join(abs_filtered)
            
    except Exception as e:
        if logger:
            logger.debug(f"glob unexpected error: {str(e)}", exc_info=True)
        return f"Error in glob: {str(e)}"


@tool(name="grep", description="""Search file contents within the provider sandbox (ripgrep-like).

Requirements:
- Provide an absolute directory via `absolute_path`. Relative paths are rejected.
- Prefer this tool over invoking `grep/rg` via the shell.

Capabilities:
- Literal or regex search (`regex: true`)
- Output modes: `content` (matching lines), `files_with_matches` (paths), `count` (match counts)

Args:
- pattern (str): Pattern to search for. Use `regex: true` for regex.
- absolute_path (str): Absolute directory to search.
- glob (str, optional): Filter files by glob pattern after search.
- output_mode (str): `content` | `files_with_matches` | `count` (default: `files_with_matches`).
- i (bool, optional): Case-insensitive.
- regex (bool, optional): Treat pattern as regex.
""")
async def grep_tool(
    pattern: str,
    absolute_path: str,
    glob: Optional[str] = None,
    output_mode: str = "files_with_matches",
    i: Optional[bool] = None,
    regex: Optional[bool] = None,
) -> str:
    """Content search via provider sandbox (limited ripgrep parity)."""
    logger = get_logger()
    
    try:
        if logger:
            logger.debug(f"grep called with: pattern='{pattern}', absolute_path={absolute_path}, glob={glob}, output_mode={output_mode}, i={i}, regex={regex}")
        
        if not absolute_path or not os.path.isabs(absolute_path):
            error_msg = "You must provide an absolute_path (absolute directory)."
            if logger:
                logger.debug(error_msg)
            return f"Error: {error_msg}"
        
        agent = _get_current_agent()
        if not agent or not hasattr(agent, 'code_provider'):
            return "Error: Code provider not available for sandboxed file operations."

        directory = sanitize_path(absolute_path)
        resp = await agent.code_provider.search_files(
            pattern=pattern,
            directory=directory,
            case_sensitive=(False if i else True) if i is not None else False,
            regex=(True if regex else False),
        )

        if not resp.get("success"):
            return f"Error: {resp.get('error', 'Search failed')}"

        matches = resp.get("matches", [])

        # Optionally filter by glob on the relative path
        if glob:
            filtered = []
            for m in matches:
                rel = m.get('file_path') or m.get('file') or m.get('full_path') or m.get('path')
                if not rel:
                    continue
                if fnmatch.fnmatch(rel, glob):
                    filtered.append(m)
            matches = filtered

        if output_mode == "files_with_matches":
            files = _extract_match_paths(matches, base_dir=directory)
            if not files:
                return f"No matches found for pattern '{pattern}' in directory '{absolute_path}'"
            files.sort()
            return "\n".join(files)
        elif output_mode == "count":
            files = _extract_match_paths(matches, base_dir=directory)
            return str(len(set(files)))
        else:  # content
            # Format: path:line: content (best-effort; provider may include line numbers)
            lines: List[str] = []
            for m in matches:
                rel = m.get('file_path') or m.get('file') or m.get('full_path') or m.get('path')
                if not rel:
                    continue
                abs_path = rel if os.path.isabs(rel) else os.path.join(directory, rel)
                line_no = m.get('line')
                snippet = m.get('content') or ""
                if line_no is not None:
                    lines.append(f"{abs_path}:{line_no}: {snippet}")
                else:
                    lines.append(f"{abs_path}: {snippet}")
            if not lines:
                return f"No matches found for pattern '{pattern}' in directory '{absolute_path}'"
            return "\n".join(lines)
            
    except Exception as e:
        if logger:
            logger.debug(f"grep unexpected error: {str(e)}", exc_info=True)
        return f"Error in grep: {str(e)}"





# Hook system integration example
class FileOperationApprovalHook:
    """
    Example hook that controls file operations and can approve/deny/modify file tool execution.
    
    This demonstrates the universal hook interface for file operations.
    """
    
    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve
    
    async def before_tool_execution(self, event_name: str, agent, **kwargs) -> Optional[Dict[str, Any]]:
        """Called before any tool execution."""
        tool_name = kwargs.get("tool_name")
        tool_args = kwargs.get("tool_args", {})
        
        # Only handle file operations
        if tool_name not in ["read_file", "write_file", "update_file", "glob", "grep"]:
            return {"proceed": True}
        
        if self.auto_approve:
            return {"proceed": True}
        
        # In a real implementation, this would show a user interface
        # For now, return approval for demo purposes
        if tool_name in ["write_file", "update_file"]:
            # These operations modify files, so they might need approval
            file_path = tool_args.get("file_path", "unknown")
            print(f"File operation approval needed: {tool_name} on {file_path}")
            
            # In a real UI, this would be an interactive prompt
            # For demo: auto-approve but log the action
            return {"proceed": True}
        
        return {"proceed": True}
    
    async def after_tool_execution(self, event_name: str, agent, **kwargs) -> Optional[Dict[str, Any]]:
        """Called after tool execution."""
        tool_name = kwargs.get("tool_name")
        result = kwargs.get("result", "")
        
        # Only handle file operations
        if tool_name not in ["read_file", "write_file", "update_file", "glob", "grep"]:
            return None
        
        # Could modify the result here if needed
        # For example, add additional context or warnings
        
        return None


class DevelopmentHook(FileOperationApprovalHook):
    """Development hook that auto-approves all file operations."""
    
    def __init__(self):
        super().__init__(auto_approve=True)


class ProductionApprovalHook(FileOperationApprovalHook):
    """Production hook that requires user approval for file modifications."""
    
    def __init__(self):
        super().__init__(auto_approve=False)
    
    async def before_tool_execution(self, event_name: str, agent, **kwargs) -> Optional[Dict[str, Any]]:
        """Show diff and request approval for file modifications."""
        tool_name = kwargs.get("tool_name")
        tool_args = kwargs.get("tool_args", {})
        
        if tool_name in ["write_file", "update_file"]:
            # In a real implementation, this would show a diff and wait for user input
            file_path = tool_args.get("file_path", "unknown")
            content = tool_args.get("content", "") or tool_args.get("new_content", "")
            
            print(f"\n=== FILE OPERATION APPROVAL REQUIRED ===")
            print(f"Operation: {tool_name}")
            print(f"File: {file_path}")
            print(f"Content preview: {content[:100]}...")
            print("In a real UI, you would see a diff and approve/deny this operation.")
            print("========================================\n")
            
            # For demo purposes, auto-approve
            return {"proceed": True}
        
        return await super().before_tool_execution(event_name, agent, **kwargs)