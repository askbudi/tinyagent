# Token Tracking Guide for TinyAgent

The TinyAgent framework includes a comprehensive token tracking system that monitors LLM usage and costs across hierarchical agent systems. This is especially important when working with agents that create sub-agents using different LLM providers.

## 🎯 Key Features

- **Accurate LiteLLM Integration**: Uses LiteLLM's response data directly, capturing all token types including thinking tokens, reasoning tokens, and cache tokens
- **Hierarchical Tracking**: Parent agents automatically aggregate usage from child agents
- **Multi-Provider Support**: Tracks costs across different LLM providers (OpenAI, Anthropic, Google, etc.)
- **Real-time Monitoring**: Live usage statistics and cost tracking
- **Detailed Reporting**: Per-model, per-provider breakdowns with JSON export
- **Hook-based Integration**: Seamlessly integrates with TinyAgent's callback system

## 🚀 Quick Start

### Basic Single Agent Tracking

```python
from tinyagent import TinyAgent
from tinyagent.hooks import create_token_tracker
import os

# Create token tracker
tracker = create_token_tracker(
    name="my_agent", 
    enable_detailed_logging=True
)

# Create agent with tracking
agent = TinyAgent(
    model="gpt-4o-mini",
    api_key=os.environ.get("OPENAI_API_KEY")
)
agent.add_callback(tracker)

# Run tasks
await agent.run("Your task here")

# Get usage statistics
usage = tracker.get_total_usage()
print(f"Total tokens: {usage.total_tokens}")
print(f"Total cost: ${usage.cost:.6f}")

# Print detailed report
tracker.print_summary(detailed=True)

# Export to JSON
tracker.save_to_file("usage_report.json")
```

### Hierarchical Agent Tracking

```python
from tinyagent import TinyAgent, tool
from tinyagent.hooks import create_token_tracker

# Create main tracker
main_tracker = create_token_tracker(name="main_agent")

# Create child tracker
sub_tracker = create_token_tracker(
    name="sub_agent", 
    parent_tracker=main_tracker  # Links to parent
)

# Create agents
main_agent = TinyAgent(model="gpt-4o-mini")
sub_agent = TinyAgent(model="claude-3-haiku-20240307")

# Add tracking
main_agent.add_callback(main_tracker)
sub_agent.add_callback(sub_tracker)

# Create delegation tool
@tool(name="delegate", description="Delegate task to sub-agent")
async def delegate_task(task: str) -> str:
    return await sub_agent.run(task)

main_agent.add_tool(delegate_task)

# Run main task (will use both agents)
await main_agent.run("Complex task that needs delegation")

# Get total usage across all agents
total_usage = main_tracker.get_total_usage(include_children=True)
print(f"Total across all agents: {total_usage.total_tokens} tokens, ${total_usage.cost:.6f}")

# Get breakdown by model/provider
model_breakdown = main_tracker.get_model_breakdown(include_children=True)
for model, stats in model_breakdown.items():
    print(f"{model}: {stats.total_tokens} tokens, ${stats.cost:.6f}")
```

## 📊 Understanding Usage Data

The `UsageStats` class captures comprehensive usage information:

```python
@dataclass
class UsageStats:
    prompt_tokens: int = 0           # Input tokens
    completion_tokens: int = 0       # Output tokens  
    total_tokens: int = 0           # Total tokens
    cost: float = 0.0               # Cost in USD
    call_count: int = 0             # Number of API calls
    thinking_tokens: int = 0         # Thinking tokens (o1 models)
    reasoning_tokens: int = 0        # Reasoning tokens
    cache_creation_input_tokens: int = 0  # Cache creation tokens
    cache_read_input_tokens: int = 0      # Cache read tokens
```

## 🔧 Integration with Existing Code

### For Export_APILLM.py Pattern

If you have existing code similar to `export_apillm.py`, here's how to add tracking:

```python
# BEFORE: Basic setup
sub_agents = dict()

@tool(name="Task")
async def task_tool(prompt: str, absolute_workdir: str, description: str) -> str:
    if sub_agents.get(absolute_workdir) is None:
        sub_agents[absolute_workdir] = create_agent(...)
    return await sub_agents[absolute_workdir].run(prompt)

# AFTER: With token tracking
from tinyagent.hooks import create_token_tracker

main_tracker = create_token_tracker(name="main", enable_detailed_logging=True)
sub_trackers = {}

@tool(name="Task")
async def task_tool(prompt: str, absolute_workdir: str, description: str) -> str:
    if sub_agents.get(absolute_workdir) is None:
        # Create child tracker
        sub_tracker = create_token_tracker(
            name=f"sub_{len(sub_agents)}", 
            parent_tracker=main_tracker
        )
        sub_trackers[absolute_workdir] = sub_tracker
        
        # Create and setup agent
        sub_agents[absolute_workdir] = create_agent(...)
        sub_agents[absolute_workdir].add_callback(sub_tracker)
    
    response = await sub_agents[absolute_workdir].run(prompt)
    
    # Log usage
    usage = sub_trackers[absolute_workdir].get_total_usage()
    print(f"Sub-agent used {usage.total_tokens} tokens, cost: ${usage.cost:.6f}")
    
    return response

# Add tracking to main agent
main_agent.add_callback(main_tracker)

# After project completion
main_tracker.print_summary(include_children=True, detailed=True)
```

