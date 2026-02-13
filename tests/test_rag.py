import pytest
from unittest.mock import MagicMock
from app.llm_engine.rag import ContextStrategist, Snippet


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
