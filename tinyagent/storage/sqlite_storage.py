import aiosqlite
import json
import os
import logging
from typing import Optional, Dict, Any
from tinyagent.storage import Storage

class SqliteStorage(Storage):
    """
    Persist TinyAgent sessions in a SQLite database with JSON state.
    """

    def __init__(self, db_path: str, table_name: str = "tny_agent_sessions"):
        self._db_path = db_path
        self._table = table_name
        self._conn: Optional[aiosqlite.Connection] = None
        self.logger = logging.getLogger(__name__)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    async def _ensure_table(self):
        """Create the sessions table if it doesn't exist."""
        await self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                agent_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT,
                memories TEXT,
                metadata TEXT,
                session_data TEXT,
                model_meta TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Create indexes
        await self._conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self._table}_session_id ON {self._table} (session_id);")
        await self._conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{self._table}_user_id ON {self._table} (user_id);")
        await self._conn.commit()

    async def _connect(self):
        if not self._conn:
            self._conn = await aiosqlite.connect(self._db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._ensure_table()

    async def save_session(self, session_id: str, data: Dict[str, Any], user_id: Optional[str] = None):
        await self._connect()
        self.logger.info(f"[sqlite] Saving session {session_id} for user {user_id}")
        self.logger.debug(f"[sqlite] Save data: {json.dumps(data)[:200]}...")
        # Extract data following the TinyAgent schema
        metadata = data.get("metadata", {}) or {}
        session_state = data.get("session_state", {}) or {}
        
        # Use session_id as agent_id if not provided
        agent_id = metadata.get("agent_id", session_id)
        
        # Extract specific components
        memories = session_state.get("memory", {})
        session_data = {"messages": session_state.get("messages", [])}
        model_meta = metadata.get("model_meta", {})
        
        # Convert dictionaries to JSON strings
        memories_json = json.dumps(memories)
        metadata_json = json.dumps(metadata)
        session_data_json = json.dumps(session_data)
        model_meta_json = json.dumps(model_meta)
        
        # Check if record exists
        cursor = await self._conn.execute(
            f"SELECT 1 FROM {self._table} WHERE agent_id = ?", 
            (agent_id,)
        )
        exists = await cursor.fetchone() is not None
        
        if exists:
            # Update existing record
            await self._conn.execute(f"""
                UPDATE {self._table} SET
                    session_id = ?,
                    user_id = ?,
                    memories = ?,
                    metadata = ?,
                    session_data = ?,
                    model_meta = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE agent_id = ?
            """, (session_id, user_id, memories_json, metadata_json, session_data_json, model_meta_json, agent_id))
        else:
            # Insert new record
            await self._conn.execute(f"""
                INSERT INTO {self._table} 
                (agent_id, session_id, user_id, memories, metadata, session_data, model_meta)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (agent_id, session_id, user_id, memories_json, metadata_json, session_data_json, model_meta_json))
        
        await self._conn.commit()

    async def load_session(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        await self._connect()
        
        # Build query
        query = f"""
            SELECT agent_id, session_id, user_id, memories, metadata, session_data, model_meta
            FROM {self._table}
            WHERE session_id = ?
        """
        params = [session_id]
        
        # Add user_id filter if provided
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        # Execute query
        cursor = await self._conn.execute(query, params)
        row = await cursor.fetchone()
        
        if not row:
            return {}
        
        # Parse JSON strings
        memories = json.loads(row["memories"]) if row["memories"] else {}
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        session_data = json.loads(row["session_data"]) if row["session_data"] else {}
        model_meta = json.loads(row["model_meta"]) if row["model_meta"] else {}
        
        # Update metadata with additional fields
        metadata.update({
            "agent_id": row["agent_id"],
            "user_id": row["user_id"],
            "model_meta": model_meta
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
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def __aenter__(self):
        await self._connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close() 