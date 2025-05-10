import logging
from typing import Dict, Optional, Union, List

class LoggingManager:
    """
    A hook for TinyAgent that provides granular logging control for different modules.
    
    This allows setting different log levels for each module in the TinyAgent ecosystem
    without affecting external libraries like httpx.
    """
    
    def __init__(self, default_level: int = logging.INFO, silence_others: bool = True):
        """
        Initialize the LoggingManager.
        
        Args:
            default_level: Default logging level for all modules
            silence_others: If True, silence all non-tinyagent loggers by default
        """
        self.default_level = default_level
        self.module_loggers: Dict[str, logging.Logger] = {}
        self.module_levels: Dict[str, int] = {}
        
        # Grab the root logger
        self.root_logger = logging.getLogger()
        self.external_logger_levels: Dict[str, int] = {}
        
        if silence_others:
            # 1) store its original level
            self.root_logger_original_level = self.root_logger.level
            # 2) strip away _any_ existing handlers (e.g. from basicConfig in libs)
            for h in list(self.root_logger.handlers):
                self.root_logger.removeHandler(h)
            # 3) raise level so that only WARNING+ pass through by default
            self.root_logger.setLevel(logging.WARNING)
        
    def get_logger(self, module_name: str) -> logging.Logger:
        """
        Get or create a logger for a specific module.
        
        Args:
            module_name: Name of the module (e.g., 'tinyagent.tiny_agent')
            
        Returns:
            A configured logger for the module
        """
        if module_name in self.module_loggers:
            return self.module_loggers[module_name]
        
        # Create a new logger
        logger = logging.getLogger(module_name)
        
        # Set level from configured module levels or default
        level = self.module_levels.get(module_name, self.default_level)
        logger.setLevel(level)
        
        # Ensure propagation is enabled for tinyagent loggers
        if module_name.startswith('tinyagent'):
            logger.propagate = True
        
        # Store the logger
        self.module_loggers[module_name] = logger
        
        return logger
    
    def set_level(self, module_name: str, level: Union[int, str]) -> None:
        """
        Set the logging level for a specific module.
        
        Args:
            module_name: Name of the module (e.g., 'tinyagent.tiny_agent')
            level: Logging level (can be int or string like 'DEBUG')
        """
        # Convert string level to int if needed
        if isinstance(level, str):
            level = getattr(logging, level.upper())
        
        # Store the level setting
        self.module_levels[module_name] = level
        
        # Update existing logger if it exists
        if module_name in self.module_loggers:
            self.module_loggers[module_name].setLevel(level)
    
    def set_levels(self, config: Dict[str, Union[int, str]]) -> None:
        """
        Set multiple logging levels at once.
        
        Args:
            config: Dictionary mapping module names to levels
        """
        for module_name, level in config.items():
            self.set_level(module_name, level)
    
    def silence_external_loggers(self, logger_names: List[str], level: int = logging.WARNING) -> None:
        """
        Silence external loggers (like httpx) by setting them to a higher level.
        
        Args:
            logger_names: List of external logger names to silence
            level: Level to set for these loggers (default: WARNING)
        """
        for name in logger_names:
            logger = logging.getLogger(name)
            # Store original level
            self.external_logger_levels[name] = logger.level
            # Set new level
            logger.setLevel(level)
    
    def restore_external_loggers(self) -> None:
        """Restore external loggers to their original levels."""
        for name, level in self.external_logger_levels.items():
            logging.getLogger(name).setLevel(level)
        
        # Restore root logger level if we changed it
        if hasattr(self, 'root_logger_original_level'):
            self.root_logger.setLevel(self.root_logger_original_level)
    
    def configure_handler(self, handler: logging.Handler, 
                         format_string: Optional[str] = None,
                         level: Optional[int] = None) -> None:
        """
        Configure a logging handler with format and level.
        
        Args:
            handler: The handler to configure
            format_string: Optional format string for the handler
            level: Optional level for the handler
        """
        if format_string:
            formatter = logging.Formatter(format_string)
            handler.setFormatter(formatter)
        
        if level is not None:
            handler.setLevel(level)
        
        # Add to root logger if not already present
        if handler not in self.root_logger.handlers:
            self.root_logger.addHandler(handler)


async def run_example():
    """Example usage of LoggingManager with TinyAgent."""
    import os
    import sys
    from tinyagent import TinyAgent
    from tinyagent.hooks.rich_ui_callback import RichUICallback
    
    # Create the logging manager with silence_others=True
    log_manager = LoggingManager(default_level=logging.INFO, silence_others=True)
    
    # Configure different levels for different modules
    log_manager.set_levels({
        'tinyagent.tiny_agent': logging.INFO,
        'tinyagent.mcp_client': logging.INFO,
        'tinyagent.hooks.rich_ui_callback': logging.DEBUG,  # Debug for RichUICallback
        'tinyagent.hooks.logging_manager': logging.DEBUG,   # Debug for this module
    })
    
    # Explicitly silence specific external loggers if needed
    log_manager.silence_external_loggers(['httpx', 'asyncio', 'litellm', 'openai'], logging.WARNING)
    
    # Add a console handler with custom format
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG
    )
    
    # Get module-specific loggers
    agent_logger = log_manager.get_logger('tinyagent.tiny_agent')
    ui_logger = log_manager.get_logger('tinyagent.hooks.rich_ui_callback')
    mcp_logger = log_manager.get_logger('tinyagent.mcp_client')
    log_manager_logger = log_manager.get_logger('tinyagent.hooks.logging_manager')
    
    log_manager_logger.debug("Starting LoggingManager example")
    agent_logger.info("Initializing TinyAgent")
    
    # Get API key from environment
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        agent_logger.error("Please set the OPENAI_API_KEY environment variable")
        return
    
    # Initialize the agent with our logger
    agent = TinyAgent(model="gpt-4.1-mini", api_key=api_key, logger=agent_logger)
    
    # Add the Rich UI callback with our logger
    rich_ui = RichUICallback(
        markdown=True,
        show_message=True,
        show_thinking=True,
        show_tool_calls=True,
        logger=ui_logger  # Pass DEBUG level logger to RichUICallback
    )
    agent.add_callback(rich_ui)
    
    # Run the agent with a user query
    user_input = "What is the capital of France?"
    agent_logger.info(f"Running agent with input: {user_input}")
    result = await agent.run(user_input)
    
    agent_logger.info(f"Final result: {result}")
    
    # Clean up
    await agent.close()
    log_manager_logger.debug("Example completed")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_example()) 