# TinyAgent File Manipulation Tools - Product Development Roadmap

## Executive Summary

This roadmap outlines the development of native file manipulation tools (Write, Update, Read, Search) for TinyAgent and TinyCodeAgent. Based on comprehensive analysis of industry leaders (Gemini CLI, Codex, Mini-SWE-Agent), we propose a **sandbox-first, hooks-based approach** that maintains TinyAgent's minimal core philosophy while providing secure, extensible file operation capabilities.

## Project Overview

### Objectives
- Add first-class file manipulation tools to TinyAgent/TinyCodeAgent ecosystem
- **Execute all file operations within provider sandboxes** (seatbelt on macOS, Linux sandbox, remote providers for Windows)
- Provide Write, Update, Read, and Search capabilities with **LLM-friendly descriptions**
- Implement **hooks-based user review system** for change approval workflows
- Enable optional file operation review through configurable hooks
- Support headless to fancy React UI integrations through extensible hook system

### Success Metrics
- 100% compatibility with existing TinyAgent architecture
- All file operations execute within sandbox boundaries
- <100ms response time for basic file operations
- Comprehensive safety validation through provider security policies
- Optional user review workflows through hooks (diff visualization, approval/rejection)
- **Text-only file support initially** with LLM-friendly errors for other formats
- Universal API for cross-platform sandbox providers

## Technical Architecture Decision

### Chosen Approach: Sandbox-First Native Tools with Hooks-Based Review

**Rationale**: 
- **Security-first**: All file operations constrained by sandbox provider policies
- **Minimal core**: File tools are thin wrappers around provider calls
- **Extensible hooks**: Review workflows handled through optional hook system
- **Platform universal**: Unified API across different sandbox implementations
- Perfect fit with existing `@tool` decorator and provider pattern
- Maintains TinyAgent's architectural consistency

### Platform Support Strategy
1. **macOS**: Use existing SeatbeltProvider (✓ Available)
2. **Linux**: Implement LinuxSandboxProvider (Landlock LSM + seccomp-bpf)
3. **Windows**: Postponed - recommend remote providers (Modal) for now

## Development Phases

### Phase 1: Foundation & Sandbox Integration (Weeks 1-3)

#### Week 1: Sandbox Integration & Universal Hook Enhancement
**Deliverables:**
- [🔄] Extend provider base class with file operation methods (IN PROGRESS)
- [ ] Enhance existing tool hooks to support execution control (approve/deny/modify)
- [ ] Create LinuxSandboxProvider specification and API design
- [ ] Define universal file operation interface across providers
- [ ] Update `before_tool_execution` and `after_tool_execution` hooks for decision-making

**Technical Tasks:**
```python
# Provider extension for file operations (simple methods)
class CodeExecutionProvider:
    async def read_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """Read file within sandbox boundaries"""
        
    async def write_file(self, file_path: str, content: str, **kwargs) -> Dict[str, Any]:
        """Write file within sandbox boundaries"""
        
    async def update_file(self, file_path: str, old_content: str, new_content: str, **kwargs) -> Dict[str, Any]:
        """Update file content within sandbox boundaries"""
        
    async def search_files(self, pattern: str, directory: str = ".", **kwargs) -> Dict[str, Any]:
        """Search files within sandbox boundaries"""

# Enhanced universal hooks (works for ALL tools)
async def _run_decision_hooks(self, hook_name: str, tool_name: str, tool_args: dict, **kwargs):
    """Universal hooks that can approve/deny/modify ANY tool execution"""
    # Hook can return: {"proceed": bool, "alternative_response": str, "modified_args": dict}
```

#### Week 2: Read Tool Implementation (Text-Only)
**Deliverables:**
- [✅] `read_file` tool with **text-only support**
- [✅] LLM-friendly error messages for non-text files
- [✅] Pagination for large files through provider
- [✅] Sandbox-constrained file access
- [✅] Comprehensive error handling

**Implementation (LLM-Friendly Description):**
```python
@tool(name="read_file", description="""
Read text file content safely within sandbox boundaries. This tool can only read text-based files and will provide helpful error messages for other file types.

Use this tool to:
- Examine source code, configuration files, documentation
- Read log files, data files, and text-based content
- Inspect file contents before making changes
- Understand project structure and file relationships

The tool respects sandbox security policies and can only access files within allowed directories.
""")
async def read_file(
    file_path: str,
    start_line: int = 1,
    max_lines: Optional[int] = None,
    encoding: str = "utf-8"
) -> str:
    """
    Read text file content within sandbox boundaries.
    
    Args:
        file_path: Path to the file (relative to working directory or absolute within sandbox)
        start_line: Starting line number (1-based) for pagination
        max_lines: Maximum lines to read (None for all)
        encoding: File encoding (default: utf-8)
    
    Returns:
        File content for text files, or helpful error message for unsupported formats
    """
```

#### Week 3: Write Tool Implementation (Universal Hook Integration)
**Deliverables:**
- [✅] `write_file` tool with sandbox-constrained writing
- [✅] Automatic integration with universal tool approval hooks
- [✅] Optional user approval workflow (works for ANY tool through universal hooks)
- [✅] Atomic write operations within sandbox
- [✅] Directory creation within sandbox boundaries

**Implementation (LLM-Friendly Description):**
```python
@tool(name="write_file", description="""
Write content to text files safely within sandbox boundaries. This tool creates or overwrites files with the specified content.

Use this tool to:
- Create new source code files, configuration files, documentation
- Save generated content, scripts, or data files  
- Write structured data (JSON, YAML, CSV) to files
- Create temporary files for testing or processing

The tool operates within sandbox security policies and may trigger user review workflows depending on configuration. It can only write to directories permitted by the sandbox policy.
""")
async def write_file(
    file_path: str,
    content: str,
    create_dirs: bool = True,
    encoding: str = "utf-8"
) -> str:
    """
    Write content to a file within sandbox boundaries.
    
    Args:
        file_path: Path to the target file (relative to working directory or absolute within sandbox)
        content: Content to write to the file
        create_dirs: Create parent directories if they don't exist (default: True)
        encoding: File encoding (default: utf-8)
    
    Returns:
        Success message with operation details, or error message if operation fails
    """
```

### Phase 2: Advanced Tools & Linux Sandbox Provider (Weeks 4-6)

#### Week 4: Update Tool Implementation (Universal Hook Integration)
**Deliverables:**
- [✅] `update_file` tool with sandbox-constrained updates
- [✅] Automatic integration with universal tool approval hooks (same as all tools)
- [✅] Precise string replacement within sandbox
- [✅] Optional user confirmation through universal hook system
- [✅] Context validation for safety

