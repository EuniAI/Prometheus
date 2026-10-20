import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Annotated

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Implementation
from pydantic import BaseModel, Field
from tavily import InvalidAPIKeyError, TavilyClient, UsageLimitExceededError

from prometheus.configuration.config import settings
from prometheus.exceptions.web_search_tool_exception import WebSearchToolException


@dataclass
class ToolSpec:
    description: str
    input_schema: type


class WebSearchInput(BaseModel):
    """Parameters shared by the web search providers."""

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
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

        tavily_api_key = settings.TAVILY_API_KEY
        provider = settings.WEB_SEARCH_PROVIDER
        self.provider = (
            ("tavily" if tavily_api_key else "parallel") if provider == "auto" else provider
        )
        self.timeout = settings.WEB_SEARCH_TIMEOUT
        if self.provider != "tavily" or not tavily_api_key:
            tavily_client = None
        else:
            tavily_client = TavilyClient(api_key=tavily_api_key)
        self.tavily_client = tavily_client

    def web_search(
        self,
        query: str,
        max_results: int | None = None,
        include_domains=None,
        exclude_domains: list[str] | None = None,
    ) -> str:
        """Search the web for technical information to aid in bug analysis and resolution.

        Args:
            query: Search query string.
            max_results: Tavily result limit (default: 5); Parallel uses server settings.
            include_domains: Tavily domains to include; unsupported on Parallel.
            exclude_domains: Tavily domains to exclude; unsupported on Parallel.

        Returns:
            Formatted search results as a string.
        """
        if self.provider == "parallel":
            return asyncio.run(
                self.aweb_search(query, max_results, include_domains, exclude_domains)
            )
        if self.provider == "disabled":
            raise WebSearchToolException("Web search is disabled")
        if self.tavily_client is None:
            raise WebSearchToolException("Tavily requires PROMETHEUS_TAVILY_API_KEY")

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

        self._logger.debug(f"Query: {query}")

        # Call the Tavily API
        try:
            response = self.tavily_client.search(
                query=query,
                max_results=5 if max_results is None else max_results,
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

    async def aweb_search(
        self,
        query: str,
        max_results: int | None = None,
        include_domains=None,
        exclude_domains: list[str] | None = None,
    ) -> str:
        """Search asynchronously, allowing Parallel requests to be cancelled."""
        if self.provider != "parallel":
            return await asyncio.to_thread(
                self.web_search, query, max_results, include_domains, exclude_domains
            )
        if max_results is not None or include_domains or exclude_domains:
            raise WebSearchToolException(
                "Parallel uses server-managed search settings. Select the tavily provider "
                "to use domain filters or custom result limits."
            )
        try:
            return await asyncio.wait_for(self._parallel_search(query), timeout=self.timeout)
        except TimeoutError:
            raise WebSearchToolException("Parallel search timed out") from None
        except WebSearchToolException:
            raise
        except Exception:  # noqa: BLE001 - sanitize SDK exceptions before model consumption.
            # SDK transport errors can contain request details. Keep the public error concise.
            raise WebSearchToolException("Parallel Search MCP request failed") from None

    async def _parallel_search(self, query: str) -> str:
        # Each call owns and closes its transport. Do not attach a process/client-wide
        # conversation ID: analyzer instances are reused across independent issue runs.
        headers = {"User-Agent": "Prometheus/1.3 (+https://github.com/EuniAI/Prometheus)"}
        async with (
            streamablehttp_client("https://search.parallel.ai/mcp", headers=headers) as (
                read,
                write,
                _,
            ),
            ClientSession(
                read, write, client_info=Implementation(name="Prometheus", version="1.3")
            ) as session,
        ):
            await session.initialize()
            result = await session.call_tool(
                "web_search", {"objective": query, "search_queries": [query]}
            )
        text = "\n".join(block.text for block in result.content if block.type == "text")
        if result.isError:
            raise WebSearchToolException(f"Parallel Search MCP returned an error: {text}")
        if not text.strip():
            raise WebSearchToolException("Parallel Search MCP returned no text results")
        return text
