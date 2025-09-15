import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# Minimal SQLite FTS5-based retriever. No external deps.
# Schema:
#   docs(id INTEGER PRIMARY KEY, path TEXT UNIQUE, mtime REAL, size INTEGER)
#   chunks(id INTEGER PRIMARY KEY, doc_id INTEGER, chunk_index INTEGER, content TEXT)
#   fts(content) USING fts5(content, content="", tokenize="porter")
#   Triggers keep fts in sync with chunks.

DEFAULT_DB_PATH = os.path.expanduser("~/.promptc_index.db")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS docs (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            mtime REAL,
            size INTEGER
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            doc_id INTEGER,
            chunk_index INTEGER,
            content TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(content, tokenize='porter');

        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO fts(rowid, content) VALUES (new.id, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO fts(fts, rowid, content) VALUES('delete', old.id, old.content);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO fts(fts, rowid, content) VALUES('delete', old.id, old.content);
            INSERT INTO fts(rowid, content) VALUES (new.id, new.content);
        END;
        """
    )
    conn.commit()


def _needs_ingest(conn: sqlite3.Connection, path: Path) -> bool:
    stat = path.stat()
    cur = conn.execute("SELECT mtime, size FROM docs WHERE path=?", (str(path),))
    row = cur.fetchone()
    return not row or row[0] != stat.st_mtime or row[1] != stat.st_size


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if len(text) <= chunk_size:
        return [text]
    chunks: List[str] = []
    i = 0
    while i < len(text):
        chunk = text[i : i + chunk_size]
        chunks.append(chunk)
        if i + chunk_size >= len(text):
            break
        i += chunk_size - overlap
        if i < 0:
            i = 0
    return chunks


def _insert_document(conn: sqlite3.Connection, path: Path, content: str) -> None:
    stat = path.stat()
    cur = conn.execute(
        "INSERT INTO docs(path, mtime, size) VALUES(?, ?, ?)\n            ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, size=excluded.size\n            RETURNING id",
        (str(path), stat.st_mtime, stat.st_size),
    )
    doc_id = cur.fetchone()[0]
    conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
    for idx, chunk in enumerate(_chunk_text(content)):
        conn.execute(
            "INSERT INTO chunks(doc_id, chunk_index, content) VALUES(?, ?, ?)",
            (doc_id, idx, chunk),
        )


def ingest_paths(paths: Iterable[str], db_path: Optional[str] = None, exts: Optional[Iterable[str]] = None) -> Tuple[int, int, float]:
    start = time.time()
    conn = _connect(db_path)
    try:
        _init_schema(conn)
        n_docs = 0
        n_chunks = 0
        allowed_exts = set(e.lower() for e in (exts or [".txt", ".md", ".py"]))
        for p in paths:
            pth = Path(p)
            if not pth.exists():
                continue
            if pth.is_dir():
                for root, _, files in os.walk(pth):
                    for f in files:
                        fp = Path(root) / f
                        if fp.suffix.lower() not in allowed_exts:
                            continue
                        if _needs_ingest(conn, fp):
                            try:
                                content = fp.read_text(encoding="utf-8", errors="ignore")
                            except Exception:
                                continue
                            _insert_document(conn, fp, content)
                            n_docs += 1
            else:
                if pth.suffix.lower() not in allowed_exts:
                    continue
                if _needs_ingest(conn, pth):
                    try:
                        content = pth.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    _insert_document(conn, pth, content)
                    n_docs += 1
        # count chunks
        cur = conn.execute("SELECT COUNT(*) FROM chunks")
        n_chunks = int(cur.fetchone()[0])
        conn.commit()
        return n_docs, n_chunks, time.time() - start
    finally:
        conn.close()


def search(query: str, k: int = 5, db_path: Optional[str] = None) -> List[dict]:
    conn = _connect(db_path)
    try:
        _init_schema(conn)
        cur = conn.execute(
            """
            SELECT c.id, c.doc_id, d.path, c.chunk_index,
                   snippet(fts, 0, '[', ']', '…', 10) as snippet,
                   bm25(fts) as score
            FROM fts JOIN chunks c ON fts.rowid = c.id
            JOIN docs d ON d.id = c.doc_id
            WHERE fts MATCH ?
            ORDER BY score LIMIT ?
            """,
            (query, k),
        )
        results = []
        for row in cur.fetchall():
            results.append(
                {
                    "chunk_id": row[0],
                    "doc_id": row[1],
                    "path": row[2],
                    "chunk_index": row[3],
                    "snippet": row[4],
                    "score": row[5],
                }
            )
        return results
    finally:
        conn.close()
