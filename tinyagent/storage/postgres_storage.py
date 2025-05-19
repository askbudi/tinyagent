import asyncpg
import json
import logging
from typing import Optional, Dict, Any
from tinyagent.storage import Storage

class PostgresStorage(Storage):
    """
    Persist TinyAgent sessions in a Postgres table with JSONB state.
    """

    def __init__(self, db_url: str, table_name: str = "tny_agent_sessions"):
        self._dsn = db_url
        self._table = table_name
        self._pool: Optional[asyncpg.pool.Pool] = None
        self.logger = logging.getLogger(__name__)

    async def _ensure_table(self):
        """Create the sessions table if it doesn't exist."""
        self.logger.debug(f"Ensuring table {self._table} exists")
        try:
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
                self.logger.info(f"Table {self._table} and indexes created/verified")
        except Exception as e:
            self.logger.error(f"Error creating table {self._table}: {str(e)}")
            raise

    async def _connect(self):
        if not self._pool:
            self.logger.debug(f"Connecting to PostgreSQL with DSN: {self._dsn[:10]}...")
            try:
                # Ensure statement_cache_size=0 to disable prepared statements for pgbouncer compatibility
                self._pool = await asyncpg.create_pool(
                    dsn=self._dsn, 
                    statement_cache_size=0,
                    min_size=1,
                    max_size=10
                )
                self.logger.info("PostgreSQL connection pool created")
                await self._ensure_table()
            except Exception as e:
                self.logger.error(f"Failed to connect to PostgreSQL: {str(e)}")
                raise

    async def save_session(self, session_id: str, data: Dict[str, Any], user_id: Optional[str] = None):
        self.logger.info(f"Saving session {session_id} for user {user_id}")
        self.logger.debug(f"Save data: {json.dumps(data)[:200]}...")
        
        try:
            await self._connect()
            
            # Extract data following the TinyAgent schema
            metadata = data.get("metadata", {}) or {}
            session_state = data.get("session_state", {}) or {}
            
            # Use session_id as agent_id if not provided
            agent_id = metadata.get("agent_id", session_id)
            self.logger.debug(f"Using agent_id: {agent_id}")
            
            # Extract specific components
            memories = session_state.get("memory", {})
            session_data = {"messages": session_state.get("messages", [])}
            model_meta = metadata.get("model_meta", {})
            
            # Convert Python dictionaries to JSON strings for PostgreSQL
            self.logger.debug("Converting Python dictionaries to JSON")
            try:
                memories_json = json.dumps(memories)
                metadata_json = json.dumps(metadata)
                session_data_json = json.dumps(session_data)
                model_meta_json = json.dumps(model_meta)
            except Exception as e:
                self.logger.error(f"JSON serialization error: {str(e)}")
                raise
            
            self.logger.debug("Executing PostgreSQL INSERT/UPDATE")
            async with self._pool.acquire() as conn:
                try:
                    await conn.execute(f"""
                        INSERT INTO {self._table} 
                        (agent_id, session_id, user_id, memories, metadata, session_data, model_meta, updated_at)
                        VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6::jsonb, $7::jsonb, NOW())
                        ON CONFLICT (agent_id) DO UPDATE
                          SET session_id = EXCLUDED.session_id,
                              user_id = EXCLUDED.user_id,
                              memories = EXCLUDED.memories,
                              metadata = EXCLUDED.metadata,
                              session_data = EXCLUDED.session_data,
                              model_meta = EXCLUDED.model_meta,
                              updated_at = NOW();
                    """, agent_id, session_id, user_id, memories_json, metadata_json, session_data_json, model_meta_json)
                    self.logger.info(f"Session {session_id} saved successfully")
                except Exception as e:
                    self.logger.error(f"Database error during save: {str(e)}")
                    raise
        except Exception as e:
            self.logger.error(f"Failed to save session {session_id}: {str(e)}")
            raise

    async def load_session(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        self.logger.info(f"Loading session {session_id} for user {user_id}")
        
        try:
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
                
                self.logger.debug(f"Executing query: {query} with params: {params}")
                row = await conn.fetchrow(query, *params)
                
                if not row:
                    self.logger.warning(f"No session found for session_id={session_id}, user_id={user_id}")
                    return {}
                
                self.logger.debug(f"Session found: {dict(row)}")
                
                # Parse JSON from PostgreSQL
                try:
                    # Check if values are already dictionaries or need parsing
                    memories = row["memories"]
                    if isinstance(memories, str):
                        memories = json.loads(memories)
                    
                    metadata = row["metadata"]
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    
                    session_data = row["session_data"]
                    if isinstance(session_data, str):
                        session_data = json.loads(session_data)
                    
                    model_meta = row["model_meta"]
                    if isinstance(model_meta, str):
                        model_meta = json.loads(model_meta)
                except Exception as e:
                    self.logger.error(f"Error parsing JSON from database: {str(e)}")
                    raise
                
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
                
                result = {
                    "session_id": row["session_id"],
                    "metadata": metadata,
                    "session_state": session_state
                }
                
                self.logger.info(f"Session {session_id} loaded successfully")
                self.logger.debug(f"Loaded data: {json.dumps(result)[:200]}...")
                return result
        except Exception as e:
            self.logger.error(f"Failed to load session {session_id}: {str(e)}")
            raise

    async def close(self):
        if self._pool:
            self.logger.info("Closing PostgreSQL connection pool")
            try:
                await self._pool.close()
                self._pool = None
                self.logger.debug("PostgreSQL connection pool closed")
            except Exception as e:
                self.logger.error(f"Error closing PostgreSQL connection: {str(e)}") 