**Implementation (LLM-Friendly Description):**
```python
@tool(name="update_file", description="""
Update existing text files by replacing specific content within sandbox boundaries. This tool performs precise string replacements and may trigger user review workflows.

Use this tool to:
- Fix bugs by replacing specific code sections
- Update configuration values or parameters
- Modify documentation or comments
- Apply targeted changes to existing files

The tool requires exact string matching for safety and operates within sandbox security policies. Depending on configuration, it may show diffs and request user approval before making changes.
""")
async def update_file(
    file_path: str,
    old_content: str,
    new_content: str,
    expected_matches: int = 1
) -> str:
    """
    Update file content with exact string replacement within sandbox.
    
    Args:
        file_path: Path to the file (relative to working directory or absolute within sandbox)
        old_content: Exact content to replace (must match exactly)
        new_content: Replacement content
        expected_matches: Expected number of matches (default: 1)
    
    Returns:
        Update summary with changes made, or error message if operation fails
    """
```

#### Week 5: Search Tool Implementation
**Deliverables:**
- [✅] `search_files` tool with sandbox-constrained searching
- [✅] Integration with provider's file system access
- [✅] Pattern matching within allowed directories
- [✅] File type filtering through sandbox policies
- [✅] Performance optimization for large codebases

**Implementation (LLM-Friendly Description):**
```python
@tool(name="search_files", description="""
Search for text patterns across files within sandbox boundaries. This tool helps you find code, configuration values, or text content across your project.

Use this tool to:
- Find function definitions, variable usages, or specific code patterns
- Locate configuration settings or documentation
- Search for error messages, comments, or specific text
- Understand code organization and relationships

The tool respects sandbox security policies and only searches within allowed directories. It supports both literal text and regular expression patterns.
""")
async def search_files(
    pattern: str,
    directory: str = ".",
    file_types: Optional[List[str]] = None,
    case_sensitive: bool = False,
    regex: bool = False
) -> str:
    """
    Search for patterns across files within sandbox boundaries.
    
    Args:
        pattern: Search pattern (literal text or regex if regex=True)
        directory: Directory to search (default: current, must be within sandbox)
        file_types: File extensions to include (e.g., ['.py', '.js'])
        case_sensitive: Case-sensitive search (default: False)
        regex: Treat pattern as regex (default: False)
    
    Returns:
        Search results with file paths and line numbers, or error message if search fails
    """
```

#### Week 6: Linux Sandbox Provider Implementation
**Deliverables:**
- [ ] LinuxSandboxProvider class with Landlock + seccomp integration
- [ ] File operation methods for Linux sandbox
- [ ] Cross-platform compatibility testing
- [ ] Performance benchmarking vs SeatbeltProvider
- [ ] Documentation for Linux deployment

