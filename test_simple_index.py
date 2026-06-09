import sqlite3
import pytest

from app.rag.simple_index import _search_with_conn

def test_sql_like_wildcard_escaped():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE fts USING fts5(content)")
    conn.execute("CREATE TABLE docs (id INTEGER PRIMARY KEY, path TEXT, mtime REAL, size INTEGER)")
    conn.execute("CREATE TABLE chunks (id INTEGER PRIMARY KEY, doc_id INTEGER, chunk_index INTEGER, content TEXT)")

    conn.execute("INSERT INTO docs VALUES (1, 'path/to/doc', 1000, 100)")

    # We add % to content and try to query for it literally
    conn.execute("INSERT INTO chunks (id, doc_id, chunk_index, content) VALUES (1, 1, 1, 'This is a test with a % sign')")
    conn.execute("INSERT INTO chunks (id, doc_id, chunk_index, content) VALUES (2, 1, 2, 'This is a test without the sign')")
    conn.commit()

    # If the wildcard is NOT escaped properly, it would act as a wildcard and match the second one.
    # Wait, the code ALREADY has the fix!
    results = _search_with_conn(conn, query="%", k=10)
    # The fix is ESCAPE '\', which means `\%` should match literal `%`
    print(results)

test_sql_like_wildcard_escaped()
