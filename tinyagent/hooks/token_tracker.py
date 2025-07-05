import logging
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from collections import defaultdict
import json

@dataclass
class UsageStats:
    """Represents usage statistics for LLM calls."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    call_count: int = 0
    # Additional fields that LiteLLM might provide
    thinking_tokens: int = 0
    reasoning_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    
    def __add__(self, other: 'UsageStats') -> 'UsageStats':
        """Add two UsageStats together."""
        return UsageStats(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cost=self.cost + other.cost,
            call_count=self.call_count + other.call_count,
            thinking_tokens=self.thinking_tokens + other.thinking_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "call_count": self.call_count,
            "thinking_tokens": self.thinking_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UsageStats':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

class TokenTracker:
    """
    A comprehensive token and cost tracker that integrates with TinyAgent's hook system.
    
    Features:
    - Accurate tracking using LiteLLM's usage data
    - Hierarchical tracking for agents with sub-agents
    - Per-model and per-provider breakdown
    - Real-time cost calculation
    - Hook-based integration with TinyAgent
    """
    
    def __init__(
        self,
        name: str = "default",
        parent_tracker: Optional['TokenTracker'] = None,
        logger: Optional[logging.Logger] = None,
        enable_detailed_logging: bool = True,
        track_per_model: bool = True,
        track_per_provider: bool = True
    ):
        """
        Initialize the TokenTracker.
        
        Args:
            name: Name identifier for this tracker
            parent_tracker: Parent tracker for hierarchical tracking
            logger: Optional logger instance
            enable_detailed_logging: Whether to log detailed usage information
            track_per_model: Whether to track usage per model
            track_per_provider: Whether to track usage per provider
        """
        self.name = name
        self.parent_tracker = parent_tracker
        self.logger = logger or logging.getLogger(__name__)
        self.enable_detailed_logging = enable_detailed_logging
        self.track_per_model = track_per_model
        self.track_per_provider = track_per_provider
        
        # Overall usage statistics
        self.total_usage = UsageStats()
        
        # Per-model tracking
        self.model_usage: Dict[str, UsageStats] = defaultdict(UsageStats)
        
        # Per-provider tracking (extracted from model names)
        self.provider_usage: Dict[str, UsageStats] = defaultdict(UsageStats)
        
        # Child trackers for hierarchical tracking
        self.child_trackers: List['TokenTracker'] = []
        
        # Session tracking
        self.session_start_time = time.time()
        self.last_call_time: Optional[float] = None
        
        # Register with parent if provided
        if self.parent_tracker:
            self.parent_tracker.add_child_tracker(self)
    
    def add_child_tracker(self, child_tracker: 'TokenTracker') -> None:
        """Add a child tracker for hierarchical tracking."""
        if child_tracker not in self.child_trackers:
            self.child_trackers.append(child_tracker)
            self.logger.debug(f"Added child tracker '{child_tracker.name}' to '{self.name}'")
    
    def remove_child_tracker(self, child_tracker: 'TokenTracker') -> None:
        """Remove a child tracker."""
        if child_tracker in self.child_trackers:
            self.child_trackers.remove(child_tracker)
            self.logger.debug(f"Removed child tracker '{child_tracker.name}' from '{self.name}'")
    
    def _extract_provider_from_model(self, model: str) -> str:
        """Extract provider name from model string."""
        # Handle common provider prefixes
        if "/" in model:
            return model.split("/")[0]
        elif model.startswith(("gpt-", "o1", "o3", "o4")):
            return "openai"
        elif model.startswith(("claude-", "anthropic/")):
            return "anthropic"
        elif model.startswith(("gemini-", "google/")):
            return "google"
        elif model.startswith("cohere/"):
            return "cohere"
        else:
            return "unknown"
    
    def _extract_usage_from_response(self, response: Any) -> Dict[str, Any]:
        """Extract usage data from LiteLLM response."""
        usage_data = {}
        
        if not response or not hasattr(response, 'usage'):
            return usage_data
        
        usage = response.usage
        
        # Handle both dict and object usage formats
        if isinstance(usage, dict):
            usage_data.update(usage)
        else:
            # Convert object to dict
            for attr in dir(usage):
                if not attr.startswith('_'):
                    value = getattr(usage, attr)
                    if isinstance(value, (int, float)):
                        usage_data[attr] = value
        
        # Extract cost from LiteLLM response (multiple methods)
        cost = 0.0
        
        # Method 1: Check response._hidden_params["response_cost"]
        try:
            if hasattr(response, '_hidden_params') and isinstance(response._hidden_params, dict):
                cost = response._hidden_params.get("response_cost", 0.0)
                if cost > 0:
                    self.logger.debug(f"Found cost in _hidden_params: ${cost:.6f}")
        except Exception as e:
            self.logger.debug(f"Could not extract cost from _hidden_params: {e}")
        
        # Method 2: Try litellm.completion_cost() as fallback
        if cost == 0.0:
            try:
                import litellm
                if hasattr(litellm, 'completion_cost'):
                    cost = litellm.completion_cost(completion_response=response)
                    if cost > 0:
                        self.logger.debug(f"Calculated cost using litellm.completion_cost: ${cost:.6f}")
            except Exception as e:
                self.logger.debug(f"Could not calculate cost using litellm.completion_cost: {e}")
        
        # Method 3: Check if cost is already in usage data
        if cost == 0.0 and 'cost' in usage_data:
            cost = usage_data.get('cost', 0.0)
            if cost > 0:
                self.logger.debug(f"Found cost in usage data: ${cost:.6f}")
        
        # Add the cost to usage_data
        usage_data['cost'] = cost
        
        return usage_data
    
    def track_llm_call(
        self,
        model: str,
        response: Any,
        **kwargs
    ) -> None:
        """
        Track a single LLM call using LiteLLM response data.
        
        Args:
            model: The model name used
            response: LiteLLM response object
            **kwargs: Additional context data
        """
        self.last_call_time = time.time()
        
        # Extract usage data from LiteLLM response
        usage_data = self._extract_usage_from_response(response)
        
        if not usage_data:
            self.logger.warning(f"No usage data found in response for model {model}")
            return
        
        # Create usage stats from response data
        call_usage = UsageStats(
            prompt_tokens=usage_data.get('prompt_tokens', 0),
            completion_tokens=usage_data.get('completion_tokens', 0),
            total_tokens=usage_data.get('total_tokens', 0),
            cost=usage_data.get('cost', 0.0),
            call_count=1,
            thinking_tokens=usage_data.get('thinking_tokens', 0),
            reasoning_tokens=usage_data.get('reasoning_tokens', 0),
            cache_creation_input_tokens=usage_data.get('cache_creation_input_tokens', 0),
            cache_read_input_tokens=usage_data.get('cache_read_input_tokens', 0),
        )
        
        # Update total usage
        self.total_usage += call_usage
        
        # Track per-model usage
        if self.track_per_model:
            self.model_usage[model] += call_usage
        
        # Track per-provider usage
        if self.track_per_provider:
            provider = self._extract_provider_from_model(model)
            self.provider_usage[provider] += call_usage
        
        # Log detailed information if enabled
        if self.enable_detailed_logging:
            self.logger.info(
                f"TokenTracker '{self.name}': {model} call - "
                f"Tokens: {call_usage.prompt_tokens}+{call_usage.completion_tokens}={call_usage.total_tokens}, "
                f"Cost: ${call_usage.cost:.6f}"
            )
            
            # Log additional token types if present
            if call_usage.thinking_tokens > 0:
                self.logger.info(f"  Thinking tokens: {call_usage.thinking_tokens}")
            if call_usage.reasoning_tokens > 0:
                self.logger.info(f"  Reasoning tokens: {call_usage.reasoning_tokens}")
            if call_usage.cache_creation_input_tokens > 0:
                self.logger.info(f"  Cache creation tokens: {call_usage.cache_creation_input_tokens}")
            if call_usage.cache_read_input_tokens > 0:
                self.logger.info(f"  Cache read tokens: {call_usage.cache_read_input_tokens}")
    
    def get_total_usage(self, include_children: bool = False) -> UsageStats:
        """
        Get total usage statistics.
        
        Args:
            include_children: Whether to include usage from child trackers
            
        Returns:
            UsageStats object with total usage
        """
        total = UsageStats(
            prompt_tokens=self.total_usage.prompt_tokens,
            completion_tokens=self.total_usage.completion_tokens,
            total_tokens=self.total_usage.total_tokens,
            cost=self.total_usage.cost,
            call_count=self.total_usage.call_count,
            thinking_tokens=self.total_usage.thinking_tokens,
            reasoning_tokens=self.total_usage.reasoning_tokens,
            cache_creation_input_tokens=self.total_usage.cache_creation_input_tokens,
            cache_read_input_tokens=self.total_usage.cache_read_input_tokens,
        )
        
        if include_children:
            for child in self.child_trackers:
                child_usage = child.get_total_usage(include_children=True)
                total += child_usage
        
        return total
    
    def get_model_breakdown(self, include_children: bool = False) -> Dict[str, UsageStats]:
        """Get usage breakdown by model."""
        breakdown = {model: UsageStats(
            prompt_tokens=stats.prompt_tokens,
            completion_tokens=stats.completion_tokens,
            total_tokens=stats.total_tokens,
            cost=stats.cost,
            call_count=stats.call_count,
            thinking_tokens=stats.thinking_tokens,
            reasoning_tokens=stats.reasoning_tokens,
            cache_creation_input_tokens=stats.cache_creation_input_tokens,
            cache_read_input_tokens=stats.cache_read_input_tokens,
        ) for model, stats in self.model_usage.items()}
        
        if include_children:
            for child in self.child_trackers:
                child_breakdown = child.get_model_breakdown(include_children=True)
                for model, stats in child_breakdown.items():
                    if model in breakdown:
                        breakdown[model] += stats
                    else:
                        breakdown[model] = stats
        
        return breakdown
    
    def get_provider_breakdown(self, include_children: bool = False) -> Dict[str, UsageStats]:
        """Get usage breakdown by provider."""
        breakdown = {provider: UsageStats(
            prompt_tokens=stats.prompt_tokens,
            completion_tokens=stats.completion_tokens,
            total_tokens=stats.total_tokens,
            cost=stats.cost,
            call_count=stats.call_count,
            thinking_tokens=stats.thinking_tokens,
            reasoning_tokens=stats.reasoning_tokens,
            cache_creation_input_tokens=stats.cache_creation_input_tokens,
            cache_read_input_tokens=stats.cache_read_input_tokens,
        ) for provider, stats in self.provider_usage.items()}
        
        if include_children:
            for child in self.child_trackers:
                child_breakdown = child.get_provider_breakdown(include_children=True)
                for provider, stats in child_breakdown.items():
                    if provider in breakdown:
                        breakdown[provider] += stats
                    else:
                        breakdown[provider] = stats
        
        return breakdown
    
    def get_session_duration(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.session_start_time
    
    def get_detailed_report(self, include_children: bool = True) -> Dict[str, Any]:
        """
        Generate a detailed usage report.
        
        Args:
            include_children: Whether to include child tracker data
            
        Returns:
            Dictionary containing comprehensive usage information
        """
        total_usage = self.get_total_usage(include_children=include_children)
        model_breakdown = self.get_model_breakdown(include_children=include_children)
        provider_breakdown = self.get_provider_breakdown(include_children=include_children)
        
        report = {
            "tracker_name": self.name,
            "session_duration_seconds": self.get_session_duration(),
            "total_usage": total_usage.to_dict(),
            "model_breakdown": {model: stats.to_dict() for model, stats in model_breakdown.items()},
            "provider_breakdown": {provider: stats.to_dict() for provider, stats in provider_breakdown.items()},
            "child_trackers": []
        }
        
        if include_children:
            for child in self.child_trackers:
                child_report = child.get_detailed_report(include_children=True)
                report["child_trackers"].append(child_report)
        
        return report
    
    def print_summary(self, include_children: bool = True, detailed: bool = False) -> None:
        """Print a summary of usage statistics."""
        total_usage = self.get_total_usage(include_children=include_children)
        
        print(f"\n📊 Token Tracker Summary: '{self.name}'")
        print("=" * 50)
        print(f"Total Tokens: {total_usage.total_tokens:,}")
        print(f"  • Prompt: {total_usage.prompt_tokens:,}")
        print(f"  • Completion: {total_usage.completion_tokens:,}")
        if total_usage.thinking_tokens > 0:
            print(f"  • Thinking: {total_usage.thinking_tokens:,}")
        if total_usage.reasoning_tokens > 0:
            print(f"  • Reasoning: {total_usage.reasoning_tokens:,}")
        if total_usage.cache_creation_input_tokens > 0:
            print(f"  • Cache Creation: {total_usage.cache_creation_input_tokens:,}")
        if total_usage.cache_read_input_tokens > 0:
            print(f"  • Cache Read: {total_usage.cache_read_input_tokens:,}")
        
        print(f"Total Cost: ${total_usage.cost:.6f}")
        print(f"API Calls: {total_usage.call_count}")
        print(f"Session Duration: {self.get_session_duration():.1f}s")
        
        if detailed:
            model_breakdown = self.get_model_breakdown(include_children=include_children)
            if model_breakdown:
                print(f"\n📈 Model Breakdown:")
                for model, stats in sorted(model_breakdown.items(), key=lambda x: x[1].cost, reverse=True):
                    print(f"  {model}: {stats.total_tokens:,} tokens, ${stats.cost:.6f}, {stats.call_count} calls")
            
            provider_breakdown = self.get_provider_breakdown(include_children=include_children)
            if provider_breakdown:
                print(f"\n🏢 Provider Breakdown:")
                for provider, stats in sorted(provider_breakdown.items(), key=lambda x: x[1].cost, reverse=True):
                    print(f"  {provider}: {stats.total_tokens:,} tokens, ${stats.cost:.6f}, {stats.call_count} calls")
        
        if include_children and self.child_trackers:
            print(f"\n👥 Child Trackers: {len(self.child_trackers)}")
            for child in self.child_trackers:
                child_usage = child.get_total_usage(include_children=True)
                print(f"  • {child.name}: {child_usage.total_tokens:,} tokens, ${child_usage.cost:.6f}")
    
    def reset_stats(self, reset_children: bool = False) -> None:
        """Reset all statistics."""
        self.total_usage = UsageStats()
        self.model_usage.clear()
        self.provider_usage.clear()
        self.session_start_time = time.time()
        self.last_call_time = None
        
        if reset_children:
            for child in self.child_trackers:
                child.reset_stats(reset_children=True)
        
        self.logger.info(f"Reset statistics for tracker '{self.name}'")
    
    def export_to_json(self, include_children: bool = True) -> str:
        """Export tracker data to JSON string."""
        report = self.get_detailed_report(include_children=include_children)
        return json.dumps(report, indent=2)
    
    def save_to_file(self, filepath: str, include_children: bool = True) -> None:
        """Save tracker data to a JSON file."""
        report = self.get_detailed_report(include_children=include_children)
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        self.logger.info(f"Saved tracker report to {filepath}")
    
    # Hook methods for TinyAgent integration
    async def __call__(self, event_name: str, agent: Any, **kwargs) -> None:
        """
        Main hook method that integrates with TinyAgent's callback system.
        
        Args:
            event_name: The event name from TinyAgent
            agent: The TinyAgent instance
            **kwargs: Event-specific data
        """
        if event_name == "llm_end":
            response = kwargs.get("response")
            if response:
                # Extract model from agent or response
                model = getattr(agent, 'model', 'unknown')
                
                # Remove 'response' from kwargs to avoid duplicate argument error
                filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'response'}
                self.track_llm_call(model, response, **filtered_kwargs)
        
        elif event_name == "agent_start":
            self.logger.debug(f"Agent '{self.name}' started new conversation")
        
        elif event_name == "agent_end":
            if self.enable_detailed_logging:
                total_usage = self.get_total_usage()
                self.logger.info(
                    f"Agent '{self.name}' completed - "
                    f"Total: {total_usage.total_tokens} tokens, ${total_usage.cost:.6f}"
                )

def create_token_tracker(
    name: str = "main",
    parent_tracker: Optional[TokenTracker] = None,
    logger: Optional[logging.Logger] = None,
    **kwargs
) -> TokenTracker:
    """
    Convenience function to create a TokenTracker instance.
    
    Args:
        name: Name for the tracker
        parent_tracker: Parent tracker for hierarchical tracking
        logger: Logger instance
        **kwargs: Additional arguments for TokenTracker
        
    Returns:
        TokenTracker instance
    """
    return TokenTracker(
        name=name,
        parent_tracker=parent_tracker,
        logger=logger,
        **kwargs
    )

# Example usage
async def run_example():
    """Example usage of TokenTracker with TinyAgent."""
    import sys
    from tinyagent import TinyAgent
    from tinyagent.hooks.logging_manager import LoggingManager
    import os
    
    # Set up logging
    log_manager = LoggingManager(default_level=logging.INFO)
    console_handler = logging.StreamHandler(sys.stdout)
    log_manager.configure_handler(
        console_handler,
        format_string='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Create main token tracker
    main_tracker = create_token_tracker(
        name="main_agent",
        logger=log_manager.get_logger('token_tracker.main'),
        enable_detailed_logging=True
    )
    
    # Create child tracker for sub-agent
    sub_tracker = create_token_tracker(
        name="sub_agent",
        parent_tracker=main_tracker,
        logger=log_manager.get_logger('token_tracker.sub'),
        enable_detailed_logging=True
    )
    
    # Create main agent with token tracking
    main_agent = TinyAgent(
        model="gpt-4o-mini",
        api_key=os.environ.get("OPENAI_API_KEY"),
        logger=log_manager.get_logger('main_agent')
    )
    main_agent.add_callback(main_tracker)
    
    # Create sub-agent with different model
    sub_agent = TinyAgent(
        model="claude-3-haiku-20240307",
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        logger=log_manager.get_logger('sub_agent')
    )
    sub_agent.add_callback(sub_tracker)
    
    # Run some tasks
    await main_agent.run("What is the capital of France?")
    await sub_agent.run("Explain quantum computing in simple terms.")
    await main_agent.run("Now tell me about the history of Paris.")
    
    # Print comprehensive summary
    main_tracker.print_summary(include_children=True, detailed=True)
    
    # Export report
    report_json = main_tracker.export_to_json(include_children=True)
    print(f"\n📄 JSON Report:\n{report_json}")
    
    # Clean up
    await main_agent.close()
    await sub_agent.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_example()) 