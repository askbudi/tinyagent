# Changelog

All notable changes to TinyAgent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **🚀 Subagent Tools System** - Revolutionary parallel task execution with clean context isolation
  - `tinyagent.tools.subagent` - Complete subagent toolkit for creating specialized AI workers
  - `SubagentConfig` - Comprehensive configuration system with parent agent inheritance
  - `SubagentContext` - Context management with automatic resource cleanup and execution tracking
  - `ContextManager` - Global context manager with automatic resource lifecycle management
  - Factory functions for specialized subagents: `create_research_subagent`, `create_coding_subagent`, `create_analysis_subagent`, `create_writing_subagent`, `create_planning_subagent`
  - `create_general_subagent` - General-purpose subagent with Python/shell execution capabilities
  - Automatic parent agent parameter inheritance (model, API keys, callbacks, logging, etc.)
  - Custom agent factory support for maximum flexibility and extensibility

- **Anthropic Prompt Caching** - Basic caching for Claude models to reduce API costs
  - `anthropic_prompt_cache()` - Cache callback for Claude-3 and Claude-4 models
  - `AnthropicPromptCacheCallback` - Core callback class for cache control
  - Automatic model detection (supports all Claude-3 and Claude-4 models)
  - Smart content length detection (adds cache control only to messages >1000 tokens)
  - Zero-configuration setup using TinyAgent's native callback system

### Enhanced  
- **Hook System** - Added Anthropic prompt cache integration following TinyAgent's callback patterns
- **Architecture** - Revolutionary subagent system with context isolation and resource management
- **Documentation** - Updated README with Anthropic caching usage examples
- **Examples** - Added Anthropic prompt cache example demonstrating basic usage

### Technical Details

#### Subagent System Architecture
- **SubagentConfig** - Dataclass-based configuration with automatic parameter inheritance from parent agents
- **SubagentContext** - Complete execution context with metadata tracking, resource management, and cleanup callbacks
- **ContextManager** - Singleton manager with periodic cleanup, stale context detection, and async context management
- **Agent Factory Pattern** - Pluggable agent creation with support for TinyAgent, TinyCodeAgent, and custom agent factories
- **Resource Lifecycle** - Automatic resource cleanup with context managers and async cleanup callbacks
- **Hook Integration** - Full integration with TinyAgent's callback system including LoggingManager, token tracking, and UI callbacks
- **Parameter Inheritance** - Intelligent parameter extraction from parent agents with selective overrides
- **Execution Isolation** - Complete context separation between subagents with independent conversation histories
- **Timeout Management** - Configurable timeouts with automatic context cleanup on timeout
- **Working Directory Management** - Per-subagent working directory control with environment variable support

#### Anthropic Prompt Caching  
- **AnthropicPromptCacheCallback** - Lightweight callback that adds `cache_control: {"type": "ephemeral"}` to large messages
- **Model Support** - Supports all Claude-3 and Claude-4 models using pattern matching ("claude-3", "claude-4")  
- **Content Detection** - Uses 4000+ character threshold (~1000 tokens) to determine when to add caching
- **Message Format** - Converts string content to structured format when adding cache control
- **Case Insensitive** - Model detection works regardless of model name casing

### Benefits

#### Subagent System Benefits
- **🔄 Parallel Processing** - Execute multiple specialized tasks concurrently with complete isolation
- **🧠 Specialized Intelligence** - Create domain-specific agents (research, coding, analysis, writing, planning)
- **🛡️ Resource Safety** - Automatic cleanup prevents memory leaks and resource exhaustion
- **🔗 Seamless Integration** - Inherits parent agent configuration (API keys, models, callbacks) automatically
- **🎯 Context Isolation** - Each subagent has independent conversation history and execution context
- **⚙️ Extensible Architecture** - Custom agent factories allow integration with any agent implementation
- **📊 Execution Tracking** - Complete metadata tracking with execution logs, duration, and resource usage
- **🔧 Developer Experience** - Simple factory functions with sensible defaults and comprehensive configuration options
- **🏗️ Production Ready** - Timeout management, error handling, and automatic context cleanup for enterprise use

#### Anthropic Prompt Caching Benefits
- **Cost Optimization** - Automatic caching for substantial messages reduces API costs
- **Developer Experience** - Simple one-line setup: `agent.add_callback(anthropic_prompt_cache())`
- **Zero Configuration** - Works out of the box with sensible defaults
- **Future-Proof** - Automatically supports new Claude-3 and Claude-4 model variants

