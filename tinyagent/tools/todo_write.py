"""
TodoWrite tool implementation for structured task management in TinyAgent.

This module provides the TodoWrite tool that allows agents to create and manage
structured todo lists during conversation sessions, helping track progress and
organize complex tasks.
"""

import json
import logging
import uuid
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from tinyagent import tool


@dataclass
class TodoItem:
    """Represents a single todo item with content, status, and unique ID."""
    content: str
    status: str  # "pending", "in_progress", "completed"
    id: str
    
    def __post_init__(self):
        """Validate todo item after initialization."""
        valid_statuses = {"pending", "in_progress", "completed"}
        if self.status not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        
        if not self.content.strip():
            raise ValueError("Todo content cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert todo item to dictionary representation."""
        return asdict(self)


class TodoManager:
    """Manages todo lists with validation and persistence."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._todos: List[TodoItem] = []
    
    def update_todos(self, todos_data: List[Dict[str, Any]]) -> List[TodoItem]:
        """
        Update the current todo list with new data.
        
        Args:
            todos_data: List of dictionaries representing todo items
            
        Returns:
            List of TodoItem objects
            
        Raises:
            ValueError: If todo data is invalid
        """
        try:
            new_todos = []
            
            # Validate and create todo items
            for todo_dict in todos_data:
                # Ensure required fields are present
                if not all(key in todo_dict for key in ["content", "status", "id"]):
                    raise ValueError("Each todo must have 'content', 'status', and 'id' fields")
                
                todo_item = TodoItem(
                    content=todo_dict["content"],
                    status=todo_dict["status"],
                    id=todo_dict["id"]
                )
                new_todos.append(todo_item)
            
            # Validate business rules
            self._validate_todo_list(new_todos)
            
            # Update internal state
            self._todos = new_todos
            
            self.logger.info(f"Updated todo list with {len(new_todos)} items")
            return new_todos
            
        except Exception as e:
            error_msg = f"Failed to update todo list: {str(e)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
    
    def _validate_todo_list(self, todos: List[TodoItem]):
        """
        Validate business rules for the todo list.
        
        Args:
            todos: List of TodoItem objects to validate
            
        Raises:
            ValueError: If validation fails
        """
        # Check for duplicate IDs
        ids = [todo.id for todo in todos]
        if len(ids) != len(set(ids)):
            raise ValueError("Todo IDs must be unique")
        
        # Check that only one task is in progress at a time
        in_progress_count = sum(1 for todo in todos if todo.status == "in_progress")
        if in_progress_count > 1:
            raise ValueError("Only one todo can be 'in_progress' at a time")
    
    def get_todos(self) -> List[Dict[str, Any]]:
        """Get current todo list as dictionaries."""
        return [todo.to_dict() for todo in self._todos]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the current todo list."""
        if not self._todos:
            return {"total": 0, "pending": 0, "in_progress": 0, "completed": 0}
        
        summary = {"total": len(self._todos)}
        for status in ["pending", "in_progress", "completed"]:
            summary[status] = sum(1 for todo in self._todos if todo.status == status)
        
        return summary


# Global todo manager instance
_todo_manager = TodoManager()


def get_todo_manager() -> TodoManager:
    """Get the global todo manager instance."""
    return _todo_manager


@tool(
    name="TodoWrite",
    description="""Use this tool to create and manage a structured task list for your current coding session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
It also helps the user understand the progress of the task and overall progress of their requests.

## When to Use This Tool
Use this tool proactively in these scenarios:

1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
3. User explicitly requests todo list - When the user directly asks you to use the todo list
4. User provides multiple tasks - When users provide a list of things to be done (numbered or comma-separated)
5. After receiving new instructions - Immediately capture user requirements as todos
6. When you start working on a task - Mark it as in_progress BEFORE beginning work. Ideally you should only have one todo as in_progress at a time
7. After completing a task - Mark it as completed and add any new follow-up tasks discovered during implementation

## When NOT to Use This Tool

Skip using this tool when:
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no organizational benefit
3. The task can be completed in less than 3 trivial steps
4. The task is purely conversational or informational

NOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly.

## Task States and Management

1. **Task States**: Use these states to track progress:
   - pending: Task not yet started
   - in_progress: Currently working on (limit to ONE task at a time)
   - completed: Task finished successfully

2. **Task Management**:
   - Update task status in real-time as you work
   - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
   - Only have ONE task in_progress at any time
   - Complete current tasks before starting new ones
   - Remove tasks that are no longer relevant from the list entirely

3. **Task Completion Requirements**:
   - ONLY mark a task as completed when you have FULLY accomplished it
   - If you encounter errors, blockers, or cannot finish, keep the task as in_progress
   - When blocked, create a new task describing what needs to be resolved
   - Never mark a task as completed if:
     - Tests are failing
     - Implementation is partial
     - You encountered unresolved errors
     - You couldn't find necessary files or dependencies

4. **Task Breakdown**:
   - Create specific, actionable items
   - Break complex tasks into smaller, manageable steps
   - Use clear, descriptive task names

When in doubt, use this tool. Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully.""",
    schema={
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Description of the task"
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "Current status of the task"
                        },
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for the task (optional, will be auto-generated if not provided)"
                        }
                    },
                    "required": ["content", "status"],
                    "additionalProperties": False
                },
                "description": "List of todo items to update"
            }
        },
        "required": ["todos"],
        "additionalProperties": False
    }
)
def todo_write(todos: Union[str, List[Dict[str, Any]], Dict[str, Any]]) -> str:
    """
    Update the current todo list with new items and their statuses.
    
    Args:
        todos: List of todo items (or JSON string, or single dict), each containing:
            - content (str): Description of the task  
            - status (str): One of "pending", "in_progress", "completed"
            - id (str): Unique identifier for the task (optional, auto-generated if missing)
            
            Note: Also accepts "task" field instead of "content" for compatibility.
    
    Returns:
        A formatted summary of the updated todo list
    """
    try:
        manager = get_todo_manager()
        
        # Handle case where todos might be passed as JSON string
        if isinstance(todos, str):
            try:
                todos = json.loads(todos)
            except json.JSONDecodeError as e:
                return f"Error: Invalid JSON format for todos: {str(e)}"
        
        # Normalize input to list format
        if isinstance(todos, dict):
            # Handle case where a single todo dict was passed instead of a list
            todos = [todos]
        elif not isinstance(todos, list):
            # Handle any other unexpected types
            return f"Error: todos must be a list or a single todo dictionary, got {type(todos).__name__}"
        
        # Generate IDs for todos that don't have them and normalize field names
        for todo in todos:
            if not isinstance(todo, dict):
                return f"Error: Each todo must be a dictionary, got {type(todo).__name__}"
            
            # Handle cases where LLM uses "task" instead of "content"
            if "task" in todo and "content" not in todo:
                todo["content"] = todo.pop("task")
            
            # Generate ID if missing
            if not todo.get("id"):
                todo["id"] = str(uuid.uuid4())[:8]
        
        # Update the todo list
        updated_todos = manager.update_todos(todos)
        
        # Generate summary
        summary = manager.get_summary()
        
        # Format response
        response_lines = [
            "Todo list updated successfully!",
            "",
            f"Summary: {summary['total']} total tasks",
            f"  • Pending: {summary['pending']}",
            f"  • In Progress: {summary['in_progress']}",
            f"  • Completed: {summary['completed']}",
            ""
        ]
        
        if updated_todos:
            response_lines.append("Current todos:")
            for todo in updated_todos:
                status_emoji = {
                    "pending": "⏳",
                    "in_progress": "🔄",
                    "completed": "✅"
                }.get(todo.status, "❓")
                
                response_lines.append(f"  {status_emoji} [{todo.id}] {todo.content}")
        
        return "\n".join(response_lines)
        
    except Exception as e:
        error_msg = f"Error updating todo list: {str(e)}"
        logger = logging.getLogger(__name__)
        logger.error(error_msg)
        logger.debug(f"TodoWrite input type: {type(todos)}, value: {repr(todos)[:500]}")
        return error_msg


