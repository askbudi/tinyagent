import asyncpg
from typing import Optional, Dict, Any
from tinyagent.storage import Storage

class PostgresStorage(Storage):
    """
    Persist TinyAgent sessions in a Postgres table with JSONB state.
    """

    def __init__(self, dsn: str, table_name: str = "tny_agent_sessions"):
        self._dsn = dsn
        self._table = table_name
        self._pool: Optional[asyncpg.pool.Pool] = None

    async def _ensure_table(self):
        """Create the sessions table if it doesn't exist."""
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._table} (
                    agent_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    memories JSONB,
                    metadata JSONB,
                    session_data JSONB,
                    model_meta JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_{self._table}_session_id ON {self._table} (session_id);
                CREATE INDEX IF NOT EXISTS idx_{self._table}_user_id ON {self._table} (user_id);
            """)

    async def _connect(self):
        if not self._pool:
            self._pool = await asyncpg.create_pool(dsn=self._dsn)
            await self._ensure_table()

    async def save_session(self, session_id: str, data: Dict[str, Any], user_id: Optional[str] = None):
        await self._connect()
        
        # Extract data following the TinyAgent schema
        metadata = data.get("metadata", {}) or {}
        session_state = data.get("session_state", {}) or {}
        
        # Use session_id as agent_id if not provided
        agent_id = metadata.get("agent_id", session_id)
        
        # Extract specific components
        memories = session_state.get("memory", {})
        session_data = {"messages": session_state.get("messages", [])}
        model_meta = metadata.get("model_meta", {})
        
        async with self._pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {self._table} 
                (agent_id, session_id, user_id, memories, metadata, session_data, model_meta, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                ON CONFLICT (agent_id) DO UPDATE
                  SET session_id = EXCLUDED.session_id,
                      user_id = EXCLUDED.user_id,
                      memories = EXCLUDED.memories,
                      metadata = EXCLUDED.metadata,
                      session_data = EXCLUDED.session_data,
                      model_meta = EXCLUDED.model_meta,
                      updated_at = NOW();
            """, agent_id, session_id, user_id, memories, metadata, session_data, model_meta)

    async def load_session(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        await self._connect()
        async with self._pool.acquire() as conn:
            # First try to find by session_id
            query = f"""
                SELECT agent_id, session_id, user_id, memories, metadata, session_data, model_meta
                  FROM {self._table}
                 WHERE session_id = $1
            """
            params = [session_id]
            
            # Add user_id filter if provided
            if user_id:
                query += " AND user_id = $2"
                params.append(user_id)
                
            row = await conn.fetchrow(query, *params)
            
            if not row:
                return {}
                
            # Reconstruct the TinyAgent format
            metadata = row["metadata"] or {}
            memories = row["memories"] or {}
            session_data = row["session_data"] or {}
            
            # Update metadata with additional fields
            metadata.update({
                "agent_id": row["agent_id"],
                "user_id": row["user_id"],
                "model_meta": row["model_meta"] or {}
            })
            
            # Construct session state
            session_state = {
                "messages": session_data.get("messages", []),
                "memory": memories,
            }
            
            return {
                "session_id": row["session_id"],
                "metadata": metadata,
                "session_state": session_state
            }

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None 

