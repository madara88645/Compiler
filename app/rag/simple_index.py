import os
import sqlite3
import time
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Dict
import math
import json
from collections import OrderedDict

# Document parser for multi-format support
try:
    from app.rag.parsers import parse_file, get_supported_extensions, can_parse

    _HAS_PARSERS = True
except ImportError:
    _HAS_PARSERS = False

# Minimal SQLite FTS5-based retriever. No external deps.
# Schema:
#   docs(id INTEGER PRIMARY KEY, path TEXT UNIQUE, mtime REAL, size INTEGER)
#   chunks(id INTEGER PRIMARY KEY, doc_id INTEGER, chunk_index INTEGER, content TEXT)
#   fts(content) USING fts5(content, content="", tokenize="porter")
#   embeddings(chunk_id INTEGER PRIMARY KEY, dim INTEGER, vec TEXT)  -- vec is JSON list of floats (L2 normalized)
#   Triggers keep fts in sync with chunks.

DEFAULT_DB_PATH = os.path.expanduser("~/.promptc_index.db")
# Force absolute path for debugging Windows environment
if os.name == "nt":
    DEFAULT_DB_PATH = r"C:\Users\User\.promptc_index.db"

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
        CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(content, tokenize="unicode61 tokenchars '_'");
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


def get_all_indexed_files(db_path: Optional[str] = None) -> List[str]:
    """Retrieve all file paths currently in the index."""
    try:
        conn = _connect(db_path)
        cursor = conn.execute("SELECT path FROM docs")
        paths = [row[0] for row in cursor.fetchall()]
        conn.close()
        return paths
    except Exception:
        return []


def _needs_ingest(conn: sqlite3.Connection, path: Path) -> bool:
    stat = path.stat()
    cur = conn.execute("SELECT mtime, size FROM docs WHERE path=?", (str(path),))
    row = cur.fetchone()
    return not row or row[0] != stat.st_mtime or row[1] != stat.st_size


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences using regex.

    Handles standard punctuation (.!?) while avoiding splits on abbreviations.
    """
    import re

    # Pattern: Split on .!? followed by whitespace, but not after common abbreviations
    pattern = r"(?<![A-Z][a-z]\.)"  # Negative lookbehind for abbreviations like "Dr."
    pattern += r"(?<![A-Z]\.)"  # Negative lookbehind for initials like "J."
    pattern += r"(?<=\.|\?|!)\s+"  # Positive lookbehind for sentence-ending punctuation

    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def _chunk_text_fixed(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> List[str]:
    """Original fixed character-based chunking."""
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


def _chunk_text_paragraph(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Paragraph-aware chunking with sentence fallback.

    Strategy:
    1. Split on paragraph boundaries (\n\n)
    2. If a paragraph is too large, split on sentence boundaries
    3. Never split mid-sentence
    4. Use last sentence as overlap for context continuity
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = text.split("\n\n")

    chunks: List[str] = []
    current_chunk = ""
    last_sentence = ""  # For overlap

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check if paragraph fits in current chunk
        test_chunk = current_chunk + ("\n\n" if current_chunk else "") + para

        if len(test_chunk) <= chunk_size:
            current_chunk = test_chunk
        else:
            # Paragraph too large to add - flush current if non-empty
            if current_chunk:
                chunks.append(current_chunk)
                # Get last sentence for overlap
                sentences = _split_sentences(current_chunk)
                last_sentence = sentences[-1] if sentences else ""

            # Check if paragraph itself is too large
            if len(para) > chunk_size:
                # Split paragraph into sentences
                sentences = _split_sentences(para)
                current_chunk = last_sentence + "\n\n" if last_sentence else ""

                for sent in sentences:
                    test = current_chunk + (" " if current_chunk.rstrip() else "") + sent

                    if len(test) <= chunk_size:
                        current_chunk = test
                    else:
                        # Flush and start new
                        if current_chunk.strip():
                            chunks.append(current_chunk.strip())
                        current_chunk = sent
                        last_sentence = ""
            else:
                # Start new chunk with overlap
                current_chunk = (last_sentence + "\n\n" + para) if last_sentence else para

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


def _chunk_text_semantic(
    text: str, chunk_size: int = CHUNK_SIZE, similarity_threshold: float = 0.3
) -> List[str]:
    """Semantic chunking using simple TF-IDF similarity.

    Groups sentences by topic similarity:
    1. Split into sentences
    2. Compute simple TF-IDF for each sentence
    3. Group sentences while they remain similar to the first
    4. Start new chunk when similarity drops below threshold
    """
    from collections import Counter
    import math

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    sentences = _split_sentences(text)

    if not sentences:
        return [text] if text.strip() else []

    if len(sentences) == 1:
        return sentences

    # Build vocabulary and compute TF-IDF
    def tokenize(s: str) -> List[str]:
        return [w.lower() for w in s.split() if len(w) > 2]

    # Document frequency
    doc_freq: Counter = Counter()
    for sent in sentences:
        tokens = set(tokenize(sent))
        for tok in tokens:
            doc_freq[tok] += 1

    n_docs = len(sentences)

    def compute_tfidf(sentence: str) -> Dict[str, float]:
        tokens = tokenize(sentence)
        tf = Counter(tokens)
        tfidf = {}
        for tok, count in tf.items():
            idf = math.log((n_docs + 1) / (doc_freq.get(tok, 0) + 1)) + 1
            tfidf[tok] = (count / len(tokens)) * idf if tokens else 0
        return tfidf

    def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
        if not v1 or not v2:
            return 0.0
        common_keys = set(v1.keys()) & set(v2.keys())
        dot = sum(v1[k] * v2[k] for k in common_keys)
        norm1 = math.sqrt(sum(v * v for v in v1.values()))
        norm2 = math.sqrt(sum(v * v for v in v2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    # Group sentences
    chunks = []
    current_chunk = sentences[0]
    anchor_tfidf = compute_tfidf(sentences[0])

    for sent in sentences[1:]:
        sent_tfidf = compute_tfidf(sent)
        sim = cosine_similarity(anchor_tfidf, sent_tfidf)

        test_chunk = current_chunk + " " + sent

        # Keep grouping if similar and within size
        if sim >= similarity_threshold and len(test_chunk) <= chunk_size:
            current_chunk = test_chunk
        else:
            # Start new chunk
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = sent
            anchor_tfidf = sent_tfidf

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]


def _chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    strategy: str = "paragraph",
) -> List[str]:
    """Smart text chunking with multiple strategies.

    Args:
        text: Input text to chunk
        chunk_size: Maximum characters per chunk
        overlap: Character overlap (only used for 'fixed' strategy)
        strategy: Chunking strategy
            - "fixed": Original character-based splitting
            - "paragraph": Split on paragraph boundaries with sentence fallback
            - "semantic": Group sentences by topic similarity (TF-IDF)

    Returns:
        List of text chunks
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    if strategy == "fixed":
        return _chunk_text_fixed(text, chunk_size, overlap)
    elif strategy == "semantic":
        return _chunk_text_semantic(text, chunk_size)
    else:  # Default to paragraph
        return _chunk_text_paragraph(text, chunk_size)


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


