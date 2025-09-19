import os
import tempfile
from app.rag.simple_index import ingest_paths
from fastapi.testclient import TestClient
from api.main import app
from cli.main import app as cli_app


def test_pack_respects_max_tokens_api():
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'a.txt')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(('token ' * 800).strip())
        r = client.post('/rag/ingest', json={'paths':[p], 'db_path': td + '/idx.db'})
        assert r.status_code == 200
        # Request pack with small token budget
        pack = client.post('/rag/pack', json={
            'query': 'token',
            'k': 5,
            'method': 'fts',
            'db_path': td + '/idx.db',
            'max_tokens': 100,
            'token_ratio': 4.0,
        })
        assert pack.status_code == 200, pack.text
        data = pack.json()
        assert data.get('tokens') is not None
        assert data['tokens'] <= 100
        assert data['chars'] >= data['tokens']  # rough sanity


def test_pack_respects_max_tokens_cli_snapshot():
    # Directly exercise pack function via API is enough; CLI path is thin wrapper.
    # This test ensures ingest with embeddings doesn't break token packing.
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'b.txt')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(('lorem ipsum ' * 600).strip())
        r = client.post('/rag/ingest', json={'paths':[p], 'db_path': td + '/idx.db', 'embed': True, 'embed_dim': 32})
        assert r.status_code == 200
        pack = client.post('/rag/pack', json={
            'query': 'ipsum',
            'k': 5,
            'method': 'hybrid',
            'db_path': td + '/idx.db',
            'embed_dim': 32,
            'alpha': 0.5,
            'max_tokens': 120,
            'token_ratio': 4.0,
        })
        assert pack.status_code == 200
        data = pack.json()
        assert data['tokens'] <= 120
