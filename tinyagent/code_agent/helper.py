
import yaml
from jinja2 import Template
from textwrap import dedent
import asyncio
from typing import Any, Dict
import inspect
from typing import get_type_hints


prompt_code_example = dedent("""
User: How the following repo has implemented Logging, and how can I make it compatible with Facebook Standard Logging? github url: https://github.com/askbudi/tinyagent
                             
function_calling: run_python
run_python("task='How the following repo has implemented Logging, and how can I make it compatible with Facebook Standard Logging?'",
                             "repo_result = code_research(repo_url='https://github.com/askbudi/tinyagent',task='How the following repo has implemented Logging, and how can I make it compatible with Facebook Standard Logging?')",
                             "print(repo_result)",
                             "answer_for_user_review = problem_solver(task=task,context=repo_result)",
                             "print(answer_for_user_review)",


""")

prompt_qwen_helper = dedent("""

**Your learning from past mistakes**     
- Always think step by step about the task, what is it, how can you solve it, what are the steps you need to take to solve it.
- When you write a code and receive an error from run_python , go through your code and error step by step, you need to debug your code.  
- You are an Agent, You need to solve the task, not suggesting user about how to solve the task.                         
- User can't directly see the response of run_python tool, so you need to use final_answer or ask_question whenever you want to show a response to the user.
Other tools calls and their responses are not visible to the user.
- run_python is a capable tool, if you need to call a function with different arguments, you can do it in one take, just like you would do in a python code you developed to be executed in one cell of Jupyter Notebook Cell.
- When Task is not resolvable using functions available in your python enviroment, first think about creating a new function to solve the task, then ask the user about your approach and your code, if user allowed you to use it, then define and execute your custom made function. [It is your super power, you can create functions to solve the task.]
- When you are defining a new function, you need to add any needed imports inside the function.
                            Example: instead of:
                            import requests
                            def get_weather_data(city: str,api_key: str) -> str:
                                response = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}")
                                return response.json()
                            You should do it like this: Otherwise you will get an error.
                            def get_weather_data(city: str,api_key: str) -> str:
                                import requests
                                response = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}")
                                return response.json()
---
You are an Agent, You need to solve the task, not suggesting user about how to solve the task. Facing an error? Think about the error and try another approach to solve the task.

                            """)

def load_template(path: str,key:str="system_prompt") -> str:
    """
    Load the YAML file and extract its 'system_prompt' field.
    """
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data[key]

def render_system_prompt(template_str: str,
                         tools: dict,
                         managed_agents: dict,
                         authorized_imports) -> str:
    """
    Render the Jinja2 template with the given context.
    """
    tmpl = Template(template_str)
    return tmpl.render(
        tools=tools,
        managed_agents=managed_agents,
        authorized_imports=authorized_imports
    )



def translate_tool_for_code_agent(tool_func_or_class: Any) -> Dict[str, Any]:
    """
    Translate a tool decorated with @tool into a format compatible with code_agent.yaml.
    
    Args:
        tool_func_or_class: A function or class decorated with @tool
        
    Returns:
        A dictionary with the tool configuration in code_agent.yaml format
    """
    def _get_type_as_string(type_hint: Any) -> str:
        """
        Convert a type hint to its string representation.
        
        Args:
            type_hint: The type hint to convert
            
        Returns:
            String representation of the type
        """
        if type_hint is Any:
            return "Any"
        
        # Handle common types
        type_map = {
            str: "str",
            int: "int",
            float: "float",
            bool: "bool",
            list: "List",
            dict: "Dict",
            tuple: "Tuple",
            None: "None"
        }
        
        if type_hint in type_map:
            return type_map[type_hint]
        
        # Try to get the name attribute
        if hasattr(type_hint, "__name__"):
            return type_hint.__name__
        
        # For generic types like List[str], Dict[str, int], etc.
        return str(type_hint).replace("typing.", "")
    # Check if the tool has the required metadata
    if not hasattr(tool_func_or_class, '_tool_metadata'):
        raise ValueError("Tool must be decorated with @tool decorator")
    
    metadata = tool_func_or_class._tool_metadata
    
    # Check if it's an async function
    is_async = asyncio.iscoroutinefunction(tool_func_or_class)
    if metadata["is_class"] and hasattr(tool_func_or_class, "__call__"):
        is_async = asyncio.iscoroutinefunction(tool_func_or_class.__call__)
    
    # Get the function signature for parameter types
    if metadata["is_class"]:
        func_to_inspect = tool_func_or_class.__init__
    else:
        func_to_inspect = tool_func_or_class
    
    sig = inspect.signature(func_to_inspect)
    type_hints = get_type_hints(func_to_inspect)
    
    # Build inputs dictionary
    inputs = {}
    for name, param in sig.parameters.items():
        if name in ['self', 'cls']:
            continue
            
        param_type = type_hints.get(name, Any)
        param_type_str = _get_type_as_string(param_type)
        
        # Get parameter description from schema if available
        param_desc = ""
        if metadata["schema"] and "properties" in metadata["schema"]:
            if name in metadata["schema"]["properties"]:
                param_desc = metadata["schema"]["properties"][name].get("description", "")
        
        inputs[name] = {
            "type": param_type_str,
            "description": param_desc
        }
    
    # Determine output type
    output_type = "Any"
    if "return" in type_hints:
        output_type = _get_type_as_string(type_hints["return"])
    
    # Create the tool config
    tool_config = {
        "name": metadata["name"],
        "description": metadata["description"],
        "inputs": inputs,
        "output_type": output_type,
        "is_async": is_async
    }
    
    return tool_config

