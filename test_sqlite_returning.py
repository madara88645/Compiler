import sqlite3

conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, doc_id INTEGER, chunk_index INTEGER, content TEXT)")

doc_id = 1
chunks = ["hello", "world", "foo", "bar"]

chunk_rows = [(doc_id, idx, chunk) for idx, chunk in enumerate(chunks)]

try:
    cur = conn.executemany("INSERT INTO chunks(doc_id, chunk_index, content) VALUES(?, ?, ?) RETURNING id", chunk_rows)
    print("Fetched from executemany:", cur.fetchall())
except Exception as e:
    print("Error:", e)
