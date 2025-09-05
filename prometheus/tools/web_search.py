from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, Field
from tavily import InvalidAPIKeyError, TavilyClient, UsageLimitExceededError

from prometheus.configuration.config import settings
from prometheus.exceptions.web_search_tool_exception import WebSearchToolException
from prometheus.utils.logger_manager import get_logger


@dataclass
class ToolSpec:
    description: str
    input_schema: type


class WebSearchInput(BaseModel):
    """Base parameters for Tavily search."""

    query: Annotated[str, Field(description="Search query")]


def format_results(response: dict) -> str:
    """Format Tavily search results into a readable string."""
    output = []

    # Add domain filter information if present
    if response.get("included_domains") or response.get("excluded_domains"):
        filters = []
        if response.get("included_domains"):
            filters.append(f"Including domains: {', '.join(response['included_domains'])}")
        if response.get("excluded_domains"):
            filters.append(f"Excluding domains: {', '.join(response['excluded_domains'])}")
        output.append("Search Filters:")
        output.extend(filters)
        output.append("")  # Empty line for separation

    if response.get("answer"):
        output.append(f"Answer: {response['answer']}")
        output.append("\nSources:")
        # Add immediate source references for the answer
        for result in response["results"]:
            output.append(f"- {result['title']}: {result['url']}")
        output.append("")  # Empty line for separation

    output.append("Detailed Results:")
    for result in response["results"]:
        output.append(f"\nTitle: {result['title']}")
        output.append(f"URL: {result['url']}")
        output.append(f"Content: {result['content']}")
        if result.get("published_date"):
            output.append(f"Published: {result['published_date']}")

    return "\n".join(output)


class WebSearchTool:
    """Tool class for web search functionality."""

    web_search_spec = ToolSpec(
        description="""\
        Searches the web for technical information to aid in bug analysis and resolution. 
        Use this when you need external context, such as: 
        1. Looking up unfamiliar error messages, exceptions, or stack traces. 
        2. Finding official documentation or usage examples for a specific library, framework, or API. 
        3. Searching for known bugs, common pitfalls, or compatibility issues related to a software version. 
        4. Learning the best practices or design patterns for fixing a class of vulnerability (e.g., SQL injection, XSS). 
        
        Queries should be specific and include relevant keywords like library names, version numbers, and error codes.
        """,
        input_schema=WebSearchInput,
    )

    def __init__(self):
        """Initialize the web search tool."""
        # Load environment variables from .env file
        self._logger = get_logger(__name__)
        self.tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    def web_search(
        self,
        query: str,
        max_results: int = 5,
        include_domains=None,
        exclude_domains: list[str] = None,
    ) -> str:
        """Search the web for technical information to aid in bug analysis and resolution.

        Args:
            query: Search query string.
            max_results: Maximum number of results to return (default: 5).
            include_domains: List of domains to include in search.
            exclude_domains: List of domains to exclude from search.

        Returns:
            Formatted search results as a string.
        """
        # Set default include domains if not provided
        if include_domains is None:
            include_domains = [
                "stackoverflow.com",
                "github.com",
                "developer.mozilla.org",
                "learn.microsoft.com",
                "docs.python.org",
                "pydantic.dev",
                "pypi.org",
                "readthedocs.org",
            ]

        # Call the Tavily API
        try:
            response = self.tavily_client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                include_answer=True,
                include_domains=include_domains or [],  # Convert None to an empty list
                exclude_domains=exclude_domains or [],  # Convert None to an empty list
            )
        except InvalidAPIKeyError:
            raise WebSearchToolException("Invalid Tavily API key")
        except UsageLimitExceededError:
            raise WebSearchToolException("Usage limit exceeded")
        except Exception as e:
            raise WebSearchToolException(f"An error occurred: {str(e)}")

        # Format and return the results
        format_response = format_results(response)
        self._logger.info(f"web_search format_response: {format_response}")
        return format_response
