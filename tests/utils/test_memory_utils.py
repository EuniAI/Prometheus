from unittest.mock import MagicMock, patch

import pytest
import requests

from prometheus.models.context import Context
from prometheus.models.query import Query
from prometheus.utils.memory_utils import AthenaMemoryClient


@pytest.fixture
def athena_client():
    """Create an AthenaMemoryClient instance for testing."""
    return AthenaMemoryClient(base_url="http://test-athena-service.com")


@pytest.fixture
def sample_contexts():
    """Create sample Context objects for testing."""
    return [
        Context(
            relative_path="src/main.py",
            content="def main():\n    print('Hello')",
            start_line_number=1,
            end_line_number=2,
        ),
        Context(
            relative_path="src/utils.py",
            content="def helper():\n    return True",
            start_line_number=10,
            end_line_number=11,
        ),
    ]


@pytest.fixture
def sample_query():
    """Create a sample Query object for testing."""
    return Query(
        essential_query="How to implement authentication?",
        extra_requirements="Using JWT tokens",
        purpose="Feature implementation",
    )


class TestAthenaMemoryClient:
    """Test suite for AthenaMemoryClient class."""

    def test_init(self):
        """Test AthenaMemoryClient initialization."""
        client = AthenaMemoryClient(base_url="http://example.com/")
        assert client.base_url == "http://example.com"
        assert client.timeout == 30

    def test_init_strips_trailing_slash(self):
        """Test that trailing slashes are removed from base_url."""
        client = AthenaMemoryClient(base_url="http://example.com///")
        assert client.base_url == "http://example.com"

    @patch("prometheus.utils.memory_utils.requests.post")
    def test_store_memory_success(self, mock_post, athena_client, sample_contexts):
        """Test successful memory storage."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "memory_id": "123"}
        mock_post.return_value = mock_response

        # Call the method
        result = athena_client.store_memory(
            repository_id=42,
            essential_query="How to use async?",
            extra_requirements="Python 3.11",
            purpose="Learning",
            contexts=sample_contexts,
        )

        # Assertions
        assert result == {"status": "success", "memory_id": "123"}
        mock_post.assert_called_once()

        # Verify the call arguments
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://test-athena-service.com/semantic-memory/store/"
        assert call_args[1]["timeout"] == 30

        # Verify payload structure
        payload = call_args[1]["json"]
        assert payload["repository_id"] == 42
        assert payload["query"]["essential_query"] == "How to use async?"
        assert payload["query"]["extra_requirements"] == "Python 3.11"
        assert payload["query"]["purpose"] == "Learning"
        assert len(payload["contexts"]) == 2
        assert payload["contexts"][0]["relative_path"] == "src/main.py"

    @patch("prometheus.utils.memory_utils.requests.post")
    def test_store_memory_request_exception(self, mock_post, athena_client, sample_contexts):
        """Test store_memory raises RequestException on failure."""
        # Setup mock to raise an exception
        mock_post.side_effect = requests.RequestException("Connection error")

        # Verify exception is raised
        with pytest.raises(requests.RequestException) as exc_info:
            athena_client.store_memory(
                repository_id=42,
                essential_query="test query",
                extra_requirements="",
                purpose="",
                contexts=sample_contexts,
            )

        assert "Connection error" in str(exc_info.value)

    @patch("prometheus.utils.memory_utils.requests.post")
    def test_store_memory_http_error(self, mock_post, athena_client, sample_contexts):
        """Test store_memory handles HTTP errors."""
        # Setup mock response with error status
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_post.return_value = mock_response

        # Verify exception is raised
        with pytest.raises(requests.HTTPError):
            athena_client.store_memory(
                repository_id=42,
                essential_query="test query",
                extra_requirements="",
                purpose="",
                contexts=sample_contexts,
            )

    @patch("prometheus.utils.memory_utils.requests.get")
    def test_retrieve_memory_success(self, mock_get, athena_client, sample_query):
        """Test successful memory retrieval."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"content": "Authentication code snippet 1"},
                {"content": "Authentication code snippet 2"},
            ]
        }
        mock_get.return_value = mock_response

        # Call the method
        result = athena_client.retrieve_memory(repository_id=42, query=sample_query)

        # Assertions
        assert len(result) == 2
        assert result[0]["content"] == "Authentication code snippet 1"
        mock_get.assert_called_once()

        # Verify the call arguments
        call_args = mock_get.call_args
        assert call_args[0][0] == "http://test-athena-service.com/semantic-memory/retrieve/42/"
        assert call_args[1]["timeout"] == 30

        # Verify query parameters
        params = call_args[1]["params"]
        assert params["essential_query"] == "How to implement authentication?"
        assert params["extra_requirements"] == "Using JWT tokens"
        assert params["purpose"] == "Feature implementation"

    @patch("prometheus.utils.memory_utils.requests.get")
    def test_retrieve_memory_with_optional_fields(self, mock_get, athena_client):
        """Test memory retrieval with empty optional query fields."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        # Create query with empty optional fields
        query = Query(essential_query="test query", extra_requirements="", purpose="")

        # Call the method
        result = athena_client.retrieve_memory(repository_id=42, query=query)

        # Verify empty strings are passed correctly
        call_args = mock_get.call_args
        params = call_args[1]["params"]
        assert params["extra_requirements"] == ""
        assert params["purpose"] == ""
        assert result == []

    @patch("prometheus.utils.memory_utils.requests.get")
    def test_retrieve_memory_request_exception(self, mock_get, athena_client, sample_query):
        """Test retrieve_memory raises RequestException on failure."""
        # Setup mock to raise an exception
        mock_get.side_effect = requests.RequestException("Timeout error")

        # Verify exception is raised
        with pytest.raises(requests.RequestException) as exc_info:
            athena_client.retrieve_memory(repository_id=42, query=sample_query)

        assert "Timeout error" in str(exc_info.value)

    @patch("prometheus.utils.memory_utils.requests.get")
    def test_retrieve_memory_http_error(self, mock_get, athena_client, sample_query):
        """Test retrieve_memory handles HTTP errors."""
        # Setup mock response with error status
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = mock_response

        # Verify exception is raised
        with pytest.raises(requests.HTTPError):
            athena_client.retrieve_memory(repository_id=42, query=sample_query)

    @patch("prometheus.utils.memory_utils.requests.delete")
    def test_delete_repository_memory_success(self, mock_delete, athena_client):
        """Test successful repository memory deletion."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "deleted_count": 15}
        mock_delete.return_value = mock_response

        # Call the method
        result = athena_client.delete_repository_memory(repository_id=42)

        # Assertions
        assert result == {"status": "success", "deleted_count": 15}
        mock_delete.assert_called_once()

        # Verify the call arguments
        call_args = mock_delete.call_args
        assert call_args[0][0] == "http://test-athena-service.com/semantic-memory/42/"
        assert call_args[1]["timeout"] == 30

    @patch("prometheus.utils.memory_utils.requests.delete")
    def test_delete_repository_memory_request_exception(self, mock_delete, athena_client):
        """Test delete_repository_memory raises RequestException on failure."""
        # Setup mock to raise an exception
        mock_delete.side_effect = requests.RequestException("Network error")

        # Verify exception is raised
        with pytest.raises(requests.RequestException) as exc_info:
            athena_client.delete_repository_memory(repository_id=42)

        assert "Network error" in str(exc_info.value)

    @patch("prometheus.utils.memory_utils.requests.delete")
    def test_delete_repository_memory_http_error(self, mock_delete, athena_client):
        """Test delete_repository_memory handles HTTP errors."""
        # Setup mock response with error status
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_delete.return_value = mock_response

        # Verify exception is raised
        with pytest.raises(requests.HTTPError):
            athena_client.delete_repository_memory(repository_id=42)