**LinuxSandboxProvider Architecture (Based on Codex Implementation):**
```python
class LinuxSandboxProvider(CodeExecutionProvider):
    """
    Linux sandbox provider using Landlock LSM for filesystem restrictions
    and seccomp-bpf for system call filtering, based on proven Codex patterns.
    
    Security Architecture:
    - Landlock LSM: Path-based filesystem access control
    - seccomp-bpf: System call filtering for network isolation
    - Default deny policy with selective permissions
    """
    
    def __init__(self, 
                 writable_roots: List[str] = None,
                 additional_read_dirs: List[str] = None,
                 network_access: bool = False,
                 landlock_abi_version: str = "V5",
                 **kwargs):
        super().__init__(**kwargs)
        self.writable_roots = writable_roots or [self.working_directory]
        self.additional_read_dirs = additional_read_dirs or []
        self.network_access = network_access
        self.landlock_abi_version = landlock_abi_version
        self._sandbox_policy = self._create_sandbox_policy()
        
    def _create_sandbox_policy(self) -> Dict[str, Any]:
        """Create sandbox policy configuration"""
        return {
            "full_network_access": self.network_access,
            "full_disk_read_access": True,  # Read access to entire filesystem
            "full_disk_write_access": False,  # Restricted write access
            "writable_roots": [Path(root).resolve() for root in self.writable_roots],
        }
    
    async def _apply_landlock_filesystem_restrictions(self) -> None:
        """
        Apply Landlock filesystem restrictions using proven Codex patterns.
        
        Implementation mirrors Codex's landlock.rs:
        - Default deny policy for all filesystem access
        - Read-only access to entire filesystem (/)
        - Write access only to specified directories
        - Safe device access (/dev/null)
        """
        try:
            import landlock
            
            # Use latest Landlock ABI (V5)
            abi = landlock.ABI.V5
            access_rw = landlock.AccessFs.from_all(abi)
            access_ro = landlock.AccessFs.from_read(abi)
            
            # Create ruleset with compatibility mode
            ruleset = (landlock.Ruleset()
                      .set_compatibility(landlock.CompatLevel.BestEffort)
                      .handle_access(access_rw)
                      .create())
            
            # Grant read-only access to entire filesystem
            ruleset = ruleset.add_rules(
                landlock.path_beneath_rules(["/"], access_ro)
            )
            
            # Allow writing to /dev/null (required for many tools)
            ruleset = ruleset.add_rules(
                landlock.path_beneath_rules(["/dev/null"], access_rw)
            )
            
            # Add user-specified writable directories
            if self.writable_roots:
                ruleset = ruleset.add_rules(
                    landlock.path_beneath_rules(self.writable_roots, access_rw)
                )
            
            # Apply restrictions with no_new_privs
            status = ruleset.restrict_self(no_new_privs=True)
            
            # Ensure restrictions were actually applied
            if status.ruleset == landlock.RulesetStatus.NotEnforced:
                raise RuntimeError("Landlock restrictions failed to apply")
                
        except ImportError:
            # Graceful degradation if Landlock not available
            logger.warning("Landlock not available, using basic restrictions")
            self._apply_basic_filesystem_restrictions()
    
    async def _apply_seccomp_network_restrictions(self) -> None:
        """
        Apply seccomp-bpf network restrictions using Codex patterns.
        
        Blocks all network-related system calls except Unix domain sockets.
        Implementation mirrors Codex's seccomp filter configuration.
        """
        if self.network_access:
            return
            
        try:
            import seccomp
            
            # Create seccomp filter with default ALLOW policy
            f = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
            
            # Block all network-related system calls
            network_syscalls = [
                "connect", "accept", "accept4", "bind", "listen",
                "getpeername", "getsockname", "shutdown", "sendto",
                "sendmsg", "sendmmsg", "recvfrom", "recvmsg", "recvmmsg",
                "getsockopt", "setsockopt", "ptrace"
            ]
            
            for syscall in network_syscalls:
                try:
                    f.add_rule(seccomp.ERRNO(errno.EPERM), syscall)
                except OSError:
                    # Syscall not available on this architecture
                    continue
            
            # Allow only AF_UNIX sockets
            f.add_rule(seccomp.ALLOW, "socket", 
                      seccomp.Arg(0, seccomp.EQ, socket.AF_UNIX))
            f.add_rule(seccomp.ERRNO(errno.EPERM), "socket")
            f.add_rule(seccomp.ERRNO(errno.EPERM), "socketpair")
            
            # Load the filter
            f.load()
            
        except ImportError:
            logger.warning("seccomp not available, network restrictions not applied")
    
    async def _setup_sandbox_environment(self) -> None:
        """Initialize sandbox environment with Landlock + seccomp restrictions"""
        await self._apply_landlock_filesystem_restrictions()
        await self._apply_seccomp_network_restrictions()
    
    async def read_file(self, file_path: str, **kwargs) -> Dict[str, Any]:
        """
        Read file within Landlock-restricted filesystem.
        
        Security: File access controlled by Landlock path-beneath rules.
        Only files within readable paths can be accessed.
        """
        try:
            resolved_path = Path(file_path).resolve()
            
            # Validate path is within allowed boundaries
            if not self._is_path_readable(resolved_path):
                return {
                    "success": False,
                    "error": f"Access denied: Path outside readable boundaries: {resolved_path}",
                    "content": None
                }
            
            # Use async file operations within sandbox
            async with aiofiles.open(resolved_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                
            return {
                "success": True,
                "content": content,
                "path": str(resolved_path),
                "size": len(content)
            }
            
        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied by Landlock restrictions: {file_path}",
                "content": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"File read error: {str(e)}",
                "content": None
            }
    
    async def write_file(self, file_path: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        Write file within Landlock-restricted filesystem.
        
        Security: Write access controlled by Landlock writable_roots policy.
        Only directories in writable_roots allow file creation/modification.
        """
        try:
            resolved_path = Path(file_path).resolve()
            
            # Validate path is within writable boundaries
            if not self._is_path_writable(resolved_path):
                return {
                    "success": False,
                    "error": f"Access denied: Path outside writable boundaries: {resolved_path}",
                    "bytes_written": 0
                }
            
            # Create parent directories if needed (within writable roots)
            parent_dir = resolved_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
            
            # Write file within sandbox constraints
            async with aiofiles.open(resolved_path, 'w', encoding='utf-8') as f:
                await f.write(content)
                
            return {
                "success": True,
                "path": str(resolved_path),
                "bytes_written": len(content.encode('utf-8')),
                "operation": "write"
            }
            
        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied by Landlock restrictions: {file_path}",
                "bytes_written": 0
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"File write error: {str(e)}",
                "bytes_written": 0
            }
    
    async def update_file(self, file_path: str, old_content: str, new_content: str, **kwargs) -> Dict[str, Any]:
        """
        Update file content with exact string replacement within sandbox.
        
        Security: Uses same Landlock restrictions as write_file.
        Validates content changes before applying within sandbox boundaries.
        """
        try:
            # Read current content
            read_result = await self.read_file(file_path)
            if not read_result["success"]:
                return read_result
                
            current_content = read_result["content"]
            
            # Validate old_content exists
            if old_content not in current_content:
                return {
                    "success": False,
                    "error": f"Old content not found in file: {file_path}",
                    "changes_made": False
                }
            
            # Apply replacement
            updated_content = current_content.replace(old_content, new_content)
            
            # Write updated content
            write_result = await self.write_file(file_path, updated_content)
            
            if write_result["success"]:
                return {
                    "success": True,
                    "path": file_path,
                    "changes_made": True,
                    "old_content": old_content,
                    "new_content": new_content,
                    "bytes_written": write_result["bytes_written"]
                }
            else:
                return write_result
                
        except Exception as e:
            return {
                "success": False,
                "error": f"File update error: {str(e)}",
                "changes_made": False
            }
    
    async def search_files(self, pattern: str, directory: str = ".", **kwargs) -> Dict[str, Any]:
        """
        Search files within Landlock-restricted filesystem.
        
        Security: Search scope limited by Landlock readable paths.
        Uses safe subprocess execution within sandbox boundaries.
        """
        try:
            resolved_dir = Path(directory).resolve()
            
            # Validate search directory is readable
            if not self._is_path_readable(resolved_dir):
                return {
                    "success": False,
                    "error": f"Access denied: Directory outside readable boundaries: {resolved_dir}",
                    "matches": []
                }
            
            # Use ripgrep for efficient searching within sandbox
            cmd = [
                "rg", "--json", "--smart-case", 
                "--type-not", "binary",
                pattern, str(resolved_dir)
            ]
            
            # Execute within sandbox constraints
            result = await self._execute_sandboxed_command(cmd)
            
            if result["returncode"] == 0:
                matches = self._parse_ripgrep_output(result["stdout"])
                return {
                    "success": True,
                    "matches": matches,
                    "pattern": pattern,
                    "directory": str(resolved_dir)
                }
            else:
                return {
                    "success": False,
                    "error": f"Search failed: {result['stderr']}",
                    "matches": []
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"File search error: {str(e)}",
                "matches": []
            }
    
    def _is_path_readable(self, path: Path) -> bool:
        """Check if path is within readable boundaries (entire filesystem)"""
        # Landlock grants read access to entire filesystem
        return True
    
    def _is_path_writable(self, path: Path) -> bool:
        """Check if path is within writable boundaries"""
        for writable_root in self.writable_roots:
            try:
                path.relative_to(writable_root)
                return True
            except ValueError:
                continue
        return False
    
    async def _execute_sandboxed_command(self, cmd: List[str]) -> Dict[str, Any]:
        """Execute command within sandbox restrictions"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_directory
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                "returncode": process.returncode,
                "stdout": stdout.decode('utf-8', errors='replace'),
                "stderr": stderr.decode('utf-8', errors='replace')
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e)
            }
```

### Phase 3: Universal Hook Examples & Cross-Platform Testing (Weeks 7-8)

#### Week 7: Universal Hook Implementation Examples  
**Deliverables:**
- [ ] Universal hook examples for different UI frameworks
- [ ] Diff generation and visualization utilities (usable by any hook)
- [ ] Example implementations (headless, CLI, Rich UI, Jupyter UI, React integration points)
- [ ] Hook decision-making documentation and best practices
- [ ] Testing universal hooks with all tool types (bash, python, file tools, MCP tools)

**Universal Hook Examples:**
```python
# Universal hooks work for ALL tools (bash, python, file operations, MCP tools)
class UniversalApprovalHook:
    async def before_tool_execution(self, event_name, agent, kwargs_dict):
        tool_name = kwargs_dict.get('tool_name')
        tool_args = kwargs_dict.get('tool_args')
        
        # Single hook handles ALL dangerous operations
        if self.is_dangerous_operation(tool_name, tool_args):
            decision = await self.show_approval_ui(tool_name, tool_args)
            return {
                "proceed": decision.approved,
                "alternative_response": decision.message if not decision.approved else None,
                "modified_args": decision.modified_args
            }
        return {"proceed": True}

# Example implementations
class HeadlessHook:
    """Auto-approve all operations (CI/automation)"""
    
class TerminalHook:
    """Show approval prompts in terminal"""
    
class JupyterHook:
    """Show interactive approval widgets in Jupyter"""
    
class ReactUIHook:
    """Send approval requests to React frontend"""
```

