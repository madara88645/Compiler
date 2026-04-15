import json
from unittest.mock import MagicMock, patch

from app.agents.context_strategist import ContextStrategist


class TestContextStrategist:
    def test_initialization(self):
        # Test with no client
        strategist = ContextStrategist()
        assert strategist.client is not None

        # Test with provided client
        mock_client = MagicMock()
        strategist_with_client = ContextStrategist(client=mock_client)
        assert strategist_with_client.client == mock_client

    def test_expand_query_success(self):
        mock_client = MagicMock()
        mock_client._call_api.return_value = json.dumps(["query1", "query2", "query3"])
        strategist = ContextStrategist(client=mock_client)

        result = strategist._expand_query("test prompt")
        assert result == ["query1", "query2", "query3"]
        mock_client._call_api.assert_called_once()

    def test_expand_query_malformed_json(self):
        mock_client = MagicMock()
        mock_client._call_api.return_value = "invalid json"
        strategist = ContextStrategist(client=mock_client)

        result = strategist._expand_query("test prompt")
        assert result == []

    def test_expand_query_api_exception(self):
        mock_client = MagicMock()
        mock_client._call_api.side_effect = Exception("API Error")
        strategist = ContextStrategist(client=mock_client)

        result = strategist._expand_query("test prompt")
        assert result == []

    def test_expand_query_non_list_response(self):
        mock_client = MagicMock()
        mock_client._call_api.return_value = json.dumps({"key": "value"})
        strategist = ContextStrategist(client=mock_client)

        result = strategist._expand_query("test prompt")
        assert result == []

    @patch("app.agents.context_strategist.search_hybrid")
    def test_retrieve_happy_path(self, mock_search_hybrid):
        mock_client = MagicMock()
        mock_client._call_api.return_value = json.dumps(["expanded1", "expanded2"])
        strategist = ContextStrategist(client=mock_client)

        # Mocking search_hybrid to return different results based on the query
        def side_effect(query, k):
            if query == "test prompt":
                return [{"path": "file1.py", "score": 1.0}, {"path": "file2.py", "score": 0.8}]
            elif query == "expanded1":
                return [{"path": "file1.py", "score": 0.9}, {"path": "file3.py", "score": 0.5}]
            elif query == "expanded2":
                return [{"path": "file4.py", "score": 0.7}]
            return []

        mock_search_hybrid.side_effect = side_effect

        results = strategist.retrieve("test prompt", limit=3)

        # Verify boosting logic
        # Original query boost: file1.py: 1.0 * 1.5 = 1.5, file2.py: 0.8 * 1.5 = 1.2
        # Expanded query boost: file1.py (confirmation): 1.5 + 0.2 = 1.7
        # Expanded query new: file3.py: 0.5, file4.py: 0.7

        assert len(results) == 3
        paths = [r["path"] for r in results]
        assert "file1.py" in paths
        assert "file2.py" in paths
        assert "file4.py" in paths

        # Verify sorting by score (descending)
        scores = [r["score"] for r in results]
        assert scores[0] >= scores[1] >= scores[2]

    @patch("app.agents.context_strategist.search_hybrid")
    def test_retrieve_empty_search_results(self, mock_search_hybrid):
        mock_client = MagicMock()
        mock_client._call_api.return_value = json.dumps(["expanded1"])
        strategist = ContextStrategist(client=mock_client)

        mock_search_hybrid.return_value = []

        results = strategist.retrieve("test prompt")
        assert results == []

    @patch("app.agents.context_strategist.search_hybrid")
    def test_retrieve_no_expanded_queries(self, mock_search_hybrid):
        mock_client = MagicMock()
        mock_client._call_api.return_value = "[]"
        strategist = ContextStrategist(client=mock_client)

        mock_search_hybrid.return_value = [{"path": "file1.py", "score": 1.0}]

        results = strategist.retrieve("test prompt")
        assert len(results) == 1
        assert results[0]["path"] == "file1.py"
        assert results[0]["score"] == 1.5  # Boost applied
