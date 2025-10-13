from unittest.mock import MagicMock, patch

import pytest
from tavily import InvalidAPIKeyError, UsageLimitExceededError

from prometheus.exceptions.web_search_tool_exception import WebSearchToolException
from prometheus.tools.web_search import WebSearchInput, WebSearchTool, format_results


class TestFormatResults:
    """Test suite for format_results function."""

    def test_format_results_basic(self):
        """Test basic formatting of search results without answer."""
        response = {
            "results": [
                {
                    "title": "How to fix Python import error",
                    "url": "https://stackoverflow.com/questions/12345",
                    "content": "This is how you fix import errors in Python...",
                },
                {
                    "title": "Python Documentation",
                    "url": "https://docs.python.org/3/",
                    "content": "Official Python documentation...",
                },
            ]
        }

        result = format_results(response)

        assert "Detailed Results:" in result
        assert "How to fix Python import error" in result
        assert "https://stackoverflow.com/questions/12345" in result
        assert "This is how you fix import errors in Python..." in result
        assert "Python Documentation" in result
        assert "https://docs.python.org/3/" in result

    def test_format_results_with_answer(self):
        """Test formatting with answer included."""
        response = {
            "answer": "To fix import errors, check your PYTHONPATH and ensure modules are installed.",
            "results": [
                {
                    "title": "Python Import Guide",
                    "url": "https://docs.python.org/import",
                    "content": "Guide to Python imports...",
                },
            ],
        }

        result = format_results(response)

        assert "Answer:" in result
        assert "To fix import errors" in result
        assert "Sources:" in result
        assert "Python Import Guide" in result
        assert "https://docs.python.org/import" in result
        assert "Detailed Results:" in result

    def test_format_results_with_published_date(self):
        """Test formatting with published date."""
        response = {
            "results": [
                {
                    "title": "Article Title",
                    "url": "https://example.com/article",
                    "content": "Article content...",
                    "published_date": "2024-01-15",
                },
            ]
        }

        result = format_results(response)

        assert "Published: 2024-01-15" in result

    def test_format_results_with_included_domains(self):
        """Test formatting with included domains filter."""
        response = {
            "included_domains": ["stackoverflow.com", "github.com"],
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://stackoverflow.com/test",
                    "content": "Test content",
                },
            ],
        }

        result = format_results(response)

        assert "Search Filters:" in result
        assert "Including domains: stackoverflow.com, github.com" in result

    def test_format_results_with_excluded_domains(self):
        """Test formatting with excluded domains filter."""
        response = {
            "excluded_domains": ["pinterest.com", "reddit.com"],
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com/test",
                    "content": "Test content",
                },
            ],
        }

        result = format_results(response)

        assert "Search Filters:" in result
        assert "Excluding domains: pinterest.com, reddit.com" in result

    def test_format_results_with_both_domain_filters(self):
        """Test formatting with both included and excluded domains."""
        response = {
            "included_domains": ["stackoverflow.com"],
            "excluded_domains": ["pinterest.com"],
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://stackoverflow.com/test",
                    "content": "Test content",
                },
            ],
        }

        result = format_results(response)

        assert "Including domains: stackoverflow.com" in result
        assert "Excluding domains: pinterest.com" in result

    def test_format_results_empty(self):
        """Test formatting with no results."""
        response = {"results": []}

        result = format_results(response)

        assert "Detailed Results:" in result
        # Should not contain any result-specific content
        assert "Title:" not in result
        assert "URL:" not in result

    def test_format_results_multiple_results(self):
        """Test formatting with multiple results."""
        response = {
            "results": [
                {
                    "title": f"Result {i}",
                    "url": f"https://example.com/{i}",
                    "content": f"Content {i}",
                }
                for i in range(5)
            ]
        }

        result = format_results(response)

        for i in range(5):
            assert f"Result {i}" in result
            assert f"https://example.com/{i}" in result
            assert f"Content {i}" in result

    def test_format_results_special_characters(self):
        """Test formatting with special characters in content."""
        response = {
            "results": [
                {
                    "title": "Special chars: @#$%^&*()",
                    "url": "https://example.com/special",
                    "content": "Content with 中文 and emojis 🚀",
                },
            ]
        }

        result = format_results(response)

        assert "@#$%^&*()" in result
        assert "中文" in result
        assert "🚀" in result


