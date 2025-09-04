import json
from dataclasses import dataclass
from typing import Annotated, Optional

import aiohttp
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from prometheus.app.services.llm_service import get_model
from prometheus.configuration.config import settings
from prometheus.utils.logger_manager import get_logger

logger = get_logger(__name__)


@dataclass
class MCPToolSpec:
    description: str
    input_schema: type


model = get_model(
    "gpt-4o-mini",
    openai_format_api_key=settings.get("OPENAI_API_KEY", None),
    openai_format_base_url=settings.get("OPENAI_BASE_URL", None),
    anthropic_api_key=None,
    gemini_api_key=None,
    temperature=0.0,
    max_output_tokens=15000,
)


# Initialize MCP server
mcp = FastMCP("WebSearchTool")

# Get Tavily API key
tavily_api_key = settings.get("TAVILY_API_KEY", None)
if tavily_api_key is None:
    logger.warning("Tavily API key is not set")

# MCP server URL
TAVILY_SERVER_URL = f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api_key}"


class WebSearchInput(BaseModel):
    """Input parameters for web search."""

    query: Annotated[str, Field(description="Search query string")]
    max_results: Annotated[int, Field(description="Maximum number of results", default=5)]
    include_domains: Annotated[
        Optional[list[str]], Field(description="List of domains to include", default=None)
    ]
    exclude_domains: Annotated[
        Optional[list[str]], Field(description="List of domains to exclude", default=None)
    ]


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

    # Add answer if present
    if response.get("answer"):
        output.append(f"Answer: {response['answer']}")
        output.append("\nSources:")
        # Add immediate source references for the answer
        for result in response.get("results", []):
            output.append(f"- {result.get('title', 'No title')}: {result.get('url', 'No URL')}")
        output.append("")  # Empty line for separation

    # Add detailed results
    output.append("Detailed Results:")
    for result in response.get("results", []):
        output.append(f"\nTitle: {result.get('title', 'No title')}")
        output.append(f"URL: {result.get('url', 'No URL')}")
        output.append(f"Content: {result.get('content', 'No content')}")
        if result.get("published_date"):
            output.append(f"Published: {result['published_date']}")

    return "\n".join(output)


class MCPWebSearchTool:
    """Web search tool class."""

    web_search_spec = MCPToolSpec(
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


@mcp.tool()
async def web_search(
    query: str,
    max_results: int = 5,
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> str:
    """\
        Searches the web for technical information to aid in bug analysis and resolution. 
        Use this when you need external context, such as: 
        1. Looking up unfamiliar error messages, exceptions, or stack traces. 
        2. Finding official documentation or usage examples for a specific library, framework, or API. 
        3. Searching for known bugs, common pitfalls, or compatibility issues related to a software version. 
        4. Learning the best practices or design patterns for fixing a class of vulnerability (e.g., SQL injection, XSS). 
        
        Queries should be specific and include relevant keywords like library names, version numbers, and error codes.
            

    Args:
        query: Search query string
        max_results: Maximum number of results (default: 5)
        include_domains: List of domains to include (default: technical documentation sites)
        exclude_domains: List of domains to exclude
    """

    # Check if API key is available
    if tavily_api_key is None:
        return "Error: Tavily API key is not set"

    # Default technical search domains
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
            "docs.djangoproject.com",
            "flask.palletsprojects.com",
            "fastapi.tiangolo.com",
        ]

    # Build request payload
    payload = {
        "query": query,
        "max_results": max_results,
        "include_domains": include_domains or [],
        "exclude_domains": exclude_domains or [],
    }

    try:
        logger.info(f"Executing web search, query: {query}")

        # Use aiohttp to send HTTP request to MCP server
        async with aiohttp.ClientSession() as session:
            async with session.post(TAVILY_SERVER_URL, json=payload) as resp:
                if resp.status != 200:
                    error_msg = f"HTTP error {resp.status}: {await resp.text()}"
                    logger.error(error_msg)
                    return error_msg

                data = await resp.json()

        # Format response
        formatted_response = format_results(data)
        logger.info(f"Web search completed, returned {len(data.get('results', []))} results")

        return formatted_response

    except aiohttp.ClientError as e:
        error_msg = f"Network request error: {str(e)}"
        logger.error(error_msg)
        return error_msg
    except json.JSONDecodeError as e:
        error_msg = f"JSON parsing error: {str(e)}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f"Error occurred during search: {str(e)}"
        logger.error(error_msg)
        return error_msg


def run_mcp_server():
    """Run MCP server."""
    logger.info("Starting MCP Web search server...")
    mcp.run()


if __name__ == "__main__":
    # # Load environment variables
    # load_dotenv()

    # # Get Tavily API key
    # tavily_api_key = settings.get("TAVILY_API_KEY", None)
    # if tavily_api_key is None:
    #     logger.warning("Tavily API key is not set")
    # TAVILY_SERVER_URL = f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api_key}"

    # Run server
    run_mcp_server()
