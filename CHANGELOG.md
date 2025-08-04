# Changelog

All notable changes to TinyAgent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Anthropic Prompt Caching** - Basic caching for Claude models to reduce API costs
  - `anthropic_prompt_cache()` - Cache callback for Claude-3 and Claude-4 models
  - `AnthropicPromptCacheCallback` - Core callback class for cache control
  - Automatic model detection (supports all Claude-3 and Claude-4 models)
  - Smart content length detection (adds cache control only to messages >1000 tokens)
  - Zero-configuration setup using TinyAgent's native callback system

### Enhanced  
- **Hook System** - Added Anthropic prompt cache integration following TinyAgent's callback patterns
- **Documentation** - Updated README with Anthropic caching usage examples
- **Examples** - Added Anthropic prompt cache example demonstrating basic usage

### Technical Details
- **AnthropicPromptCacheCallback** - Lightweight callback that adds `cache_control: {"type": "ephemeral"}` to large messages
- **Model Support** - Supports all Claude-3 and Claude-4 models using pattern matching ("claude-3", "claude-4")  
- **Content Detection** - Uses 4000+ character threshold (~1000 tokens) to determine when to add caching
- **Message Format** - Converts string content to structured format when adding cache control
- **Case Insensitive** - Model detection works regardless of model name casing

### Benefits
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