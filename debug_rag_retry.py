import os
from app.rag.simple_index import ingest_paths, search, stats

# Use a temp db
temp_db_path = "test_rag_retry.db"
if os.path.exists(temp_db_path):
    os.remove(temp_db_path)

# Create a test file
test_file = "test_rag_retry.py"
with open(test_file, "w") as f:
    f.write(
        """
def test_pack_budget():
    packed = pack("test query", results, max_chars=50)
"""
    )

print("Ingesting...")
# Note: Ingest paths automatically uses the hardcoded path if we don't pass db_path
# But since I hardcoded it for Windows, I should override it here for testing if I want a temp file.
# BUT wait, I hardcoded it inside the function default arg? No, global variable.
# Let's see if I can override the global for the test script or pass it explicitly.
# The `search` function takes `db_path`.
ingest_paths([test_file], db_path=temp_db_path)

print("\n--- Stats ---")
print(stats(db_path=temp_db_path))

print("\n--- Search 'max_chars' (Should find via LIKE fallback) ---")
res_kw = search("max_chars", db_path=temp_db_path)
print(f"Found {len(res_kw)} results")
for r in res_kw:
    print(r)

# Clean up
try:
    os.remove(test_file)
    os.remove(temp_db_path)
except Exception:
    pass
