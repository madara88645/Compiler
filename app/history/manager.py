import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from .models import HistoryEntry

DEFAULT_DB_PATH = os.path.expanduser("~/.promptc_history.db")
if os.name == "nt":
    DEFAULT_DB_PATH = r"C:\Users\User\.promptc_history.db"


class HistoryManager:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        # Ensure the parent directory exists before initializing the database
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    prompt_text TEXT,
                    source TEXT,
                    parent_id TEXT,
                    metadata TEXT,
                    score REAL
                )
            """
            )
            conn.commit()
        finally:
            conn.close()

    def save(self, entry: HistoryEntry):
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO history (id, timestamp, prompt_text, source, parent_id, metadata, score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.timestamp.isoformat(),
                    entry.prompt_text,
                    entry.source,
                    entry.parent_id,
                    json.dumps(entry.metadata),
                    entry.score,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_by_id(self, item_id: str) -> Optional[HistoryEntry]:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT * FROM history WHERE id = ?", (item_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_entry(row)
        finally:
            conn.close()

    def list_recent(self, limit: int = 20) -> List[HistoryEntry]:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT * FROM history ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            return [self._row_to_entry(row) for row in rows]
        finally:
            conn.close()

    def _row_to_entry(self, row) -> HistoryEntry:
        # id, timestamp, prompt_text, source, parent_id, metadata, score
        return HistoryEntry(
            id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            prompt_text=row[2],
            source=row[3],
            parent_id=row[4],
            metadata=json.loads(row[5]) if row[5] else {},
            score=row[6],
        )


_global_manager = None


def get_history_manager() -> HistoryManager:
    global _global_manager
    if _global_manager is None:
        _global_manager = HistoryManager()
    return _global_manager