def _insert_document(
    conn: sqlite3.Connection,
    path: Path,
    content: str,
    *,
    embed: bool = False,
    embed_dim: int = 64,
    chunking_strategy: str = "paragraph",
) -> None:
    stat = path.stat()
    cur = conn.execute(
        "INSERT INTO docs(path, mtime, size) VALUES(?, ?, ?)\n            ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime, size=excluded.size\n            RETURNING id",
        (str(path), stat.st_mtime, stat.st_size),
    )
    doc_id = cur.fetchone()[0]
    conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
    for idx, chunk in enumerate(_chunk_text(content, strategy=chunking_strategy)):
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
    chunking_strategy: str = "paragraph",
) -> Tuple[int, int, float]:
    """Ingest files into the RAG index.

    Args:
        paths: File or directory paths to ingest
        db_path: Database path (defaults to ~/.promptc_index.db)
        exts: Allowed file extensions
        embed: Whether to compute embeddings
        embed_dim: Embedding dimension
        chunking_strategy: How to split text into chunks
            - "fixed": Character-based with fixed overlap
            - "paragraph": Paragraph-aware with sentence fallback (default)
            - "semantic": TF-IDF based topic grouping

    Returns:
        Tuple of (num_docs, num_chunks, elapsed_seconds)
    """
    start = time.time()
    conn = _connect(db_path)
    try:
        _init_schema(conn)
        n_docs = 0
        n_chunks = 0
        # Use parser-supported extensions if available, else fallback
        if _HAS_PARSERS and exts is None:
            allowed_exts = set(get_supported_extensions())
        else:
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
                                if _HAS_PARSERS and can_parse(fp):
                                    result = parse_file(fp)
                                    content = result.content
                                else:
                                    content = fp.read_text(encoding="utf-8", errors="ignore")
                            except Exception:
                                continue
                            if not content:
                                continue
                            _insert_document(
                                conn,
                                fp,
                                content,
                                embed=embed,
                                embed_dim=embed_dim,
                                chunking_strategy=chunking_strategy,
                            )
                            n_docs += 1
            else:
                if pth.suffix.lower() not in allowed_exts:
                    continue
                if _needs_ingest(conn, pth):
                    try:
                        if _HAS_PARSERS and can_parse(pth):
                            result = parse_file(pth)
                            content = result.content
                        else:
                            content = pth.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    if not content:
                        continue
                    _insert_document(
                        conn,
                        pth,
                        content,
                        embed=embed,
                        embed_dim=embed_dim,
                        chunking_strategy=chunking_strategy,
                    )
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
        # Use simple LIKE for robustness if FTS fails or behaves oddly
        # 1. Try FTS Search
        try:
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
                (f"{query}*", k),
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
        except Exception as e:
            print(f"[DEBUG] FTS Search failed or returned error: {e}")
            results = []

        # 2. Fallback to LIKE if not enough results
        if len(results) < k:
            seen_ids = {r["chunk_id"] for r in results}
            limit_needed = k - len(results)

            cur = conn.execute(
                """
                SELECT c.id, c.doc_id, d.path, c.chunk_index,
                       c.content,
                       0.5 as score
                FROM chunks c
                JOIN docs d ON d.id = c.doc_id
                WHERE lower(c.content) LIKE lower(?)
                LIMIT ?
                """,
                (f"%{query}%", limit_needed * 2),  # Grab a few more to filter dupes
            )

            for row in cur.fetchall():
                if row[0] not in seen_ids:
                    # Create a simple snippet
                    content = row[4]
                    idx = content.lower().find(query.lower())
                    start = max(0, idx - 20)
                    end = min(len(content), idx + len(query) + 20)
                    snippet = f"…{content[start:end]}…"

                    results.append(
                        {
                            "chunk_id": row[0],
                            "doc_id": row[1],
                            "path": row[2],
                            "chunk_index": row[3],
                            "snippet": snippet,
                            "score": row[5],
                        }
                    )
                    seen_ids.add(row[0])
                    if len(results) >= k:
                        break

        _cache_put(cache_key, results)
        return results
    finally:
        conn.close()


