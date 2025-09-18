import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Dict
import math
import json
from collections import OrderedDict

# Minimal SQLite FTS5-based retriever. No external deps.
# Schema:
#   docs(id INTEGER PRIMARY KEY, path TEXT UNIQUE, mtime REAL, size INTEGER)
#   chunks(id INTEGER PRIMARY KEY, doc_id INTEGER, chunk_index INTEGER, content TEXT)
#   fts(content) USING fts5(content, content="", tokenize="porter")
#   embeddings(chunk_id INTEGER PRIMARY KEY, dim INTEGER, vec TEXT)  -- vec is JSON list of floats (L2 normalized)
#   Triggers keep fts in sync with chunks.

DEFAULT_DB_PATH = os.path.expanduser("~/.promptc_index.db")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Simple in-process LRU cache for query results (per run)
_CACHE_CAP = 64
_query_cache: "OrderedDict[str, list]" = OrderedDict()


def _cache_get(key: str):
    if key in _query_cache:
        _query_cache.move_to_end(key)
        return _query_cache[key]
    return None


def _cache_put(key: str, value):
    _query_cache[key] = value
    _query_cache.move_to_end(key)
    if len(_query_cache) > _CACHE_CAP:
        _query_cache.popitem(last=False)


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
        CREATE TABLE IF NOT EXISTS embeddings (
            chunk_id INTEGER PRIMARY KEY,
            dim INTEGER NOT NULL,
            vec TEXT NOT NULL
        );

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


def _simple_embed(text: str, dim: int = 64) -> List[float]:
    """Deterministic tiny embedding: hash tokens into fixed-size bag, L2 normalize.

    This avoids external dependencies while enabling relative similarity ranking.
    """
    vec = [0.0] * dim
    # very small tokenizer: lowercase split on whitespace
    for tok in text.lower().split():
        # stable hash: built-in hash is randomized per run, so use sha1
        h = 0
        for ch in tok.encode("utf-8"):
            h = (h * 131 + ch) & 0xFFFFFFFF
        idx = h % dim
        vec[idx] += 1.0
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    vec = [v / norm for v in vec]
    return vec


def _insert_document(conn: sqlite3.Connection, path: Path, content: str, *, embed: bool = False, embed_dim: int = 64) -> None:
    stat = path.stat()
    cur = conn.execute(
        "INSERT INTO docs(path, mtime, size) VALUES(?, ?, ?)\n            ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, size=excluded.size\n            RETURNING id",
        (str(path), stat.st_mtime, stat.st_size),
    )
    doc_id = cur.fetchone()[0]
    conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
    for idx, chunk in enumerate(_chunk_text(content)):
        cur = conn.execute(
            "INSERT INTO chunks(doc_id, chunk_index, content) VALUES(?, ?, ?) RETURNING id",
            (doc_id, idx, chunk),
        )
        chunk_row_id = cur.fetchone()[0]
        if embed:
            emb = _simple_embed(chunk, dim=embed_dim)
            conn.execute(
                "INSERT OR REPLACE INTO embeddings(chunk_id, dim, vec) VALUES(?,?,?)",
                (chunk_row_id, embed_dim, json.dumps(emb)),
            )


def ingest_paths(
    paths: Iterable[str],
    db_path: Optional[str] = None,
    exts: Optional[Iterable[str]] = None,
    *,
    embed: bool = False,
    embed_dim: int = 64,
) -> Tuple[int, int, float]:
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
                            _insert_document(conn, fp, content, embed=embed, embed_dim=embed_dim)
                            n_docs += 1
            else:
                if pth.suffix.lower() not in allowed_exts:
                    continue
                if _needs_ingest(conn, pth):
                    try:
                        content = pth.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    _insert_document(conn, pth, content, embed=embed, embed_dim=embed_dim)
                    n_docs += 1
        # count chunks
        cur = conn.execute("SELECT COUNT(*) FROM chunks")
        n_chunks = int(cur.fetchone()[0])
        conn.commit()
        return n_docs, n_chunks, time.time() - start
    finally:
        conn.close()


def search(query: str, k: int = 5, db_path: Optional[str] = None) -> List[dict]:
    cache_key = f"fts::{db_path or DEFAULT_DB_PATH}::{k}::{query}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached[:k]
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
        _cache_put(cache_key, results)
        return results
    finally:
        conn.close()


def search_embed(query: str, k: int = 5, db_path: Optional[str] = None, embed_dim: int = 64) -> List[dict]:
    cache_key = f"emb::{embed_dim}::{db_path or DEFAULT_DB_PATH}::{k}::{query}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached[:k]
    """Embedding similarity search using cosine distance over stored vectors.

    Requires that documents were ingested with embed=True.
    """
    conn = _connect(db_path)
    try:
        _init_schema(conn)
        q_vec = _simple_embed(query, dim=embed_dim)
        # fetch embeddings joined with chunk + doc metadata
        cur = conn.execute(
            """
            SELECT e.chunk_id, c.doc_id, d.path, c.chunk_index, c.content, e.vec, e.dim
            FROM embeddings e
            JOIN chunks c ON c.id = e.chunk_id
            JOIN docs d ON d.id = c.doc_id
            WHERE e.dim = ?
            """,
            (embed_dim,),
        )
        results = []
        for row in cur.fetchall():
            chunk_id, doc_id, path, chunk_index, content, vec_json, dim = row
            emb = json.loads(vec_json)
            # cosine since vectors L2 normalized => dot product
            sim = sum(a * b for a, b in zip(q_vec, emb))
            # score as (1 - sim) so lower is better similar to bm25 semantics
            score = 1.0 - sim
            snippet = content[:200].replace("\n", " ")
            results.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "path": path,
                    "chunk_index": chunk_index,
                    "snippet": snippet,
                    "score": score,
                    "similarity": sim,
                }
            )
        results.sort(key=lambda r: r["score"])  # lower distance first
        _cache_put(cache_key, results)
        return results[:k]
    finally:
        conn.close()