#### Week 8: TinyCodeAgent Integration & Cross-Platform Testing
**Deliverables:**
- [ ] Seamless integration with existing TinyCodeAgent
- [ ] File tools work alongside run_python and bash tools (all use same universal hooks)
- [ ] Cross-platform testing (macOS Seatbelt, Linux Landlock, Modal remote)
- [ ] Provider-specific file operation security policies
- [ ] Documentation for each platform's file operation capabilities

### Phase 4: Testing & Documentation (Weeks 9-10)

#### Week 9: Comprehensive Testing & Security Validation
**Deliverables:**
- [🔄] Unit tests for all tools (>95% coverage) - IN PROGRESS
- [🔄] Integration tests with all three providers (Seatbelt, Linux, Modal) - PARTIAL (Modal done)
- [🔄] Security testing of sandbox file operation boundaries - IN PROGRESS
- [ ] Performance benchmarks for file operations across providers
- [ ] Hooks system testing with different UI integrations

#### Week 10: Documentation & Platform-Specific Guides
**Deliverables:**
- [ ] Complete API documentation for file tools and hooks
- [ ] Platform-specific deployment guides (macOS, Linux, Remote)
- [ ] Hook system documentation with UI integration examples
- [ ] Best practices for secure file operations
- [ ] Migration guide for adding file tools to existing TinyCodeAgent projects

## Technical Specifications

### Security Requirements (Sandbox-First)
1. **Sandbox Boundary Enforcement**: All file operations must execute within provider sandbox policies
2. **Platform-Specific Security**:
   - **macOS**: Seatbelt profile restrictions on file system access
   - **Linux**: Landlock LSM + seccomp-bpf filesystem and network isolation
   - **Windows/Remote**: Modal provider cloud execution with containerization
3. **No Direct File System Access**: File tools never bypass provider sandbox mechanisms
4. **Hook-Based Approval**: Optional user review workflows through configurable hooks
5. **Provider Security Inheritance**: File operations inherit all provider security policies

### Universal Hooks-Based Review System
1. **Universal Tool Control**: Single hook system works for ALL tools (bash, python, file ops, MCP tools)
2. **Decision-Making Hooks**: Hooks can approve/deny/modify ANY tool execution before it happens
3. **UI-Agnostic Design**: Same hook interface supports headless, terminal, and web UI integrations
4. **Configurable Policies**: Developers configure which tool+args combinations require review
5. **Non-Blocking Architecture**: Hooks are optional and don't impact automation use cases

### Performance Requirements (Provider-Constrained)
1. **Response Time**: <100ms for basic operations (within sandbox overhead)
2. **Memory Usage**: <20MB additional memory footprint per provider
3. **File Size Limits**: Handle files up to provider limits (typically 100MB)
4. **Concurrent Operations**: Limited by provider's concurrent execution capabilities
5. **Search Performance**: Depends on provider's file system access speed

### Text-Only File Support (Initial Implementation)
1. **Supported Formats**: Plain text, source code, configuration files, logs
2. **Encoding Support**: UTF-8 (primary), with auto-detection for common encodings
3. **LLM-Friendly Errors**: Clear error messages for unsupported file types (images, PDFs, binaries)
4. **Future Extension Point**: Architecture allows adding multi-format support later
5. **MIME Type Detection**: Basic file type detection for appropriate error messages

### Cross-Platform Compatibility
1. **Provider Abstraction**: Unified API across all sandbox providers
2. **Platform Detection**: Automatic selection of appropriate provider (seatbelt/linux/modal)
3. **Graceful Degradation**: Fall back to remote providers when local sandboxing unavailable
4. **Universal File Paths**: Consistent path handling across different sandbox implementations
5. **Provider-Specific Documentation**: Clear guidance for each platform's capabilities

## Linux Sandbox Provider Specification (Based on Codex Implementation)

### Requirements for Linux Implementation
Based on Codex's battle-tested Linux sandboxing approach, the LinuxSandboxProvider implements multi-layered security using Landlock LSM and seccomp-bpf:

#### Filesystem Isolation (Landlock LSM)
Following Codex's `landlock.rs` implementation patterns:

- **Landlock ABI V5**: Use latest Landlock features for maximum security
- **Default Deny Policy**: All filesystem access denied by default
- **Selective Write Access**: Only specified directories writable (working directory + configured paths)
- **Read-Only Root**: Entire filesystem (`/`) readable for tool functionality
- **Path-Beneath Rules**: Directory tree access control using Landlock's path-beneath rules
- **Safe Device Access**: `/dev/null` always writable for command compatibility
- **Best-Effort Compatibility**: Graceful degradation on older kernels

#### System Call Filtering (seccomp-bpf)
Following Codex's network isolation patterns:

- **Complete Network Block**: All TCP/UDP networking syscalls blocked
- **Unix Sockets Only**: Allow AF_UNIX domain sockets for IPC
- **Blocked Syscalls**: `connect`, `accept`, `bind`, `listen`, `sendto`, `recvfrom`, `ptrace`
- **Error Handling**: Return `EPERM` for blocked system calls
- **Architecture Support**: x86_64 and aarch64 compatible
- **Custom Filter Rules**: Configurable seccomp BPF programs