## 📈 Advanced Features

### Cost Analysis

```python
# Get comprehensive breakdown
total_usage = tracker.get_total_usage(include_children=True)
model_breakdown = tracker.get_model_breakdown(include_children=True)
provider_breakdown = tracker.get_provider_breakdown(include_children=True)

# Calculate efficiency metrics
if total_usage.call_count > 0:
    avg_cost_per_call = total_usage.cost / total_usage.call_count
    avg_tokens_per_call = total_usage.total_tokens / total_usage.call_count
    cost_per_1k_tokens = (total_usage.cost / total_usage.total_tokens) * 1000
    
    print(f"Average cost per call: ${avg_cost_per_call:.6f}")
    print(f"Average tokens per call: {avg_tokens_per_call:.1f}")
    print(f"Cost per 1K tokens: ${cost_per_1k_tokens:.6f}")
```

### Real-time Monitoring

```python
# Enable detailed logging for real-time monitoring
tracker = create_token_tracker(
    name="monitored_agent",
    enable_detailed_logging=True,  # Logs each API call
    track_per_model=True,         # Track usage per model
    track_per_provider=True       # Track usage per provider
)

# The tracker will log:
# - Each API call with token counts and costs
# - Model-specific usage
# - Provider-specific breakdowns
# - Additional token types (thinking, reasoning, cache)
```

### Export and Analysis

```python
# Export detailed JSON report
tracker.save_to_file("detailed_usage.json", include_children=True)

# Get raw data for custom analysis
report_data = tracker.get_detailed_report(include_children=True)

# The report includes:
# - Total usage statistics
# - Per-model breakdown
# - Per-provider breakdown  
# - Child tracker data (hierarchical)
# - Session duration and timing
```

## 🏗️ Integration with TinyCodeAgent

```python
from tinyagent.code_agent import TinyCodeAgent
from tinyagent.hooks import create_token_tracker

# Create tracker
tracker = create_token_tracker(name="code_agent", enable_detailed_logging=True)

# Create code agent
code_agent = TinyCodeAgent(
    model="gpt-4o-mini",
    provider="modal",
    local_execution=True
)

# Add tracking
code_agent.add_callback(tracker)

# Execute code tasks
await code_agent.run("Create a data visualization with matplotlib")

# Track code execution costs
tracker.print_summary(detailed=True)
```

## 💡 Best Practices

1. **Create Trackers Early**: Set up tracking before creating agents for complete coverage
2. **Use Hierarchical Tracking**: Link child trackers to parents for automatic aggregation
3. **Enable Detailed Logging**: Get real-time insights during development and debugging
4. **Regular Reporting**: Print summaries after major tasks to monitor costs
5. **Export Data**: Save detailed reports for cost analysis and optimization
6. **Clean Up**: Always close agents to finalize tracking data

## 🔍 Troubleshooting

### No Usage Data Found
```python
# Check if LiteLLM response has usage data
if not hasattr(response, 'usage'):
    print("Response missing usage data")
    
# Ensure tracker is added to agent
agent.add_callback(tracker)  # Don't forget this!
```

### Missing Child Usage
```python
# Make sure to include children in reports
total_usage = tracker.get_total_usage(include_children=True)  # include_children=True
tracker.print_summary(include_children=True)
```

### Cost Calculation Issues
```python
# LiteLLM provides cost information, TokenTracker extracts it automatically:
# 1. From response._hidden_params["response_cost"] (primary method)
# 2. Using litellm.completion_cost(response) (fallback method)
# 3. From response.usage.cost (if already present)

model_breakdown = tracker.get_model_breakdown()
for model, stats in model_breakdown.items():
    print(f"{model}: {stats.call_count} calls, ${stats.cost:.6f}")
```

## 📚 Examples

- **Complete Example**: `examples/token_tracking_example.py` - Comprehensive hierarchical tracking
- **Integration Guide**: `examples/integrate_with_existing_agents.py` - Add tracking to existing code
- **TinyCodeAgent**: See TinyCodeAgent examples with token tracking

## 🔗 API Reference

### TokenTracker
- `track_llm_call(model, response, **kwargs)` - Track individual LLM call
- `get_total_usage(include_children=False)` - Get total usage statistics  
- `get_model_breakdown(include_children=False)` - Usage by model
- `get_provider_breakdown(include_children=False)` - Usage by provider
- `print_summary(include_children=True, detailed=False)` - Print usage report
- `save_to_file(filepath, include_children=True)` - Export to JSON
- `reset_stats(reset_children=False)` - Reset all statistics

### create_token_tracker()
- `name` - Tracker identifier
- `parent_tracker` - Parent for hierarchical tracking
- `logger` - Optional logger instance
- `enable_detailed_logging` - Real-time logging
- `track_per_model` - Enable per-model tracking
- `track_per_provider` - Enable per-provider tracking 