import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Union
from tinyagent.storage import Storage

class JSONFileStorage(Storage):
    """
    Persist TinyAgent sessions as individual JSON files.
    """

    def __init__(self, folder: Union[str, Path]):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    async def save_session(self, session_id: str, data: Dict[str, Any]) -> None:
        path = self.folder / f"{session_id}.json"
        # Write in a thread pool to avoid blocking the event loop
        await asyncio.to_thread(path.write_text, json.dumps(data, indent=2), "utf-8")

    async def load_session(self, session_id: str) -> Dict[str, Any]:
        path = self.folder / f"{session_id}.json"
        if not path.exists():
            return {}
        text = await asyncio.to_thread(path.read_text, "utf-8")
        return json.loads(text)

    async def close(self) -> None:
        # Nothing to clean up for file storage
        return