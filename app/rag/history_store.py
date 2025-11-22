from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


@dataclass
class QueryEntry:
    query: str
    method: str
    k: int
    timestamp: str


@dataclass
class PinEntry:
    label: str
    snippet: str
    source: str
    created_at: str


@dataclass
class RAGHistoryStore:
    path: Optional[Path] = None
    max_queries: int = 25
    max_pins: int = 20
    queries: List[QueryEntry] = field(default_factory=list)
    pins: List[PinEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.path is None:
            self.path = Path.home() / ".promptc_rag_history.json"
        self.path = Path(self.path)
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                data = {}
        except Exception:
            data = {}
        self.queries = [
            QueryEntry(
                query=str(item.get("query", "")),
                method=str(item.get("method", "fts")),
                k=int(item.get("k", 10)),
                timestamp=str(item.get("timestamp", self._now())),
            )
            for item in data.get("queries", [])
            if isinstance(item, dict)
        ]
        self.pins = [
            PinEntry(
                label=str(item.get("label", "Unnamed")),
                snippet=str(item.get("snippet", "")),
                source=str(item.get("source", "")),
                created_at=str(item.get("created_at", self._now())),
            )
            for item in data.get("pins", [])
            if isinstance(item, dict)
        ]

    def save(self) -> None:
        payload = {
            "queries": [entry.__dict__ for entry in self.queries[-self.max_queries :]],
            "pins": [entry.__dict__ for entry in self.pins[-self.max_pins :]],
        }
        try:
            self.path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def add_query(self, query: str, method: str, k: int) -> None:
        if not query:
            return
        entry = QueryEntry(query=query, method=method or "fts", k=max(1, k), timestamp=self._now())
        # dedupe consecutive duplicates
        if (
            self.queries
            and self.queries[-1].query == entry.query
            and self.queries[-1].method == entry.method
        ):
            self.queries[-1] = entry
        else:
            self.queries.append(entry)
        if len(self.queries) > self.max_queries:
            self.queries = self.queries[-self.max_queries :]
        self.save()

    def add_pin(self, label: str, snippet: str, source: str = "") -> None:
        if not snippet.strip():
            return
        label = label.strip() or snippet.strip()[:40]
        entry = PinEntry(label=label, snippet=snippet, source=source, created_at=self._now())
        self.pins.append(entry)
        if len(self.pins) > self.max_pins:
            self.pins = self.pins[-self.max_pins :]
        self.save()

    def delete_query(self, index: int) -> None:
        if 0 <= index < len(self.queries):
            del self.queries[index]
            self.save()

    def clear_queries(self) -> None:
        self.queries.clear()
        self.save()

    def delete_pin(self, index: int) -> None:
        if 0 <= index < len(self.pins):
            del self.pins[index]
            self.save()

    def clear_pins(self) -> None:
        self.pins.clear()
        self.save()

    def iter_queries(self):
        for idx in range(len(self.queries) - 1, -1, -1):
            entry = self.queries[idx]
            yield idx, entry

    def iter_pins(self):
        for idx in range(len(self.pins) - 1, -1, -1):
            entry = self.pins[idx]
            yield idx, entry

    def format_timestamp(self, ts: str) -> str:
        try:
            dt = datetime.fromisoformat(ts)
            return dt.strftime("%b %d %H:%M")
        except Exception:
            return ts

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
