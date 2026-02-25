import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from prometheus.configuration.config import settings
from prometheus.exceptions.evermind_exception import EvermindException


class EvermindClient:
    """Client for interacting with the Evermind (EverMemOS) conversation memory service."""

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize Evermind memory client.

        Args:
            base_url: Base URL of the Evermind service (e.g. http://localhost:1995/api/v1)
            api_key: API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        self.timeout = 30
        self._logger = logging.getLogger(f"thread-{threading.get_ident()}.{__name__}")

    def retrieve_memories(self, repository_id: int, query: str, limit: int = 5) -> str:
        """
        Search for relevant past conversation memories for a repository.

        Args:
            repository_id: Repository identifier (used as user_id namespace)
            query: Natural language query (e.g. issue title + body)
            limit: Maximum number of memories to return

        Returns:
            Formatted string of retrieved memories, or empty string if none found

        Raises:
            EvermindException: If the request fails
        """
        url = f"{self.base_url}/memories/search"
        params = {
            "query": query,
            "user_id": f"repo_{repository_id}",
            "memory_types": ["episodic_memory"],
            "retrieve_method": "hybrid",
            "limit": limit,
            "offset": 0,
        }

        self._logger.debug(f"Retrieving memories for repository {repository_id}")
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            self._logger.error(f"Failed to retrieve memories for repository {repository_id}: {e}")
            raise EvermindException(str(e)) from e

        data = response.json()
        memories: List[Dict[str, Any]] = data.get("result", {}).get("memories", [])
        self._logger.info(f"Retrieved {len(memories)} memories for repository {repository_id}")

        if not memories:
            return ""

        lines = []
        for mem in memories:
            content = mem.get("content", "").strip()
            role = mem.get("role", "")
            if content:
                prefix = "[Past Issue]" if role == "user" else "[Past Resolution]"
                lines.append(f"{prefix} {content}")

        return "\n".join(lines)

    def store_conversation(
        self,
        repository_id: int,
        issue_title: str,
        issue_body: str,
        issue_response: str,
        edit_patch: Optional[str],
        issue_type: str,
    ) -> None:
        """
        Store a completed issue resolution as a two-message conversation.

        Args:
            repository_id: Repository identifier
            issue_title: Title of the issue
            issue_body: Body of the issue
            issue_response: The agent's response/resolution summary
            edit_patch: Generated patch (if any)
            issue_type: Issue type string (bug, question, feature, documentation)

        Raises:
            EvermindException: If either store request fails
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        base_id = f"repo_{repository_id}_{issue_title[:40].replace(' ', '_')}_{timestamp}"

        user_content = f"Issue ({issue_type}): {issue_title}\n{issue_body}"
        assistant_content = issue_response or ""
        if edit_patch:
            assistant_content += f"\n\nPatch:\n{edit_patch}"

        self._store_message(
            message_id=f"{base_id}_0",
            create_time=timestamp,
            sender=f"repo_{repository_id}",
            role="user",
            content=user_content,
            group_id=str(repository_id),
            group_name=f"repo_{repository_id}",
        )
        self._store_message(
            message_id=f"{base_id}_1",
            create_time=timestamp,
            sender="prometheus",
            role="assistant",
            content=assistant_content,
            group_id=str(repository_id),
            group_name=f"repo_{repository_id}",
        )

        self._logger.info(
            f"Stored conversation for repository {repository_id}, issue: {issue_title[:60]}"
        )

    def _store_message(
        self,
        message_id: str,
        create_time: str,
        sender: str,
        role: str,
        content: str,
        group_id: str,
        group_name: str,
    ) -> None:
        """
        Store a single message to Evermind.

        Raises:
            EvermindException: If the request fails
        """
        url = f"{self.base_url}/memories"
        payload = {
            "message_id": message_id,
            "create_time": create_time,
            "sender": sender,
            "role": role,
            "content": content,
            "group_id": group_id,
            "group_name": group_name,
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as e:
            self._logger.error(f"Failed to store message {message_id}: {e}")
            raise EvermindException(str(e)) from e


# Global client instance, only created when both URL and API key are configured
if settings.EVERMIND_BASE_URL and settings.EVERMIND_API_KEY:
    evermind_client: Optional[EvermindClient] = EvermindClient(
        base_url=settings.EVERMIND_BASE_URL,
        api_key=settings.EVERMIND_API_KEY,
    )
else:
    evermind_client = None


def retrieve_memories(repository_id: int, query: str, limit: int = 5) -> str:
    """
    Retrieve relevant past conversation memories for a repository.

    Args:
        repository_id: Repository identifier
        query: Natural language query derived from the current issue
        limit: Maximum number of memories to return

    Returns:
        Formatted string of retrieved memories, or empty string if none

    Raises:
        EvermindException: If client is not configured or request fails
    """
    if not evermind_client:
        raise EvermindException("Evermind client is not configured.")

    return evermind_client.retrieve_memories(
        repository_id=repository_id,
        query=query,
        limit=limit,
    )


def store_conversation(
    repository_id: int,
    issue_title: str,
    issue_body: str,
    issue_response: str,
    edit_patch: Optional[str],
    issue_type: str,
) -> None:
    """
    Store a completed issue resolution as a conversation in Evermind.

    Args:
        repository_id: Repository identifier
        issue_title: Title of the issue
        issue_body: Body of the issue
        issue_response: The agent's response/resolution summary
        edit_patch: Generated patch (if any)
        issue_type: Issue type string (bug, question, feature, documentation)

    Raises:
        EvermindException: If client is not configured or request fails
    """
    if not evermind_client:
        raise EvermindException("Evermind client is not configured.")

    evermind_client.store_conversation(
        repository_id=repository_id,
        issue_title=issue_title,
        issue_body=issue_body,
        issue_response=issue_response,
        edit_patch=edit_patch,
        issue_type=issue_type,
    )
