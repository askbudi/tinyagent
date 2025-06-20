# TinyCodeAgent with User Variables

The TinyCodeAgent now supports passing user variables to the Python execution environment. This allows you to pre-load data, configuration, and other variables that the LLM can use when writing and executing code.

## Features

1. **Initialize with Variables**: Pass variables during agent creation
2. **Dynamic Variable Management**: Add, update, or remove variables after initialization
3. **Automatic Serialization**: Variables are automatically serialized and sent to Modal
4. **Smart System Prompt**: LLM receives information about available variables and their types
5. **Type Detection**: Automatic detection and description of common data types (DataFrames, arrays, etc.)

## Basic Usage

### Initialize with Variables

```python
import pandas as pd
import numpy as np
from tinyagent.code_agent import TinyCodeAgent

# Prepare your data
user_data = {
    "sales_data": [100, 200, 150, 300, 250],
    "config": {"currency": "USD", "tax_rate": 0.08},
    "df": pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}),
    "matrix": np.array([[1, 2], [3, 4]])
}

# Create agent with variables
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    user_variables=user_data
)

# Now the LLM knows about these variables and can use them
result = await agent.run("Calculate the total of sales_data and format with the currency from config")
```

### Add Variables Dynamically

```python
# Add single variable
agent.add_user_variable("target_revenue", 1000)

# Set multiple variables (replaces existing ones)
new_vars = {
    "regions": ["North", "South", "East", "West"],
    "goals": {"q1": 500, "q2": 600}
}
agent.set_user_variables(new_vars)

# Remove a variable
agent.remove_user_variable("old_data")

# Get current variables
current_vars = agent.get_user_variables()
```

## Supported Data Types

The system automatically handles and describes various data types:

- **Basic Types**: `str`, `int`, `float`, `bool`, `list`, `dict`, `tuple`
- **NumPy Arrays**: Shows shape and dtype information
- **Pandas DataFrames**: Shows shape, columns, and data types
- **Custom Objects**: Serializable objects via cloudpickle

## System Prompt Integration

When you provide user variables, the LLM receives information like:

```
## Available Variables

The following variables are pre-loaded and available in your Python environment:

- **sales_data** (list): list with 5 items (first item type: int)
- **config** (dict): Dictionary with 2 keys. Sample keys: ['currency', 'tax_rate']
- **df** (DataFrame): DataFrame with shape (3, 2) and columns: ['A', 'B']
- **matrix** (ndarray): Array with shape (2, 2) and dtype int64

These variables are already loaded and ready to use in your code. You don't need to import or define them.
You can directly reference them by name in your Python code.
```

## Serialization and Modal Integration

Variables are automatically:
1. **Serialized** using `cloudpickle` for complex objects
2. **Injected** into the Modal execution environment
3. **Available** in the global scope of your Python code
4. **Persistent** across multiple code executions in the same session

## Example: Data Analysis Workflow

```python
import pandas as pd
from tinyagent.code_agent import TinyCodeAgent

# Load your data
df = pd.read_csv("sales_data.csv")
config = {
    "target_growth": 0.15,
    "currency": "USD",
    "regions": ["US", "EU", "ASIA"]
}

# Create agent with your data
agent = TinyCodeAgent(
    model="gpt-4o-mini",
    user_variables={
        "sales_df": df,
        "business_config": config,
        "analysis_date": "2024-Q1"
    }
)

# The LLM can now work with your data directly
await agent.run("""
Analyze the sales_df to:
1. Calculate growth rates by region
2. Compare against target_growth from business_config
3. Generate insights for each region in business_config['regions']
4. Create a summary report for analysis_date period
""")
```

## Best Practices

1. **Variable Naming**: Use clear, descriptive names
2. **Data Size**: Be mindful of large datasets (serialization overhead)
3. **Type Consistency**: Ensure variables are serializable
4. **Documentation**: Use descriptive variable names that hint at their purpose
5. **Session Management**: Variables persist across runs in the same session

## Error Handling

If a variable can't be serialized, it will be skipped with a warning. Common issues:
- File handles or network connections
- Lambda functions (use regular functions instead)
- Complex custom objects without proper serialization support

## Performance Considerations

- Variables are serialized once when set/added
- Large datasets may impact initialization time
- Consider chunking very large datasets
- Variables are loaded once per Modal execution session

## Advanced Usage

### Working with Large DataFrames

```python
# For large datasets, consider providing metadata
large_df = pd.read_csv("huge_dataset.csv")

agent.add_user_variable("dataset", large_df)
agent.add_user_variable("dataset_info", {
    "rows": len(large_df),
    "columns": list(large_df.columns),
    "memory_usage": large_df.memory_usage(deep=True).sum()
})

await agent.run("First, examine dataset_info to understand the data structure, then sample the dataset for analysis")
```

### Configuration-Driven Analysis

```python
analysis_config = {
    "metrics": ["revenue", "profit", "growth"],
    "time_periods": ["Q1", "Q2", "Q3", "Q4"],
    "output_format": "executive_summary",
    "currency": "USD"
}

agent.set_user_variables({
    "data": your_dataframe,
    "config": analysis_config
})

await agent.run("Perform the analysis specified in the config dictionary using the provided data")
``` 