def enable_todo_write_tool(agent, enabled: bool = True):
    """
    Enable or disable the TodoWrite tool for an agent.
    
    Args:
        agent: TinyAgent or TinyCodeAgent instance
        enabled: Whether to enable the tool (default: True)
    """
    if enabled:
        if not hasattr(agent, '_todo_write_enabled') or not agent._todo_write_enabled:
            agent.add_tool(todo_write)
            agent._todo_write_enabled = True
            
            if hasattr(agent, 'logger'):
                agent.logger.info("TodoWrite tool enabled")
    else:
        # Remove the tool if it was added
        if hasattr(agent, '_todo_write_enabled') and agent._todo_write_enabled:
            # Remove from available tools
            if hasattr(agent, 'available_tools'):
                agent.available_tools = [
                    tool for tool in agent.available_tools 
                    if tool.get("function", {}).get("name") != "TodoWrite"
                ]
            
            # Remove from custom tools
            if hasattr(agent, 'custom_tools'):
                agent.custom_tools = [
                    tool for tool in agent.custom_tools 
                    if tool.get("function", {}).get("name") != "TodoWrite"
                ]
                
            # Remove from custom tool handlers
            if hasattr(agent, 'custom_tool_handlers'):
                agent.custom_tool_handlers.pop("TodoWrite", None)
            
            agent._todo_write_enabled = False
            
            if hasattr(agent, 'logger'):
                agent.logger.info("TodoWrite tool disabled")


def get_current_todos() -> List[Dict[str, Any]]:
    """Get the current todo list."""
    return get_todo_manager().get_todos()


def get_todo_summary() -> Dict[str, Any]:
    """Get a summary of the current todo list."""
    return get_todo_manager().get_summary()