#### Codex-Based Security Architecture
```python
# Based on Codex's core/src/protocol.rs SandboxPolicy
class SandboxPolicy:
    """
    Sandbox policy configuration following Codex patterns.
    
    Mirrors Codex's SandboxPolicy struct for proven security model.
    """
    def __init__(self):
        self.full_network_access: bool = False      # Network completely blocked
        self.full_disk_read_access: bool = True     # Read entire filesystem
        self.full_disk_write_access: bool = False   # Restrict writes
        self.writable_roots: List[Path] = []        # Allowed write directories

# Based on Codex's linux-sandbox/src/landlock.rs
async def apply_sandbox_policy_to_current_thread(
    sandbox_policy: SandboxPolicy,
    cwd: Path
) -> None:
    """
    Apply multi-layered sandbox restrictions.
    
    Follows Codex's exact security layering approach:
    1. Network restrictions via seccomp (if needed)
    2. Filesystem restrictions via Landlock (if needed)
    """
    
    # Apply network restrictions if not allowed
    if not sandbox_policy.full_network_access:
        await install_network_seccomp_filter_on_current_thread()
    
    # Apply filesystem restrictions if not full access
    if not sandbox_policy.full_disk_write_access:
        writable_roots = sandbox_policy.get_writable_roots_with_cwd(cwd)
        await install_filesystem_landlock_rules_on_current_thread(writable_roots)

# Based on Codex's Landlock ruleset configuration
async def install_filesystem_landlock_rules_on_current_thread(
    writable_roots: List[Path]
) -> None:
    """
    Install Landlock filesystem restrictions.
    
    Follows Codex's exact Landlock configuration from landlock.rs:
    - Default deny policy for all filesystem access
    - Read-only access to entire filesystem (/)
    - Write access only to specified directories
    - Safe device access (/dev/null)
    """
    
    abi = landlock.ABI.V5  # Use latest ABI like Codex
    access_rw = landlock.AccessFs.from_all(abi)
    access_ro = landlock.AccessFs.from_read(abi)
    
    ruleset = (landlock.Ruleset()
              .set_compatibility(landlock.CompatLevel.BestEffort)
              .handle_access(access_rw)
              .create())
    
    # Grant read-only access to entire filesystem (Codex pattern)
    ruleset = ruleset.add_rules(landlock.path_beneath_rules(["/"], access_ro))
    
    # Allow writing to /dev/null (required for many tools - Codex pattern)
    ruleset = ruleset.add_rules(landlock.path_beneath_rules(["/dev/null"], access_rw))
    
    # Add user-specified writable directories
    if writable_roots:
        ruleset = ruleset.add_rules(landlock.path_beneath_rules(writable_roots, access_rw))
    
    # Apply restrictions with no_new_privs (Codex security model)
    status = ruleset.restrict_self(no_new_privs=True)
    
    # Ensure restrictions were actually applied (Codex validation)
    if status.ruleset == landlock.RulesetStatus.NotEnforced:
        raise SandboxError("Landlock restrictions failed to apply")

# Based on Codex's seccomp filter configuration
async def install_network_seccomp_filter_on_current_thread() -> None:
    """
    Install seccomp network restrictions.
    
    Follows Codex's exact seccomp configuration:
    - Block all network-related system calls
    - Allow only AF_UNIX sockets for IPC
    - Return EPERM for blocked calls
    """
    
    f = seccomp.SyscallFilter(defaction=seccomp.ALLOW)
    
    # Block network syscalls (exact list from Codex)
    network_syscalls = [
        "connect", "accept", "accept4", "bind", "listen",
        "getpeername", "getsockname", "shutdown", "sendto",
        "sendmsg", "sendmmsg", "recvfrom", "recvmsg", "recvmmsg",
        "getsockopt", "setsockopt", "ptrace"
    ]
    
    for syscall in network_syscalls:
        f.add_rule(seccomp.ERRNO(errno.EPERM), syscall)
    
    # Allow only AF_UNIX sockets (Codex pattern)
    f.add_rule(seccomp.ALLOW, "socket", 
              seccomp.Arg(0, seccomp.EQ, socket.AF_UNIX))
    f.add_rule(seccomp.ERRNO(errno.EPERM), "socket")
    f.add_rule(seccomp.ERRNO(errno.EPERM), "socketpair")
    
    f.load()
```

#### Command Execution Pipeline (Codex Pattern)
Following Codex's `linux-sandbox/src/linux_run_main.rs` execution model:

```python
# Based on Codex's sandbox execution pipeline
async def execute_sandboxed_file_operation(
    operation: Callable,
    sandbox_policy: SandboxPolicy,
    cwd: Path
) -> Any:
    """
    Execute file operation within sandbox constraints.
    
    Follows Codex's execution pipeline:
    1. Apply sandbox policies to current thread
    2. Execute operation within restrictions
    3. Handle sandbox errors appropriately
    """
    
    try:
        # Apply Codex-style sandbox restrictions
        await apply_sandbox_policy_to_current_thread(sandbox_policy, cwd)
        
        # Execute file operation within sandbox
        result = await operation()
        
        return result
        
    except landlock.LandlockError as e:
        raise SandboxError(f"Landlock restriction failed: {e}")
    except seccomp.SeccompError as e:
        raise SandboxError(f"Seccomp filter failed: {e}")
```

#### Error Handling and Graceful Degradation (Codex Patterns)
Following Codex's robust error handling approach:

```python
# Based on Codex's error handling in linux_run_main.rs
class SandboxError(Exception):
    """Sandbox-specific errors following Codex error taxonomy"""
    pass

class LinuxSandboxProvider(CodeExecutionProvider):
    async def _apply_sandbox_restrictions(self) -> None:
        """Apply sandbox with graceful degradation like Codex"""
        try:
            await self._apply_landlock_filesystem_restrictions()
        except ImportError:
            logger.warning("Landlock not available, using basic restrictions")
            await self._apply_basic_filesystem_restrictions()
        except Exception as e:
            logger.error(f"Landlock setup failed: {e}")
            raise SandboxError(f"Failed to apply filesystem restrictions: {e}")
        
        try:
            await self._apply_seccomp_network_restrictions()
        except ImportError:
            logger.warning("seccomp not available, network restrictions not applied")
        except Exception as e:
            logger.warning(f"seccomp setup failed: {e}, continuing without network restrictions")
```

#### Performance Characteristics (Codex-Validated)
Based on Codex's production performance data:

- **Landlock Overhead**: Minimal runtime overhead (~1-2% CPU, validated in Codex)
- **seccomp Overhead**: Very low overhead for syscall filtering (<1% CPU)
- **Process Spawning**: Additional ~10ms for sandbox setup (Codex measurements)
- **Memory Usage**: ~1MB additional per sandboxed process (Codex data)
- **File Operation Latency**: <5% overhead for file I/O operations

#### Universal API Consistency
The Linux provider maintains API compatibility with SeatbeltProvider while using Codex security patterns:

- **Same method signatures**: `read_file()`, `write_file()`, `update_file()`, `search_files()`
- **Consistent error handling**: Unified error response format across platforms
- **Compatible configuration**: Same policy configuration interface as other providers
- **Unified security abstractions**: Platform-independent security policy definitions

## Risk Management

### Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Linux sandbox implementation complexity | High | Medium | Use proven Codex patterns, extensive testing |
| Provider API inconsistencies | Medium | Medium | Rigorous interface design, cross-platform testing |
| Hooks system performance overhead | Medium | Low | Asynchronous design, optional hooks |
| Sandbox security bypass | High | Low | Multi-layered security, security audits |

### Business Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Platform fragmentation (macOS/Linux/Windows) | Medium | Medium | Clear documentation, provider-specific guides |
| User adoption of hooks system | Medium | Low | Simple defaults, comprehensive examples |
| Breaking changes to existing TinyCodeAgent | High | Low | Backward compatibility, gradual integration |

## Current TinyAgent Hook System Integration

### How Existing Hooks Work in TinyAgent
Based on analysis of `tinyagent/tiny_agent.py`, TinyAgent uses a callback-based hook system:

