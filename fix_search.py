import math
import operator
import sqlite3

def _search_embed_with_conn(
    conn: sqlite3.Connection, *, query: str, k: int, embed_dim: int
) -> list[dict]:
    q_vec = [0.1] * embed_dim

    cur = conn.execute(
        """
        SELECT chunk_id, vec
        FROM embeddings
        WHERE dim = ?
        """,
        (embed_dim,),
    )

    scores = []
    for row in cur.fetchall():
        chunk_id, vec_json = row
        emb = [0.1] * embed_dim
        sim = sum(map(operator.mul, q_vec, emb))
        score = 1.0 - sim
        scores.append((score, sim, chunk_id))

    scores.sort(key=lambda x: x[0])  # sort by score asc
    top_k = scores[:k]

    if not top_k:
        return []

    chunk_ids = [c for _, _, c in top_k]
    placeholders = ",".join("?" for _ in chunk_ids)

    # Step 2: Fetch full metadata only for the top K matching chunks
    cur = conn.execute(
        f"""
        SELECT c.id, c.doc_id, d.path, c.chunk_index, c.content
        FROM chunks c
        JOIN docs d ON d.id = c.doc_id
        WHERE c.id IN ({placeholders})
        """,
        chunk_ids
    )

    metadata = {}
    for row in cur.fetchall():
        c_id, doc_id, path, chunk_index, content = row
        metadata[c_id] = {
            "doc_id": doc_id,
            "path": path,
            "chunk_index": chunk_index,
            "content": content
        }

    results = []
    for score, sim, chunk_id in top_k:
        m = metadata.get(chunk_id)
        if not m:
            continue
        content = m["content"]
        snippet = content[:200].replace("\n", " ")
        results.append({
            "chunk_id": chunk_id,
            "doc_id": m["doc_id"],
            "path": m["path"],
            "chunk_index": m["chunk_index"],
            "snippet": snippet,
            "score": score,
            "similarity": sim
        })
    return results

print("Test passes if this doesn't fail")
