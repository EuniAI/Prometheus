import logging
import threading
from typing import Any, Dict, List

import requests

from prometheus.configuration.config import settings
from prometheus.models.context import Context
from prometheus.models.query import Query


class AthenaMemoryClient:
    """Client for interacting with Athena semantic memory service."""

    def __init__(
        self,
        base_url: str,
    ):
        """
        Initialize Athena memory client.

        Args:
            base_url: Base URL of the Athena service
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = 30
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def store_memory(
        self,
        repository_id: int,
        essential_query: str,
        extra_requirements: str,
        purpose: str,
        contexts: List[Context],
    ) -> dict[str, Any]:
        """
        Store content in semantic memory.

        Args:
            repository_id: Repository identifier
            essential_query: The main query
            extra_requirements: Optional extra requirements
            purpose: Optional purpose description
            contexts: List of Context objects to store

        Returns:
            Response from Athena service

        Raises:
            requests.RequestException: If the request fails
        """
        url = f"{self.base_url}/semantic-memory/store/"

        payload = {
            "repository_id": repository_id,
            "query": {
                "essential_query": essential_query,
                "extra_requirements": extra_requirements,
                "purpose": purpose,
            },
            "contexts": contexts,
        }

        self._logger.debug(f"Storing memory for repository {repository_id}")
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            self._logger.error(f"Failed to store memory for repository {repository_id}: {e}")
            raise
        result = response.json()
        self._logger.debug(f"Successfully stored memory: {result}")
        return result

    def retrieve_memory(
        self,
        repository_id: int,
        query: Query,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve content from semantic memory using a query.

        Args:
            repository_id: Repository identifier
            query: Query object with essential_query, extra_requirements, and purpose

        Returns:
            Response from Athena service containing retrieved memories

        Raises:
            requests.RequestException: If the request fails
        """
        url = f"{self.base_url}/semantic-memory/retrieve/{repository_id}/"

        params = {
            "essential_query": query.essential_query,
            "extra_requirements": query.extra_requirements or "",
            "purpose": query.purpose or "",
        }

        self._logger.debug(
            f"Retrieving memory for repository {repository_id} with query: {query.essential_query}"
        )

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            self._logger.error(f"Failed to retrieve memory for repository {repository_id}: {e}")
            raise

        result = response.json()
        self._logger.debug(f"Successfully retrieved {len(result.get('data', []))} memories")
        return result["data"]

    def delete_repository_memory(self, repository_id: int) -> dict[str, Any]:
        """
        Delete all memories for a repository.

        Args:
            repository_id: Repository identifier

        Returns:
            Response from Athena service

        Raises:
            requests.RequestException: If the request fails
        """
        url = f"{self.base_url}/semantic-memory/{repository_id}/"

        self._logger.debug(f"Deleting memory for repository {repository_id}")
        try:
            response = requests.delete(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            self._logger.error(f"Failed to delete repository memory {repository_id}: {e}")
            raise
        result = response.json()
        self._logger.debug(f"Successfully deleted repository memory: {result}")
        return result


# Global instance with settings from config
athena_client = AthenaMemoryClient(
    base_url=settings.ATHENA_BASE_URL,
)


def store_memory(
    repository_id: int,
    essential_query: str,
    extra_requirements: str,
    purpose: str,
    contexts: List[Context],
) -> dict[str, Any]:
    """
    Store contexts to semantic memory for a repository.

    Args:
        repository_id: Repository identifier
        essential_query: The main query that was used to retrieve these contexts
        extra_requirements: Optional extra requirements for the query
        purpose: Optional purpose description
        contexts: List of Context objects to store

    Returns:
        Response from Athena service

    Raises:
        requests.RequestException: If the request fails
    """
    return athena_client.store_memory(
        repository_id=repository_id,
        essential_query=essential_query,
        extra_requirements=extra_requirements,
        purpose=purpose,
        contexts=contexts,
    )


def retrieve_memory(
    repository_id: int,
    query: Query,
) -> List[Dict[str, Any]]:
    """
    Retrieve contexts from semantic memory using a query.

    Args:
        repository_id: Repository identifier
        query: Query object with essential_query, extra_requirements, and purpose

    Returns:
        Response from Athena service containing retrieved contexts

    Raises:
        requests.RequestException: If the request fails
    """
    return athena_client.retrieve_memory(repository_id=repository_id, query=query)


def delete_repository_memory(repository_id: int) -> dict[str, Any]:
    """
    Delete all memories for a repository.

    Args:
        repository_id: Repository identifier

    Returns:
        Response from Athena service

    Raises:
        requests.RequestException: If the request fails
    """
    return athena_client.delete_repository_memory(repository_id=repository_id)
