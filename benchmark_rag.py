import time
import os
from pathlib import Path
from app.rag.simple_index import ingest_paths


def create_large_file(path, num_paragraphs):
    with open(path, "w") as f:
        # A simple long string of text
        sentence = "This is a sentence to test the chunking and embedding logic. " * 10
        f.write((sentence + "\n\n") * num_paragraphs)


if __name__ == "__main__":
    test_file = Path("test_large_doc.txt")
    db_path = "test_index.db"

    # Generate around 10000 paragraphs (should be around 10000 chunks based on logic)
    create_large_file(test_file, 10000)
    print(f"Created file size: {os.path.getsize(test_file)}")

    if os.path.exists(db_path):
        os.remove(db_path)

    start_time = time.time()
    n_docs, n_chunks, elapsed = ingest_paths(
        [str(test_file)], db_path=db_path, embed=True, embed_dim=64, chunking_strategy="paragraph"
    )
    end_time = time.time()

    print(
        f"Baseline - Ingested {n_docs} docs, {n_chunks} chunks in {end_time - start_time:.4f} seconds."
    )
    print(f"Baseline - Elapsed reported: {elapsed:.4f} seconds.")

    # Clean up
    if os.path.exists(test_file):
        os.remove(test_file)
    if os.path.exists(db_path):
        os.remove(db_path)