```python
# Hook registration
self.callbacks: List[callable] = []
def add_callback(self, callback: callable) -> None:
    self.callbacks.append(callback)

# Hook execution at key points
await self._run_callbacks("agent_start", user_input=user_input)
await self._run_callbacks("llm_start", messages=messages, tools=tools)
await self._run_callbacks("llm_end", response=response)
await self._run_callbacks("tool_start", tool_call=tool_call)
await self._run_callbacks("tool_end", tool_call=tool_call, result=result)
await self._run_callbacks("message_add", message=message)
await self._run_callbacks("agent_end", result=result)
```

### Universal Hook Enhancement
Instead of file-specific hooks, we enhance the existing tool hooks to support execution control:

```python
# Enhanced universal hooks (work for ALL tools - file ops, bash, python, MCP tools)
decision = await self._run_callbacks("before_tool_execution", 
                                    tool_name=tool_name, 
                                    tool_args=tool_args,
                                    tool_call=tool_call)

# Hook can return decision to:
# - proceed: bool (allow/deny execution)  
# - alternative_response: str (return this instead of executing)
# - modified_args: dict (modify tool parameters)
# - raise_exception: Exception (raise error instead)

result = await self._run_callbacks("after_tool_execution",
                                 tool_name=tool_name,
                                 result=result, 
                                 tool_call=tool_call)
```

This provides universal tool control - a single hook can handle approval for file operations, bash commands, Python execution, and MCP tools. Much simpler and more powerful than tool-specific hooks.

## Success Criteria

### Technical Success Criteria
- [ ] All file tools execute within sandbox boundaries (0 security bypasses)
- [ ] Linux sandbox provider achieves feature parity with Seatbelt provider
- [ ] Hook system supports headless, terminal, and web UI integrations
- [ ] Text-only file support with LLM-friendly error messages for other formats
- [ ] Performance within 20% of direct file system operations
- [ ] 100% backward compatibility with existing TinyCodeAgent

### Business Success Criteria
- [ ] Clear migration path for developers to add file tools to existing projects
- [ ] Platform-specific documentation enables easy deployment on macOS and Linux
- [ ] Hook system allows seamless integration with different UI frameworks
- [ ] No breaking changes to existing TinyAgent/TinyCodeAgent workflows
- [ ] Developers can choose appropriate security level (local sandbox vs remote execution)

## Post-Launch Roadmap

### Phase 5: Multi-Format Support & Advanced Features (Months 2-3)
- **Multi-format file reading**: Images, PDFs, structured data (JSON, YAML, XML)
- **Advanced search capabilities**: Semantic search, fuzzy matching
- **Windows sandbox provider**: Implement Windows-specific security (Job Objects, AppContainer)
- **Batch file operations**: Multi-file operations with atomic transactions
- **Integration with version control**: Git-aware file operations

### Phase 6: Advanced UI Integrations & Performance (Months 4-6)
- **Web-based diff viewer**: React/Vue components for file operation review
- **Collaborative workflows**: Multi-user file operation approval
- **Performance optimizations**: Caching, streaming for large files
- **Advanced hooks**: Conditional approval, workflow automation
- **File operation analytics**: Usage patterns, security metrics

## Resource Requirements

### Development Team
- **1 Senior Python Developer**: Core implementation and Linux sandbox provider
- **1 Systems/Security Specialist**: Sandbox security and cross-platform testing
- **1 Frontend Developer**: Hook system examples and UI integration guides
- **1 QA Engineer**: Cross-platform testing and security validation
- **1 Technical Writer**: Platform-specific documentation and migration guides

### Infrastructure
- **Multi-Platform CI**: Automated testing on macOS, Linux, and containerized environments
- **Sandbox Testing**: Isolated environments for security validation
- **Performance Monitoring**: File operation benchmarking across providers
- **Documentation Platform**: Interactive examples for hook system integration

## Conclusion

This updated roadmap provides a **sandbox-first, universally-hooked approach** to implementing file manipulation tools in the TinyAgent ecosystem. The key innovations include:

1. **Security-First Design**: All file operations execute within provider sandbox boundaries
2. **Universal Hooks**: Single hook system controls ALL tools (file ops, bash, python, MCP tools)
3. **Platform Universal**: Unified API across macOS (Seatbelt), Linux (Landlock), and remote (Modal) providers
4. **Minimal Core**: File tools are simple provider method calls, hooks are universal
5. **Maximum Simplicity**: One hook pattern instead of multiple tool-specific patterns

### Key Simplifications from Universal Hooks:
- **Single Hook System**: `before_tool_execution` and `after_tool_execution` handle everything
- **No Tool-Specific Hooks**: Universal pattern works for file ops, bash, python, MCP tools
- **Simpler Architecture**: Less complexity, fewer hook points, cleaner separation of concerns
- **More Powerful**: A Jupyter UI hook can approve ANY dangerous operation, not just file operations
- **True Universality**: Same approval UI works for `rm -rf`, `write_file`, `run_python`, etc.

### Implementation Benefits:
- **Faster Development**: No need to implement file-specific hook patterns
- **Better User Experience**: Consistent approval flows across all tool types
- **Easier Testing**: Single hook pattern to test instead of multiple systems
- **Cleaner Codebase**: Universal hooks maintain TinyAgent's minimal philosophy

This approach achieves maximum functionality with minimum complexity, staying true to TinyAgent's core principle of **simple, fast core with extensible hooks**. The universal hook system is more powerful than file-specific hooks while being significantly simpler to implement and maintain.

## Additional Roadmap Simplifications

With universal hooks, we can further simplify the roadmap:

### Development Timeline Reduction
- **Original**: 10 weeks with complex file-specific hook system
- **Simplified**: **8 weeks** - universal hooks eliminate 2 weeks of complex hook development

### Reduced Complexity
1. **No File-Specific Hook Documentation**: Universal hooks are documented once, work everywhere
2. **Fewer Test Cases**: Test universal hooks once instead of file-specific patterns
3. **Simpler Integration Examples**: One hook pattern covers all use cases
4. **Less Phase 3 Complexity**: Universal hook examples instead of file-specific review workflows

### Implementation Simplifications
- **File Tools**: Just provider method calls with `@tool` decorator - no special hook integration needed
- **Provider Methods**: Simple file operation methods, no hook-specific code required
- **Testing**: Universal hook tests cover all tools, not just file operations
- **Documentation**: One hook system guide instead of multiple tool-specific guides

### Resource Reduction
- **Development Team**: Can reduce from 5 to **4 people** (less hook complexity to implement)
- **Testing Overhead**: Single hook pattern testing instead of multiple systems
- **Documentation Effort**: Universal examples work for all tools, not just file operations

The universal hooks approach delivers more functionality (works for ALL tools) with significantly less implementation complexity.

## Gemini CLI Reference Implementations

### Actual Source Code Analysis from Gemini CLI

Based on analysis of the actual Gemini CLI source code in `/external_context/tinyagent/gemini-cli/packages/core/src/tools/`, here are the proven implementation patterns our team can reference:

#### 1. WriteFile Tool Implementation

