import os
import sqlite3
import tempfile
from app.rag.simple_index import ingest_text, _connect, search_embed
from unittest.mock import patch

def test_delete_chunk_cleans_up_embeddings():
    with tempfile.TemporaryDirectory() as td:
        test_db = os.path.join(td, "test_cleanup.db")
        upload_dir = os.path.join(td, "uploads")

        with (
            patch("app.rag.simple_index.DEFAULT_DB_PATH", test_db),
            patch.dict(
                os.environ,
                {
                    "PROMPTC_UPLOAD_DIR": upload_dir,
                    "PROMPTC_RAG_ALLOWED_ROOTS": td,
                },
                clear=False,
            ),
        ):
            # Ingest text with embed=True
            doc_path, chunks, _ = ingest_text("secret_doc.txt", "This is a super secret document with sensitive data.", db_path=test_db, embed=True)

            # Verify data is in chunks and embeddings
            conn = _connect(test_db)
            cur = conn.cursor()

            cur.execute("SELECT id FROM chunks")
            chunk_ids = [r[0] for r in cur.fetchall()]
            assert len(chunk_ids) > 0, "Chunks were not created"

            cur.execute("SELECT chunk_id FROM embeddings")
            emb_chunk_ids = [r[0] for r in cur.fetchall()]
            assert len(emb_chunk_ids) > 0, "Embeddings were not created"

            # Re-ingest the document, replacing the old chunks
            doc_path2, chunks2, _ = ingest_text("secret_doc.txt", "Replacement document.", db_path=test_db, embed=True)

            # The old chunks should have been deleted (since doc_id matches and we do DELETE FROM chunks)
            # This should also trigger the chunks_ad_embed trigger and delete the old embeddings.
            # If the trigger didn't exist, we'd have orphaned embeddings.

            cur.execute("SELECT id FROM chunks")
            new_chunk_ids = [r[0] for r in cur.fetchall()]

            cur.execute("SELECT chunk_id FROM embeddings")
            new_emb_chunk_ids = [r[0] for r in cur.fetchall()]

            # Verify the old chunk IDs are gone from embeddings
            for old_id in chunk_ids:
                if old_id not in new_chunk_ids:
                    assert old_id not in new_emb_chunk_ids, f"Orphaned embedding found for deleted chunk {old_id}"

            conn.close()