class TestModuleLevelFunctions:
    """Test suite for module-level convenience functions."""

    @patch("prometheus.utils.memory_utils.athena_client.store_memory")
    def test_store_memory_function(self, mock_store, sample_contexts):
        """Test module-level store_memory function."""
        from prometheus.utils.memory_utils import store_memory

        # Setup mock
        mock_store.return_value = {"status": "success"}

        # Call the function
        result = store_memory(
            repository_id=123,
            essential_query="test query",
            extra_requirements="requirements",
            purpose="testing",
            contexts=sample_contexts,
        )

        # Verify it delegates to the client
        assert result == {"status": "success"}
        mock_store.assert_called_once_with(
            repository_id=123,
            essential_query="test query",
            extra_requirements="requirements",
            purpose="testing",
            contexts=sample_contexts,
        )

    @patch("prometheus.utils.memory_utils.athena_client.retrieve_memory")
    def test_retrieve_memory_function(self, mock_retrieve, sample_query):
        """Test module-level retrieve_memory function."""
        from prometheus.utils.memory_utils import retrieve_memory

        # Setup mock
        mock_retrieve.return_value = [{"content": "test"}]

        # Call the function
        result = retrieve_memory(repository_id=123, query=sample_query)

        # Verify it delegates to the client
        assert result == [{"content": "test"}]
        mock_retrieve.assert_called_once_with(repository_id=123, query=sample_query)

    @patch("prometheus.utils.memory_utils.athena_client.delete_repository_memory")
    def test_delete_repository_memory_function(self, mock_delete):
        """Test module-level delete_repository_memory function."""
        from prometheus.utils.memory_utils import delete_repository_memory

        # Setup mock
        mock_delete.return_value = {"status": "deleted"}

        # Call the function
        result = delete_repository_memory(repository_id=123)

        # Verify it delegates to the client
        assert result == {"status": "deleted"}
        mock_delete.assert_called_once_with(repository_id=123)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("prometheus.utils.memory_utils.requests.post")
    def test_store_memory_with_empty_contexts_list(self, mock_post, athena_client):
        """Test storing memory with empty contexts list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        result = athena_client.store_memory(
            repository_id=1,
            essential_query="test",
            extra_requirements="",
            purpose="",
            contexts=[],
        )

        # Verify empty list is handled
        payload = mock_post.call_args[1]["json"]
        assert payload["contexts"] == []
        assert result == {"status": "success"}

    @patch("prometheus.utils.memory_utils.requests.get")
    def test_retrieve_memory_empty_results(self, mock_get, athena_client):
        """Test retrieving memory when no results are found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response

        query = Query(
            essential_query="nonexistent query",
            extra_requirements="",
            purpose="",
        )

        result = athena_client.retrieve_memory(repository_id=999, query=query)

        assert result == []

    def test_context_serialization(self, sample_contexts):
        """Test that Context objects are properly serialized."""
        context = sample_contexts[0]
        serialized = context.model_dump()

        assert serialized["relative_path"] == "src/main.py"
        assert serialized["content"] == "def main():\n    print('Hello')"
        assert serialized["start_line_number"] == 1
        assert serialized["end_line_number"] == 2

    @patch("prometheus.utils.memory_utils.requests.post")
    def test_store_memory_with_special_characters(self, mock_post, athena_client):
        """Test storing memory with special characters in content."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        special_context = Context(
            relative_path="test/file.py",
            content="def test():\n    # Special chars: @#$%^&*(){}[]|\\<>?~`",
            start_line_number=1,
            end_line_number=2,
        )

        result = athena_client.store_memory(
            repository_id=1,
            essential_query="test with special chars: @#$%",
            extra_requirements="requirements with 中文",
            purpose="purpose with émojis 🚀",
            contexts=[special_context],
        )

        assert result == {"status": "success"}
        # Verify special characters are preserved in the payload
        payload = mock_post.call_args[1]["json"]
        assert "@#$%" in payload["query"]["essential_query"]
        assert "中文" in payload["query"]["extra_requirements"]
        assert "🚀" in payload["query"]["purpose"]