## [0.0.19] - Previous Release

### Added
- Examples for bank account analysis and data extraction using TinyCodeAgent
- Enhanced TinyCodeAgent functionality

### Changed
- Updated version to 0.0.19

## [0.0.18] - Previous Release

### Enhanced
- Error logging in MCPClient and TinyAgent callbacks
- Environment variable support in MCP STDIO

### Changed
- Updated version to 0.0.18

---

## Migration Guide

### Using the New Subagent System

The subagent system revolutionizes how you can break down complex tasks into specialized, parallel executions:

**Basic Subagent Usage:**
```python
from tinyagent import TinyAgent
from tinyagent.tools.subagent import create_general_subagent, create_coding_subagent

# Create main agent
main_agent = TinyAgent(model="gpt-4o-mini", api_key="your-key")

# Add a general-purpose subagent tool
general_helper = create_general_subagent(
    name="helper",
    model="gpt-4.1-mini",
    max_turns=15
)
main_agent.add_tool(general_helper)

# Add a specialized coding subagent
coding_assistant = create_coding_subagent(
    name="coder",
    model="claude-3-sonnet",  
    max_turns=25,
    enable_python_tool=True,
    enable_shell_tool=True
)
main_agent.add_tool(coding_assistant)

# Use them in conversation
result = await main_agent.run(
    "Use coder to implement a sorting algorithm, "
    "then use helper to write documentation for it"
)
```

**Advanced Configuration with Parent Inheritance:**
```python
from tinyagent.tools.subagent import SubagentConfig, create_subagent_tool

# Create configuration that inherits from parent
config = SubagentConfig.from_parent_agent(
    parent_agent=main_agent,  # Inherits API keys, callbacks, logging
    model="gpt-4o",           # Override model
    max_turns=20,             # Override max turns
    enable_python_tool=True,  # Enable code execution
    timeout=300               # 5 minute timeout
)

# Create custom subagent with inherited configuration
research_tool = create_subagent_tool("researcher", config)
main_agent.add_tool(research_tool)
```

**Custom Agent Factory Integration:**
```python
def my_custom_agent_factory(**kwargs):
    # Create any kind of agent you want
    return TinyCodeAgent(
        provider="modal",
        provider_config={"timeout": 120},
        **kwargs
    )

# Use custom factory
config = SubagentConfig(model="claude-3-sonnet", max_turns=15)
custom_tool = create_subagent_tool(
    name="custom_coder",
    config=config,
    agent_factory=my_custom_agent_factory
)
main_agent.add_tool(custom_tool)
```

### Upgrading to Anthropic Prompt Caching

If you're upgrading from a previous version and want to add caching:

**Before:**
```python
from tinyagent import TinyAgent

agent = TinyAgent(model="claude-3-5-sonnet-20241022")
response = await agent.run("Your prompt")
```

**After:**
```python
from tinyagent import TinyAgent
from tinyagent.hooks import anthropic_prompt_cache

agent = TinyAgent(model="claude-3-5-sonnet-20241022")
cache_callback = anthropic_prompt_cache()
agent.add_callback(cache_callback)

response = await agent.run("Your prompt")  # Caching happens automatically
```

### Breaking Changes
- None in this release. Anthropic prompt caching is fully backward compatible.

### Deprecations  
- None in this release.

---

## Future Roadmap

### Planned Features
- Cache persistence across sessions
- Multi-model caching support (GPT, Claude, etc.)
- Advanced cache warming strategies
- Integration with external cache stores (Redis, etc.)
- Cache analytics dashboard
- Automatic cache optimization based on usage patterns

### Under Consideration
- Cross-conversation cache sharing
- Distributed caching for multi-instance deployments
- Cache compression for large content
- Machine learning-based cache prediction

---

## Contributing

When contributing new features:

1. **Update CHANGELOG.md** - Add your changes under `[Unreleased]`
2. **Add Examples** - Include usage examples in the `examples/` directory
3. **Update Documentation** - Update README.md and relevant .md files
4. **Add Tests** - Include tests for new functionality
5. **Follow Patterns** - Use existing code patterns and hook architecture

### Changelog Format

Use these section headers as appropriate:
- `Added` for new features
- `Changed` for changes in existing functionality  
- `Deprecated` for soon-to-be removed features
- `Removed` for now removed features
- `Fixed` for any bug fixes
- `Security` for vulnerability fixes

### Version Numbering

- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible