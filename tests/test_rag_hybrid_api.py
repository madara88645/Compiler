import os
import tempfile
from fastapi.testclient import TestClient
from api.main import app


def test_rag_query_hybrid_and_pack():
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as td:
        # create small docs
        p1 = os.path.join(td, 'a.txt')
        p2 = os.path.join(td, 'b.txt')
        open(p1,'w', encoding='utf-8').write('Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau')
        open(p2,'w', encoding='utf-8').write('Beta gamma delta epsilon some other tokens to differentiate content and provide overlap for hybrid retrieval test case.')
        # ingest with embeddings
        r = client.post('/rag/ingest', json={'paths':[p1,p2], 'db_path': td + '/idx.db', 'embed': True, 'embed_dim': 32})
        assert r.status_code == 200, r.text
        # hybrid query
        q = client.post('/rag/query', json={'query':'beta gamma', 'k':5, 'method':'hybrid', 'db_path': td + '/idx.db', 'embed_dim': 32, 'alpha':0.4})
        assert q.status_code == 200, q.text
        data = q.json()
        assert data['count'] > 0
        # ensure hybrid_score present
        assert any('hybrid_score' in r for r in data['results'])
        # pack endpoint
        pack = client.post('/rag/pack', json={'query':'beta gamma', 'k':5, 'method':'hybrid', 'db_path': td + '/idx.db', 'embed_dim':32, 'alpha':0.4, 'max_chars': 500})
        assert pack.status_code == 200, pack.text
        pdata = pack.json()
        assert 'packed' in pdata and isinstance(pdata['packed'], str)
        assert pdata['chars'] <= 500
        assert pdata['included']