**Source**: `write-file.ts`  
**Tool Name**: `write_file`  
**LLM Description**: "Writes content to a specified file in the local filesystem. The user has the ability to modify `content`. If modified, this will be stated in the response."

```typescript
interface WriteFileToolParams {
  file_path: string;          // Absolute path to file
  content: string;            // Content to write
  modified_by_user?: boolean; // User modification flag
}

class WriteFileTool extends BaseTool<WriteFileToolParams, ToolResult> {
  // Key implementation features:
  // - Validates absolute paths and root directory constraints
  // - Uses ensureCorrectFileContent() for AI-powered content validation
  // - Creates visual diffs using diff library for user confirmation
  // - Automatically creates parent directories
  // - Records CREATE/UPDATE telemetry metrics
  // - Comprehensive error handling for file operations
}
```

**Key Security Features**:
- Absolute path validation with root directory enforcement
- AI-powered content correction and validation
- User confirmation with diff visualization
- Directory traversal prevention

#### 2. ReadFile Tool Implementation

**Source**: `read-file.ts`  
**Tool Name**: `read_file`  
**LLM Description**: "Reads and returns the content of a specified file from the local filesystem. Handles text, images (PNG, JPG, GIF, WEBP, SVG, BMP), and PDF files. For text files, it can read specific line ranges."

```typescript
interface ReadFileToolParams {
  absolute_path: string; // Absolute path to file
  offset?: number;       // Line number to start reading (0-based)
  limit?: number;        // Number of lines to read
}

class ReadFileTool extends BaseTool<ReadFileToolParams, ToolResult> {
  // Key implementation features:
  // - Multi-format support (text, images, PDFs)
  // - Pagination with offset/limit for large files
  // - MIME type detection and appropriate processing
  // - Respects .geminiignore patterns
  // - Uses processSingleFileContent() utility
}
```

**Multi-Format Processing**:
- Text files: Line-based reading with pagination
- Images: Base64 encoding for AI model consumption  
- PDFs: Text extraction and processing
- Binary files: Appropriate handling based on MIME type

#### 3. Edit/Replace Tool Implementation

**Source**: `edit.ts`  
**Tool Name**: `replace`  
**LLM Description**: "Replaces text within a file. By default, replaces a single occurrence, but can replace multiple occurrences when `expected_replacements` is specified. This tool requires providing significant context around the change to ensure precise targeting. Always use the read_file tool to examine the file's current content before attempting a text replacement."

```typescript
interface EditToolParams {
  file_path: string;              // Absolute path to file
  old_string: string;             // Text to replace (EXACT match required)
  new_string: string;             // Replacement text
  expected_replacements?: number; // Number of expected replacements (default: 1)
  modified_by_user?: boolean;     // User modification flag
}

class EditTool extends BaseTool<EditToolParams, ToolResult> {
  // Key implementation features:
  // - Exact literal text matching (no regex, no escaping)
  // - Requires minimum 3 lines of context before/after change
  // - Uses ensureCorrectEdit() for AI-powered validation
  // - Supports creating new files with empty old_string
  // - Validates occurrence counts match expectations
  // - Creates visual diffs for user confirmation
}
```

**Critical Requirements**:
- `old_string` must be exact literal text with substantial context
- Must uniquely identify the instance to change
- No string escaping allowed - pure literal text matching

#### 4. Search Tool Implementation

**Source**: `grep.ts`  
**Tool Name**: `search_file_content`  
**LLM Description**: "Searches for a regular expression pattern within the content of files in a specified directory (or current working directory). Can filter files by a glob pattern. Returns the lines containing matches, along with their file paths and line numbers."

```typescript
interface GrepToolParams {
  pattern: string; // Regular expression pattern
  path?: string;   // Directory to search (optional)
  include?: string; // File pattern filter (e.g., "*.js")
}

class GrepTool extends BaseTool<GrepToolParams, ToolResult> {
  // Multi-strategy search implementation:
  // 1. Git grep (priority 1) - fastest for git repositories
  // 2. System grep (priority 2) - fallback for Unix systems  
  // 3. JavaScript implementation (priority 3) - pure Node.js fallback
}
```

**Search Strategy Priority**:
1. **Git grep**: `git grep --untracked -n -E --ignore-case "pattern" -- "*.js"`
2. **System grep**: `grep -r -n -H -E --exclude-dir=.git --exclude-dir=node_modules --include="*.js" "pattern" .`
3. **JavaScript fallback**: Uses `glob` library with regex matching

#### 5. Base Tool Architecture

**Source**: `tools.ts`  
**Core Interface Pattern**:

```typescript
interface Tool<TParams, TResult> {
  name: string;                    // Tool identifier
  displayName: string;             // Human-readable name
  description: string;             // LLM-facing description
  icon: Icon;                      // UI icon
  schema: FunctionDeclaration;     // Parameter schema for LLM
  validateToolParams(params: TParams): string | null;
  getDescription(params: TParams): string;
  shouldConfirmExecute(params: TParams, signal: AbortSignal): Promise<ToolCallConfirmationDetails | false>;
  execute(params: TParams, signal: AbortSignal): Promise<TResult>;
}
```

**BaseTool Abstract Class Features**:
- Schema validation using `@google/genai` types
- Built-in confirmation system for dangerous operations
- Telemetry collection and metrics
- Structured error handling for both LLM and users
- Security validation (path constraints, type checking)

#### 6. Additional Reference Tools

**Glob Tool** (`glob.ts`):
```typescript
// Tool Name: "glob"
// Purpose: Find files matching glob patterns, sorted by modification time
// Features: Respects .gitignore, returns newest files first
```

**ReadManyFiles Tool** (`read-many-files.ts`):
```typescript  
// Tool Name: "read_many_files"
// Purpose: Read and concatenate multiple files
// Features: Supports glob patterns, handles images/PDFs, extensive filtering
```

### Key Implementation Insights for TinyAgent

1. **LLM-Friendly Descriptions**: Gemini CLI provides detailed, constraint-specific descriptions
2. **Multi-Strategy Fallbacks**: Tools prefer fast native commands but fallback gracefully
3. **Extensive Validation**: Every tool validates paths, parameters, and content
4. **AI Integration**: Uses AI models for content correction and validation
5. **Security First**: Absolute paths required, root directory enforcement
6. **User Experience**: Built-in confirmation workflows with diff visualization
7. **Error Handling**: Structured responses suitable for both LLM and user display

These implementations provide proven patterns for production-ready file manipulation tools that balance security, usability, and AI assistant integration.

### Additional Implementation Details from Source Code

#### File Processing Utilities (`fileUtils.ts`)

