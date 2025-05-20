import json
from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from tinyagent.storage import Storage

class RedisStorage(Storage):
    """
    Persist TinyAgent sessions in Redis.  Optionally expire them after `ttl` seconds.
    """

    def __init__(self, url: str = "redis://localhost", ttl: Optional[int] = None):
        """
        :param url: Redis connection URL, e.g. "redis://localhost:6379/0"
        :param ttl: time‐to‐live in seconds (None ⇒ no expiry)
        """
        self.url = url
        self.ttl = ttl
        self._client: Optional[aioredis.Redis] = None

    async def _connect(self):
        if not self._client:
            # from_url returns an asyncio‐enabled Redis client
            self._client = aioredis.from_url(self.url)

    async def save_session(self, session_id: str, data: Dict[str, Any], user_id: Optional[str] = None) -> None:
        await self._connect()
        payload = json.dumps(data)
        if self.ttl is not None:
            # set with expiration
            await self._client.set(f"{session_id}_{user_id}", payload, ex=self.ttl)
        else:
            # set without expiration
            await self._client.set(f"{session_id}_{user_id}", payload)

    async def load_session(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        await self._connect()
        raw = await self._client.get(f"{session_id}_{user_id}")
        if not raw:
            return {}
        # raw may be bytes or str
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None