from textwrap import dedent
from typing import Optional, List, Dict, Any
from tinyagent import TinyAgent, tool
from tinyagent.hooks.logging_manager import LoggingManager
from .providers.base import CodeExecutionProvider
from .providers.modal_provider import ModalProvider
from .helper import translate_tool_for_code_agent, load_template, render_system_prompt, prompt_code_example, prompt_qwen_helper


class TinyCodeAgent:
    """
    A TinyAgent specialized for code execution tasks.
    
    This class provides a high-level interface for creating agents that can execute
    Python code using various providers (Modal, Docker, local execution, etc.).
    """
    
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: Optional[str] = None,
        log_manager: Optional[LoggingManager] = None,
        provider: str = "modal",
        tools: Optional[List[Any]] = None,
        authorized_imports: Optional[List[str]] = None,
        system_prompt_template: Optional[str] = None,
        provider_config: Optional[Dict[str, Any]] = None,
        **agent_kwargs
    ):
        """
        Initialize TinyCodeAgent.
        
        Args:
            model: The language model to use
            api_key: API key for the model
            log_manager: Optional logging manager
            provider: Code execution provider ("modal", "local", etc.)
            tools: List of tools to add to the agent
            authorized_imports: List of authorized Python imports
            system_prompt_template: Path to custom system prompt template
            provider_config: Configuration for the code execution provider
            **agent_kwargs: Additional arguments passed to TinyAgent
        """
        self.model = model
        self.api_key = api_key
        self.log_manager = log_manager
        self.tools = tools or []
        self.authorized_imports = authorized_imports or ["tinyagent", "gradio", "requests", "asyncio"]
        self.provider_config = provider_config or {}
        
        # Create the code execution provider
        self.code_provider = self._create_provider(provider, self.provider_config)
        
        # Build system prompt
        self.system_prompt = self._build_system_prompt(system_prompt_template)
        
        # Create the underlying TinyAgent
        self.agent = TinyAgent(
            model=model,
            api_key=api_key,
            system_prompt=self.system_prompt,
            logger=log_manager.get_logger('tinyagent.tiny_agent') if log_manager else None,
            **agent_kwargs
        )
        
        # Add the code execution tool
        self._setup_code_execution_tool()
        
        # Add user-provided tools
        if self.tools:
            self.agent.add_tools(self.tools)
    
    def _create_provider(self, provider_type: str, config: Dict[str, Any]) -> CodeExecutionProvider:
        """Create a code execution provider based on the specified type."""
        if provider_type.lower() == "modal":
            return ModalProvider(
                log_manager=self.log_manager,
                code_tools=self.tools,
                **config
            )
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")
    
    def _build_system_prompt(self, template_path: Optional[str] = None) -> str:
        """Build the system prompt for the code agent."""
        # Use default template if none provided
        if template_path is None:
            template_path = "./prompts/code_agent.yaml"
        
        # Translate tools to code agent format
        tools_metadata = {}
        for tool in self.tools:
            if hasattr(tool, '_tool_metadata'):
                metadata = translate_tool_for_code_agent(tool)
                tools_metadata[metadata["name"]] = metadata
        
        # Load and render template
        try:
            template_str = load_template(template_path)
            system_prompt = render_system_prompt(
                template_str, 
                tools_metadata, 
                {}, 
                self.authorized_imports
            )
            return system_prompt + prompt_code_example + prompt_qwen_helper
        except Exception as e:
            # Fallback to a basic prompt if template loading fails
            return self._get_fallback_prompt()
    
    def _get_fallback_prompt(self) -> str:
        """Get a fallback system prompt if template loading fails."""
        return dedent("""
        You are a helpful AI assistant that can execute Python code to solve problems.
        
        You have access to a run_python tool that can execute Python code in a sandboxed environment.
        Use this tool to solve computational problems, analyze data, or perform any task that requires code execution.
        
        When writing code:
        - Always think step by step about the task
        - Use print() statements to show intermediate results
        - Handle errors gracefully
        - Provide clear explanations of your approach
        
        The user cannot see the direct output of run_python, so use final_answer to show results.
        """)
    
    def _setup_code_execution_tool(self):
        """Set up the run_python tool using the code provider."""
        @tool(name="run_python", description=dedent("""
        This tool receives Python code and executes it in a sandboxed environment.
        During each intermediate step, you can use 'print()' to save important information.
        These print outputs will appear in the 'Observation:' field for the next step.

        Args:
            code_lines: list[str]: The Python code to execute as a list of strings.
                Your code should include all necessary steps for successful execution,
                cover edge cases, and include error handling.
                Each line should be an independent line of code.

        Returns:
            Status of code execution or error message.
        """))
        async def run_python(code_lines: List[str], timeout: int = 120) -> str:
            """Execute Python code using the configured provider."""
            try:
                result = await self.code_provider.execute_python(code_lines, timeout)
                return str(result)
            except Exception as e:
                return f"Error executing code: {str(e)}"
        
        self.agent.add_tool(run_python)
    
    async def run(self, user_input: str, max_turns: int = 10) -> str:
        """
        Run the code agent with the given input.
        
        Args:
            user_input: The user's request or question
            max_turns: Maximum number of conversation turns
            
        Returns:
            The agent's response
        """
        return await self.agent.run(user_input, max_turns)
    
    async def connect_to_server(self, command: str, args: List[str], **kwargs):
        """Connect to an MCP server."""
        return await self.agent.connect_to_server(command, args, **kwargs)
    
    def add_callback(self, callback):
        """Add a callback to the agent."""
        self.agent.add_callback(callback)
    
    def add_tool(self, tool):
        """Add a tool to the agent."""
        self.agent.add_tool(tool)
    
    def add_tools(self, tools: List[Any]):
        """Add multiple tools to the agent."""
        self.agent.add_tools(tools)
    
    async def close(self):
        """Clean up resources."""
        await self.code_provider.cleanup()
        await self.agent.close()
    
    def clear_conversation(self):
        """Clear the conversation history."""
        self.agent.clear_conversation()
    
    @property
    def messages(self):
        """Get the conversation messages."""
        return self.agent.messages
    
    @property
    def session_id(self):
        """Get the session ID."""
        return self.agent.session_id 