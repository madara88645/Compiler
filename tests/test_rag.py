import pytest
from unittest.mock import MagicMock, patch
from app.llm_engine.rag import ContextStrategist, Snippet, MockVectorDB, SQLiteVectorDB


# Mock WorkerClient
class MockLLMClient:
    def expand_query_intent(self, text):
        return {"queries": [text, "expanded query"]}


@pytest.fixture
def mock_db():
    db = MagicMock()
    # Mock search results
    db.search.return_value = [
        {"file_path": "app/main.py", "content": "def main(): pass", "metadata": {}},
        {"file_path": "app/utils.py", "content": "def util(): pass", "metadata": {}},
    ]
    return db


@pytest.fixture
def strategist(mock_db):
    return ContextStrategist(mock_db, MockLLMClient())


def test_expand_query(strategist):
    queries = strategist.expand_query("fix login")
    assert "fix login" in queries
    assert "expanded query" in queries
    assert len(queries) == 2


def test_expand_query_filters_invented_artifact_names(mock_db):
    class ArtifactLLMClient:
        def expand_query_intent(self, text):
            return {
                "queries": [
                    "User.authenticate",
                    "password_regex",
                    "login error handling",
                    text,
                ]
            }

    strategist = ContextStrategist(mock_db, ArtifactLLMClient())

    queries = strategist.expand_query(
        "The login page returns 500 when the password has a special character."
    )

    assert queries == [
        "The login page returns 500 when the password has a special character.",
        "login error handling",
    ]


def test_retrieve_rrf(strategist, mock_db):
    # Setup mock returns structure for multiple calls if needed
    # But for now the simple return_value is enough

    snippets = strategist.retrieve(["q1", "q2"])

    # We expect duplicates to be merged and scores to be accumulated
    # app/main.py appears in both queries (mocked)
    # Score for app/main.py:
    #   q1: rank 0 -> score 1/1 = 1.0
    #   q2: rank 0 -> score 1/1 = 1.0
    #   Total = 2.0

    assert len(snippets) == 2
    assert snippets[0].file_path == "app/main.py"
    assert snippets[0].score == 2.0
    assert snippets[1].file_path == "app/utils.py"
    assert snippets[1].score == 1.0  # 0.5 + 0.5 = 1.0


def test_rank_and_prune(strategist):
    snippets = [
        Snippet("a.py", "a" * 400, 10.0, {}),  # 100 tokens
        Snippet("b.py", "b" * 400, 5.0, {}),  # 100 tokens
        Snippet("c.py", "c" * 400, 1.0, {}),  # 100 tokens
    ]

    # Case 1: All fit
    result = strategist.rank_and_prune(snippets, max_tokens=500)
    assert len(result) == 3

    # Case 2: Only top 2 fit
    result = strategist.rank_and_prune(snippets, max_tokens=250)
    assert len(result) == 2
    assert result[0].file_path == "a.py"
    assert result[1].file_path == "b.py"


def test_process_end_to_end(strategist):
    result = strategist.process("fix login")

    assert "retrieved_files" in result
    assert "app/main.py" in result["retrieved_files"]
    assert "snippets" in result
    assert len(result["snippets"]) == 2


def test_mock_vector_db():
    db = MockVectorDB()
    assert db.search("anything") == []


@patch("app.llm_engine.rag.search_hybrid")
def test_sqlite_vector_db_success(mock_search_hybrid):
    db = SQLiteVectorDB(db_path="dummy.db")
    mock_search_hybrid.return_value = [
        {
            "path": "test.py",
            "snippet": "content",
            "hybrid_score": 0.9,
            "chunk_index": 1,
            "chunk_id": "c1",
        }
    ]

    results = db.search("query")
    assert len(results) == 1
    assert results[0]["file_path"] == "test.py"
    assert results[0]["content"] == "content"
    assert results[0]["score"] == 0.9
    assert results[0]["metadata"]["chunk_index"] == 1
    assert results[0]["metadata"]["chunk_id"] == "c1"

    mock_search_hybrid.assert_called_once_with(
        "query", k=5, db_path="dummy.db", embed_dim=64, alpha=0.35
    )


@patch("app.llm_engine.rag.search")
@patch("app.llm_engine.rag.search_hybrid")
def test_sqlite_vector_db_fallback(mock_search_hybrid, mock_search):
    db = SQLiteVectorDB(db_path="dummy.db")
    mock_search_hybrid.side_effect = Exception("Hybrid search failed")
    mock_search.return_value = [
        {
            "path": "test2.py",
            "snippet": "content2",
            "score": 0.2,
            "chunk_index": 2,
            "chunk_id": "c2",
        }
    ]

    results = db.search("query")
    assert len(results) == 1
    assert results[0]["file_path"] == "test2.py"
    assert results[0]["content"] == "content2"
    # Fallback score calculation: 1.0 - score
    assert results[0]["score"] == 0.8
    assert results[0]["metadata"]["chunk_index"] == 2
    assert results[0]["metadata"]["chunk_id"] == "c2"

    mock_search_hybrid.assert_called_once_with(
        "query", k=5, db_path="dummy.db", embed_dim=64, alpha=0.35
    )
    mock_search.assert_called_once_with("query", k=5, db_path="dummy.db")
