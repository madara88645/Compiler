import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute(
    "CREATE TABLE chunks (id INTEGER PRIMARY KEY, doc_id INTEGER, chunk_index INTEGER, content TEXT)"
)
conn.execute("CREATE TABLE embeddings (chunk_id INTEGER PRIMARY KEY, dim INTEGER, vec TEXT)")

doc_id = 1
chunks = ["hello", "world", "foo", "bar"]

chunk_rows = [(doc_id, idx, chunk) for idx, chunk in enumerate(chunks)]
conn.executemany("INSERT INTO chunks(doc_id, chunk_index, content) VALUES(?, ?, ?)", chunk_rows)

cur = conn.execute(
    "SELECT id, chunk_index, content FROM chunks WHERE doc_id = ? ORDER BY chunk_index", (doc_id,)
)
fetched = cur.fetchall()
print("Fetched chunks:", fetched)