class TestWebSearchInput:
    """Test suite for WebSearchInput model."""

    def test_web_search_input_valid(self):
        """Test valid WebSearchInput creation."""
        input_data = WebSearchInput(query="Python import error")
        assert input_data.query == "Python import error"

    def test_web_search_input_empty_query(self):
        """Test WebSearchInput with empty query."""
        input_data = WebSearchInput(query="")
        assert input_data.query == ""

    def test_web_search_input_long_query(self):
        """Test WebSearchInput with long query."""
        long_query = "A" * 1000
        input_data = WebSearchInput(query=long_query)
        assert input_data.query == long_query


class TestWebSearchTool:
    """Test suite for WebSearchTool class."""

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_init_with_api_key(self, mock_tavily_client, mock_settings):
        """Test WebSearchTool initialization with API key."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        tool = WebSearchTool()

        mock_tavily_client.assert_called_once_with(api_key="test_api_key")
        assert tool.tavily_client is not None

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_init_without_api_key(self, mock_tavily_client, mock_settings):
        """Test WebSearchTool initialization without API key."""
        mock_settings.TAVILY_API_KEY = None

        tool = WebSearchTool()

        mock_tavily_client.assert_not_called()
        assert tool.tavily_client is None

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_success(self, mock_tavily_client, mock_settings):
        """Test successful web search."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        # Setup mock client
        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance

        mock_response = {
            "answer": "Test answer",
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://stackoverflow.com/test",
                    "content": "Test content",
                }
            ],
        }
        mock_client_instance.search.return_value = mock_response

        # Create tool and search
        tool = WebSearchTool()
        result = tool.web_search(query="Python import error")

        # Verify search was called with correct parameters
        mock_client_instance.search.assert_called_once()
        call_kwargs = mock_client_instance.search.call_args[1]
        assert call_kwargs["query"] == "Python import error"
        assert call_kwargs["max_results"] == 5
        assert call_kwargs["search_depth"] == "advanced"
        assert call_kwargs["include_answer"] is True
        assert "stackoverflow.com" in call_kwargs["include_domains"]
        assert "github.com" in call_kwargs["include_domains"]

        # Verify result formatting
        assert "Test answer" in result
        assert "Test Result" in result

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_with_custom_params(self, mock_tavily_client, mock_settings):
        """Test web search with custom parameters."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance

        mock_response = {
            "results": [
                {
                    "title": "Custom Result",
                    "url": "https://example.com/test",
                    "content": "Custom content",
                }
            ]
        }
        mock_client_instance.search.return_value = mock_response

        tool = WebSearchTool()
        tool.web_search(
            query="test query",
            max_results=10,
            include_domains=["custom-domain.com"],
            exclude_domains=["excluded.com"],
        )

        # Verify custom parameters were used
        call_kwargs = mock_client_instance.search.call_args[1]
        assert call_kwargs["max_results"] == 10
        assert call_kwargs["include_domains"] == ["custom-domain.com"]
        assert call_kwargs["exclude_domains"] == ["excluded.com"]

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_default_domains(self, mock_tavily_client, mock_settings):
        """Test web search uses default domains when not specified."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance

        mock_response = {"results": []}
        mock_client_instance.search.return_value = mock_response

        tool = WebSearchTool()
        tool.web_search(query="test")

        call_kwargs = mock_client_instance.search.call_args[1]
        default_domains = call_kwargs["include_domains"]

        # Verify default domains are present
        assert "stackoverflow.com" in default_domains
        assert "github.com" in default_domains
        assert "developer.mozilla.org" in default_domains
        assert "learn.microsoft.com" in default_domains
        assert "docs.python.org" in default_domains
        assert "pydantic.dev" in default_domains
        assert "pypi.org" in default_domains
        assert "readthedocs.org" in default_domains

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_invalid_api_key(self, mock_tavily_client, mock_settings):
        """Test web search with invalid API key."""
        mock_settings.TAVILY_API_KEY = "invalid_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance
        mock_client_instance.search.side_effect = InvalidAPIKeyError("Invalid API key")

        tool = WebSearchTool()

        with pytest.raises(WebSearchToolException) as exc_info:
            tool.web_search(query="test")

        assert "Invalid Tavily API key" in str(exc_info.value)

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_usage_limit_exceeded(self, mock_tavily_client, mock_settings):
        """Test web search when usage limit is exceeded."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance
        mock_client_instance.search.side_effect = UsageLimitExceededError("Limit exceeded")

        tool = WebSearchTool()

        with pytest.raises(WebSearchToolException) as exc_info:
            tool.web_search(query="test")

        assert "Usage limit exceeded" in str(exc_info.value)

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_generic_exception(self, mock_tavily_client, mock_settings):
        """Test web search with generic exception."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance
        mock_client_instance.search.side_effect = Exception("Network error")

        tool = WebSearchTool()

        with pytest.raises(WebSearchToolException) as exc_info:
            tool.web_search(query="test")

        assert "An error occurred: Network error" in str(exc_info.value)

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_empty_query(self, mock_tavily_client, mock_settings):
        """Test web search with empty query."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance

        mock_response = {"results": []}
        mock_client_instance.search.return_value = mock_response

        tool = WebSearchTool()
        result = tool.web_search(query="")

        # Should still call search even with empty query
        mock_client_instance.search.assert_called_once()
        assert "Detailed Results:" in result

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_with_none_exclude_domains(self, mock_tavily_client, mock_settings):
        """Test web search with None exclude_domains."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance

        mock_response = {"results": []}
        mock_client_instance.search.return_value = mock_response

        tool = WebSearchTool()
        tool.web_search(query="test", exclude_domains=None)

        # Verify None is converted to empty list
        call_kwargs = mock_client_instance.search.call_args[1]
        assert call_kwargs["exclude_domains"] == []

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_complex_query(self, mock_tavily_client, mock_settings):
        """Test web search with complex query containing special characters."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance

        mock_response = {
            "results": [
                {
                    "title": "Result",
                    "url": "https://example.com",
                    "content": "Content",
                }
            ]
        }
        mock_client_instance.search.return_value = mock_response

        tool = WebSearchTool()
        complex_query = 'Python "ModuleNotFoundError" 中文 @#$%'
        tool.web_search(query=complex_query)

        # Verify complex query is passed correctly
        call_kwargs = mock_client_instance.search.call_args[1]
        assert call_kwargs["query"] == complex_query


class TestToolSpec:
    """Test suite for ToolSpec and tool configuration."""

    def test_web_search_tool_spec_exists(self):
        """Test that web_search_spec is properly defined."""
        assert hasattr(WebSearchTool, "web_search_spec")
        spec = WebSearchTool.web_search_spec

        assert spec.description is not None
        assert len(spec.description) > 0
        assert spec.input_schema == WebSearchInput

    def test_web_search_tool_spec_description(self):
        """Test that web_search_spec description contains expected keywords."""
        spec = WebSearchTool.web_search_spec

        # Verify description mentions key use cases
        assert "bug analysis" in spec.description
        assert "error messages" in spec.description
        assert "documentation" in spec.description
        assert "library" in spec.description


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_max_results_boundary(self, mock_tavily_client, mock_settings):
        """Test web search with boundary values for max_results."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance
        mock_response = {"results": []}
        mock_client_instance.search.return_value = mock_response

        tool = WebSearchTool()

        # Test with 0
        tool.web_search(query="test", max_results=0)
        assert mock_client_instance.search.call_args[1]["max_results"] == 0

        # Test with large number
        tool.web_search(query="test", max_results=100)
        assert mock_client_instance.search.call_args[1]["max_results"] == 100

    def test_format_results_missing_optional_fields(self):
        """Test formatting when optional fields are missing."""
        response = {
            "results": [
                {
                    "title": "Title",
                    "url": "https://example.com",
                    "content": "Content",
                    # No published_date
                }
            ]
            # No answer, included_domains, excluded_domains
        }

        result = format_results(response)

        # Should not fail and should not include missing fields
        assert "Published:" not in result
        assert "Answer:" not in result
        assert "Search Filters:" not in result

    @patch("prometheus.tools.web_search.settings")
    @patch("prometheus.tools.web_search.TavilyClient")
    def test_web_search_with_empty_domains_lists(self, mock_tavily_client, mock_settings):
        """Test web search with empty domain lists."""
        mock_settings.TAVILY_API_KEY = "test_api_key"

        mock_client_instance = MagicMock()
        mock_tavily_client.return_value = mock_client_instance
        mock_response = {"results": []}
        mock_client_instance.search.return_value = mock_response

        tool = WebSearchTool()
        tool.web_search(query="test", include_domains=[], exclude_domains=[])

        call_kwargs = mock_client_instance.search.call_args[1]
        assert call_kwargs["include_domains"] == []
        assert call_kwargs["exclude_domains"] == []

    def test_format_results_with_long_content(self):
        """Test formatting with very long content."""
        long_content = "A" * 10000
        response = {
            "results": [
                {
                    "title": "Long Content Result",
                    "url": "https://example.com",
                    "content": long_content,
                }
            ]
        }

        result = format_results(response)

        # Should handle long content without errors
        assert long_content in result
        assert "Long Content Result" in result
