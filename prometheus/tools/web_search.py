import os
import shutil
from pathlib import Path
from typing import Annotated
import json
import asyncio
from dataclasses import dataclass
from dynaconf.vendor.dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from tavily import TavilyClient, InvalidAPIKeyError, UsageLimitExceededError
from prometheus.configuration.config import settings
from prometheus.utils.logger_manager import get_logger
from langchain_mcp_adapters.client import MultiServerMCPClient

logger = get_logger(__name__)

@dataclass
class ToolSpec:
    description: str
    input_schema: type


tavily_api_key = settings.get("TAVILY_API_KEY", None)
if tavily_api_key is None:
    logger.warning("Tavily API key is not set")
    tavily_client = None
else:
    tavily_client = TavilyClient(api_key=tavily_api_key)


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
        input_schema=WebSearchInput
    )
    
    def __init__(self):
        """Initialize the web search tool."""
        self.tavily_client = tavily_client
    
    def web_search(self, query: str, max_results: int = 5, 
                   include_domains: list[str] = [
                       'stackoverflow.com', 
                       'github.com', 
                       'developer.mozilla.org', 
                       'learn.microsoft.com', 
                       'docs.python.org', 
                       'pydantic.dev',
                       'pypi.org',
                       'readthedocs.org',
                   ], 
                   exclude_domains: list[str] = None) -> str:
        """Search the web for technical information to aid in bug analysis and resolution.
        
        Args:
            query: Search query string.
            max_results: Maximum number of results to return (default: 5).
            include_domains: List of domains to include in search.
            exclude_domains: List of domains to exclude from search.
            
        Returns:
            Formatted search results as a string.
        """
        
        if tavily_client is None:
            raise RuntimeError("Tavily API key is not set")
        try:
            response = tavily_client.search(
                query=query,
                max_results=max_results,
                search_depth="advanced",
                include_answer=True,
                include_domains=include_domains or [],  # Convert None to empty list
                exclude_domains=exclude_domains or [],  # Convert None to empty list
            )
            format_response = format_results(response)
            self._logger.info(f"web_search format_response: {format_response}")
            return format_response
        except InvalidAPIKeyError: 
            raise ValueError("Invalid Tavily API key")
        except UsageLimitExceededError:
            raise RuntimeError("Usage limit exceeded")
        except Exception as e:
            raise RuntimeError(f"An error occurred: {str(e)}")

async def mcp_web_search():
    client = MultiServerMCPClient(
            {        
                "tavily_web_search": {
                    "transport": "streamable_http",
                    "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api_key}",
                }
            }
        )
        # 异步获取工具
    tools = await client.get_tools()
    return tools

if __name__ == "__main__":
    load_dotenv()
    tavily_api_key = os.getenv("PROMETHEUS_TAVILY_API_KEY")
    if tavily_api_key is None:
        logger.warning("Tavily API key is not set")
        tavily_client = None
    else:
        tavily_client = TavilyClient(api_key=tavily_api_key)

    print(web_search("What is the capital of France?"))