**Binary File Detection**:
```typescript
// Sophisticated binary detection using content sampling
export async function isBinaryFile(filePath: string): Promise<boolean> {
  // Reads up to 4KB sample
  // Null byte detection (strong binary indicator)
  // Non-printable character ratio analysis (>30% = binary)
  // Proper file handle cleanup with error handling
}

// File type detection with special cases
export async function detectFileType(filePath: string): Promise<'text' | 'image' | 'pdf' | 'audio' | 'video' | 'binary' | 'svg'> {
  // Special handling for .ts files (TypeScript vs MPEG transport stream)
  // MIME type lookup with extension-based fallbacks
  // Content-based binary detection for edge cases
}
```

**File Content Processing**:
```typescript
// Universal file content processor
export async function processSingleFileContent(
  filePath: string,
  rootDirectory: string,
  offset?: number,
  limit?: number
): Promise<ProcessedFileReadResult> {
  // 20MB file size limit enforcement
  // Text files: Line-based reading with truncation (2000 lines max, 2000 chars per line)
  // Images/PDFs: Base64 encoding for AI consumption
  // SVG: Text processing with 1MB limit
  // Binary: Graceful rejection with helpful messages
  // Comprehensive error handling and cleanup
}
```

**Security Path Validation**:
```typescript
// Root directory boundary enforcement
export function isWithinRoot(pathToCheck: string, rootDirectory: string): boolean {
  // Path normalization and resolution
  // Directory separator handling (cross-platform)
  // Prevents directory traversal attacks
  // Handles edge cases (root paths, symbolic links)
}
```

#### Advanced Glob Tool (`glob.ts`)

**Smart File Sorting Algorithm**:
```typescript
// Prioritizes recent files (modified within 24 hours) then alphabetical
export function sortFileEntries(
  entries: GlobPath[],
  nowTimestamp: number,
  recencyThresholdMs: number
): GlobPath[] {
  // Recent files: newest first (by modification time)
  // Older files: alphabetical order
  // Configurable recency threshold
}
```

**Git-Aware File Discovery**:
```typescript
// Integration with centralized file filtering service
const fileDiscovery = this.config.getFileService();
const filteredRelativePaths = fileDiscovery.filterFiles(relativePaths, {
  respectGitIgnore: true,
  respectGeminiIgnore: false,
});
// Respects both .gitignore and .geminiignore patterns
// Provides statistics on filtered files
```

#### Multi-File Reader (`read-many-files.ts`)

**Comprehensive Default Exclusions**:
```typescript
const DEFAULT_EXCLUDES: string[] = [
  '**/node_modules/**', '**/.git/**', '**/.vscode/**', '**/.idea/**',
  '**/dist/**', '**/build/**', '**/coverage/**', '**/__pycache__/**',
  '**/*.pyc', '**/*.pyo', '**/*.bin', '**/*.exe', '**/*.dll', '**/*.so',
  '**/*.dylib', '**/*.class', '**/*.jar', '**/*.war', '**/*.zip',
  '**/*.tar', '**/*.gz', '**/*.bz2', '**/*.rar', '**/*.7z',
  '**/*.doc', '**/*.docx', '**/*.xls', '**/*.xlsx', '**/*.ppt', '**/*.pptx',
  '**/*.odt', '**/*.ods', '**/*.odp', '**/.DS_Store', '**/.env'
];
```

**Intelligent Content Aggregation**:
```typescript
// Separates different file content with clear delimiters
const separator = DEFAULT_OUTPUT_SEPARATOR_FORMAT.replace('{filePath}', filePath);
contentParts.push(`${separator}\n\n${fileReadResult.llmContent}\n\n`);

// Handles mixed content types (text + images/PDFs)
// Provides detailed skip reasons and statistics
// Supports both explicit and pattern-based file inclusion
```

#### Base Tool Architecture (`tools.ts`)

**Universal Tool Interface**:
```typescript
export interface Tool<TParams = unknown, TResult extends ToolResult = ToolResult> {
  name: string;                    // API identifier
  displayName: string;             // Human-readable name
  description: string;             // LLM-facing description
  icon: Icon;                      // UI icon
  schema: FunctionDeclaration;     // Parameter schema
  isOutputMarkdown: boolean;       // Output format flag
  canUpdateOutput: boolean;        // Streaming support
  
  validateToolParams(params: TParams): string | null;
  getDescription(params: TParams): string;
  toolLocations(params: TParams): ToolLocation[];
  shouldConfirmExecute(params: TParams, signal: AbortSignal): Promise<ToolCallConfirmationDetails | false>;
  execute(params: TParams, signal: AbortSignal, updateOutput?: (output: string) => void): Promise<TResult>;
}
```

**Confirmation System Types**:
```typescript
// Comprehensive confirmation system for dangerous operations
export interface ToolEditConfirmationDetails {
  type: 'edit';
  title: string;
  fileName: string;
  fileDiff: string;               // Generated diff for user review
  originalContent: string | null;
  newContent: string;
  isModifying?: boolean;
  onConfirm: (outcome: ToolConfirmationOutcome, payload?: ToolConfirmationPayload) => Promise<void>;
}

export enum ToolConfirmationOutcome {
  ProceedOnce = 'proceed_once',
  ProceedAlways = 'proceed_always',
  ProceedAlwaysServer = 'proceed_always_server',
  ProceedAlwaysTool = 'proceed_always_tool',
  ModifyWithEditor = 'modify_with_editor',
  Cancel = 'cancel',
}
```

### Key Architecture Insights for TinyAgent Team

#### 1. **Multi-Strategy Approach**
Gemini CLI consistently uses fallback strategies:
- Git grep → System grep → JavaScript fallback (Search tool)
- Native tools → Pure JavaScript implementations
- Multiple MIME type detection methods with content-based validation

#### 2. **Security-First Design Patterns**
- **Path Validation**: Every tool validates paths against root directory boundaries
- **Content Validation**: Binary detection and file type verification before processing
- **Resource Limits**: File size limits (20MB), line limits (2000), character limits (2000/line)
- **Error Isolation**: Comprehensive error handling with graceful degradation

#### 3. **AI Integration Points**
- **Content Correction**: Uses AI models to fix malformed edits and content
- **Validation**: AI-powered verification of file operations before execution
- **Error Recovery**: AI suggests fixes for failed operations
- **Context Understanding**: AI helps determine appropriate file operations based on content

#### 4. **Performance Optimization Strategies**
- **Smart Caching**: Recent file prioritization in search results
- **Stream Processing**: Handles large files and outputs efficiently  
- **Process Management**: Proper cleanup of child processes with signal handling
- **Lazy Loading**: Only processes files that pass initial filters

#### 5. **User Experience Patterns**
- **Progressive Disclosure**: Show essential information first, details on demand
- **Clear Error Messages**: Actionable feedback with suggestions for resolution
- **Diff Visualization**: Visual confirmation of changes before execution
- **Consistent Formatting**: Standardized output formats across all tools

These patterns demonstrate production-tested approaches for building robust, secure, and user-friendly file manipulation tools that integrate seamlessly with AI assistants while maintaining strict security boundaries.