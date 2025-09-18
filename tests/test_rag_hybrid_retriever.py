import os
import tempfile
from app.rag.simple_index import ingest_paths, search, search_embed, search_hybrid, pack


def _write(p, txt):
    with open(p, 'w', encoding='utf-8') as f:
        f.write(txt)


def test_hybrid_fallback_without_embeddings():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'doc.txt')
        _write(p, 'alpha beta gamma delta epsilon zeta eta theta')
        # ingest without embeddings
        ingest_paths([p], db_path=td + '/idx.db', embed=False)
        # hybrid should still return lexical results (no error)
        res = search_hybrid('alpha beta', k=3, db_path=td + '/idx.db', embed_dim=64)
        assert res, 'Hybrid should return results even if embeddings missing'
        # ensure hybrid_score present
        assert 'hybrid_score' in res[0]


def test_pack_char_limit():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'doc.txt')
        _write(p, ' '.join(['token'] * 500))
        ingest_paths([p], db_path=td + '/idx.db', embed=False)
        res = search('token', k=5, db_path=td + '/idx.db')
        packed = pack('token', res, max_chars=120)
        assert packed['chars'] <= 120
        # included not empty
        assert packed['included']


def test_cache_consistency():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'doc.txt')
        _write(p, 'alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu')
        ingest_paths([p], db_path=td + '/idx.db', embed=True, embed_dim=32)
        first = search_embed('alpha beta', k=3, db_path=td + '/idx.db', embed_dim=32)
        second = search_embed('alpha beta', k=3, db_path=td + '/idx.db', embed_dim=32)
        # Should be identical lists (cache hit)
        assert first == second
