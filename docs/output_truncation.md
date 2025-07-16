# Output Truncation in TinyCodeAgent

TinyCodeAgent includes a feature to automatically truncate large outputs from Python code execution and shell commands. This helps prevent overwhelming the LLM with excessive output, which can lead to context window limitations and reduced performance.

## How It Works

When a Python script or shell command produces a large output, TinyCodeAgent can automatically truncate it based on configurable limits:

1. **Token Limit**: Maximum number of tokens (approximately 4 characters per token) to include in the output
2. **Line Limit**: Maximum number of lines to include in the output

If the output exceeds either of these limits, it will be truncated and a message will be added explaining that truncation occurred.

## Configuration

You can configure the truncation behavior when creating a TinyCodeAgent instance:

```python
from tinyagent.code_agent import TinyCodeAgent

agent = TinyCodeAgent(
    model="gpt-4.1-mini",
    truncation_config={
        "max_tokens": 3000,    # Maximum tokens to keep (default: 3000)
        "max_lines": 250,      # Maximum lines to keep (default: 250)
        "enabled": True        # Whether truncation is enabled (default: True)
    }
)
```

### Default Values

- `max_tokens`: 3000
- `max_lines`: 250
- `enabled`: True

## Customizing Truncation at Runtime

You can modify the truncation configuration after creating the agent:

```python
# Update all truncation settings
agent.set_truncation_config({
    "max_tokens": 5000,
    "max_lines": 500,
    "enabled": True
})

# Get current truncation settings
config = agent.get_truncation_config()
print(f"Max tokens: {config['max_tokens']}")
print(f"Max lines: {config['max_lines']}")

# Enable or disable truncation
agent.enable_truncation(True)   # Enable
agent.enable_truncation(False)  # Disable
```

## Customizing Truncation Messages

The truncation messages are stored in a YAML template file at `tinyagent/prompts/truncation.yaml`. You can customize these messages by modifying this file.

Default template structure:

```yaml
truncation_messages:
  python_output:
    message: |-
      ---
      **Output Truncated**: The original output was {original_size} {size_unit} ({original_lines} lines). Showing only the last {max_lines} lines.
      To get more detailed output, please make your request more specific or adjust the output size.
      ---
  bash_output:
    message: |-
      ---
      **Output Truncated**: The original output was {original_size} {size_unit} ({original_lines} lines). Showing only the last {max_lines} lines.
      To get more detailed output, please use more specific commands or add filtering.
      ---
```

The following variables are available for use in the templates:

- `{original_size}`: The size of the original output (in tokens or K tokens)
- `{size_unit}`: The unit of measurement ("tokens" or "K tokens")
- `{original_lines}`: The number of lines in the original output
- `{max_lines}`: The maximum number of lines configured for truncation

## Truncation Logic

When truncation is needed:

1. First, the output is truncated by lines, keeping the last `max_lines` lines
2. If the result still exceeds the token limit, it's further truncated to approximately `max_tokens` tokens
3. The truncation message is added to the output to inform the LLM about the truncation

## Best Practices

- Set appropriate limits based on your LLM's context window size
- For debugging large outputs, temporarily disable truncation
- For production use, keep truncation enabled to prevent context window overflow
- Adjust the truncation message to guide the LLM on how to request more specific information 