def search_embed(
    query: str, k: int = 5, db_path: Optional[str] = None, embed_dim: int = 64
) -> List[dict]:
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


# Optional tiktoken support for accurate token counting
_tiktoken_enc = None


def _count_tokens(text: str, ratio: float = 4.0) -> int:
    """Count tokens using tiktoken (if available) or fallback to char ratio."""
    global _tiktoken_enc
    try:
        if _tiktoken_enc is None:
            import tiktoken

            _tiktoken_enc = tiktoken.get_encoding("cl100k_base")
        return len(_tiktoken_enc.encode(text))
    except ImportError:
        return int(len(text) / ratio)


def pack(
    query: str,
    results: List[dict],
    max_chars: int = 4000,
    *,
    max_tokens: Optional[int] = None,
    token_chars: float = 4.0,  # Used only for fallback
    dedup: bool = False,
    token_aware: bool = False,
) -> dict:
    """Pack ordered retrieval results into a context block respecting budget.

    Budgets:
      - max_chars: upper bound by character count
      - max_tokens: approximate token budget (tokens ≈ len(text)/token_chars)

    Args:
        dedup: If True, skip chunks with identical content.
    """
    included = []
    buf_parts: List[str] = []
    total = 0
    total_tokens = 0
    seen_content = set()

    for r in results:
        # fetch full content for chunk (we only stored snippet); simplest approach: re-query chunk content
        # For minimal implementation we skip refetch and just use snippet (already representative)
        chunk_text = r.get("snippet", "")

        if dedup:
            # Normalize for dedup checks (strip whitespace)
            norm = chunk_text.strip()
            if norm in seen_content:
                continue
            seen_content.add(norm)

        score_val = r.get("hybrid_score") or r.get("score")
        score_str = f" score={score_val:.3f}" if score_val is not None else ""
        header = (
            f"# {Path(r.get('path', 'unknown')).name} chunk={r.get('chunk_index', 0)}{score_str}\n"
        )

        block = header + chunk_text + "\n\n"

        block_len = len(block)
        block_tokens = _count_tokens(block, token_chars)

        if max_tokens is not None and (total_tokens + block_tokens) > max_tokens:
            break

        next_chars = total + block_len
        if next_chars > max_chars:
            break

        buf_parts.append(block)
        total = next_chars
        total_tokens += block_tokens
        included.append({k: r[k] for k in ("path", "chunk_index", "chunk_id") if k in r})

    return {
        "packed": "".join(buf_parts).rstrip(),
        "included": included,
        "chars": total,
        "tokens": total_tokens,
        "query": query,
        "budget": {"max_chars": max_chars, "max_tokens": max_tokens, "token_chars": token_chars},
    }


def stats(db_path: Optional[str] = None) -> dict:
    conn = _connect(db_path)
    try:
        _init_schema(conn)
        doc_count = conn.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
        chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        sizes = conn.execute(
            "SELECT COALESCE(SUM(size),0), COALESCE(AVG(size),0) FROM docs"
        ).fetchone()
        total_size, avg_size = sizes
        largest = conn.execute("SELECT path, size FROM docs ORDER BY size DESC LIMIT 5").fetchall()
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