def search_hybrid(
    query: str,
    k: int = 5,
    db_path: Optional[str] = None,
    embed_dim: int = 64,
    alpha: float = 0.5,
    rrf_k: int = 60,
) -> List[dict]:
    """Hybrid retrieval combining lexical BM25 (fts) + embedding similarity.

    Uses Reciprocal Rank Fusion (RRF) over individual ranked lists, then rescales with
    a simple weighted score: hybrid_score = alpha * norm_bm25 + (1-alpha) * norm_sim.

    For a lightweight demo we approximate normalization:
      norm_bm25 = 1 - rank_ft / len_ft
      norm_sim  = similarity (already 0..1-ish for our toy embeddings)
    """
    cache_key = f"hyb::{embed_dim}::{db_path or DEFAULT_DB_PATH}::{k}::{alpha:.3f}::{query}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached[:k]
    fts_results = search(query, k=max(k, 20), db_path=db_path)
    emb_results = search_embed(query, k=max(k, 50), db_path=db_path, embed_dim=embed_dim)
    # Build rank maps
    fts_rank: Dict[int, int] = {r["chunk_id"]: i for i, r in enumerate(fts_results)}
    fused: Dict[int, dict] = {}
    for lst in (fts_results, emb_results):
        for i, r in enumerate(lst):
            cid = r["chunk_id"]
            if cid not in fused:
                fused[cid] = r.copy()
            # RRF contribution
            fused[cid]["_rrf"] = fused[cid].get("_rrf", 0.0) + 1.0 / (rrf_k + i + 1)
    # compute final hybrid score
    len_fts = len(fts_results) or 1
    for cid, r in fused.items():
        rank_ft = fts_rank.get(cid, len_fts)
        norm_bm25 = 1.0 - (rank_ft / (len_fts + 1))
        sim = r.get("similarity") or (1.0 - float(r.get("score", 1.0)))
        hybrid_score = alpha * norm_bm25 + (1 - alpha) * sim
        r["hybrid_score"] = hybrid_score
    ranked = sorted(fused.values(), key=lambda x: x["hybrid_score"], reverse=True)
    _cache_put(cache_key, ranked)
    return ranked[:k]


def pack(query: str, results: List[dict], max_chars: int = 4000) -> dict:
    """Pack ordered retrieval results into a context block respecting character budget.

    Returns dict with combined text and list of included chunk metadata.
    """
    included = []
    buf_parts: List[str] = []
    total = 0
    for r in results:
        header = f"# {Path(r['path']).name} chunk={r['chunk_index']}\n"
        # fetch full content for chunk (we only stored snippet); simplest approach: re-query chunk content
        # For minimal implementation we skip refetch and just use snippet (already representative)
        chunk_text = r.get("snippet", "")
        block = header + chunk_text + "\n\n"
        if total + len(block) > max_chars:
            break
        buf_parts.append(block)
        total += len(block)
        included.append({k: r[k] for k in ("path", "chunk_index", "chunk_id")})
    return {"packed": "".join(buf_parts).rstrip(), "included": included, "chars": total, "query": query}


def stats(db_path: Optional[str] = None) -> dict:
    conn = _connect(db_path)
    try:
        _init_schema(conn)
        doc_count = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        sizes = conn.execute("SELECT COALESCE(SUM(size),0), COALESCE(AVG(size),0) FROM docs").fetchone()
        total_size, avg_size = sizes
        largest = conn.execute(
            "SELECT path, size FROM docs ORDER BY size DESC LIMIT 5"
        ).fetchall()
        return {
            "docs": doc_count,
            "chunks": chunk_count,
            "total_bytes": int(total_size),
            "avg_bytes": float(avg_size),
            "largest": [{"path": p, "size": s} for (p, s) in largest],
        }
    finally:
        conn.close()


def prune(db_path: Optional[str] = None) -> dict:
    """Remove docs whose files no longer exist by rebuilding index.

    Strategy: capture surviving file paths, record counts, recreate DB from scratch
    for remaining files. This avoids FTS trigger complexities on bulk deletes.
    """
    db_file = db_path or DEFAULT_DB_PATH
    conn = _connect(db_file)
    try:
        _init_schema(conn)
        # snapshot existing counts
        old_chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        cur = conn.execute("SELECT path FROM docs")
        surviving: list[str] = []
        missing_docs = 0
        for (p,) in cur.fetchall():
            if Path(p).exists():
                surviving.append(p)
            else:
                missing_docs += 1
    finally:
        conn.close()

    if missing_docs == 0:
        return {"removed_docs": 0, "removed_chunks": 0}

    # Recreate database file (simple approach for small scale indexes)
    try:
        os.remove(db_file)
    except OSError:
        pass
    # Re-ingest surviving files
    _, new_chunk_count, _ = ingest_paths(surviving, db_path=db_file)
    removed_chunks = old_chunk_count - new_chunk_count
    if removed_chunks < 0:
        removed_chunks = 0
    return {"removed_docs": missing_docs, "removed_chunks": int(removed_chunks)}
