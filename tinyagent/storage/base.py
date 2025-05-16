from abc import ABC, abstractmethod
from typing import Dict, Any, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tinyagent.tiny_agent import TinyAgent

class Storage(ABC):
    """
    Abstract base class for TinyAgent session storage.
    """

    @abstractmethod
    async def save_session(self, session_id: str, data: Dict[str, Any], user_id: Optional[str] = None) -> None:
        """
        Persist the given agent state under `session_id`.
        """
        ...

    @abstractmethod
    async def load_session(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve the agent state for `session_id`, or return {} if not found.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """
        Clean up any resources (DB connections, file handles, etc.).
        """
        ...

    def attach(self, agent: "TinyAgent") -> None:
        """
        Hook this storage to a TinyAgent so that on every `llm_end`
        it will auto‐persist the agent's state.

        Usage:
            storage.attach(agent)
        or in TinyAgent.__init__:
            if storage: storage.attach(self)
        """
        async def _auto_save(event_name: str, agent: "TinyAgent", **kwargs):
            if event_name != "llm_end":
                return
            state = agent.to_dict()
            await self.save_session(agent.session_id, state)

        agent.callbacks.append(_auto_save) 