import asyncio
from typing import Dict

import httpx

from prometheus.exceptions.github_exception import GithubException


async def get_github_issue(repo: str, issue_number: int, github_token: str) -> Dict:
    """
    Retrieve issue information from GitHub asynchronously using httpx
    Args:
        repo (str): The GitHub repository in the format "owner/repo".
        issue_number (int): The issue number to retrieve.
        github_token (str): GitHub personal access token for authentication.
    """
    github_headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(headers=github_headers) as client:
        issue_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
        comments_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"

        # Send requests concurrently
        issue_response, comments_response = await asyncio.gather(
            client.get(issue_url), client.get(comments_url)
        )

        if issue_response.status_code != 200:
            raise GithubException(
                f"Failed to retrieve issue: {issue_response.status_code} - {issue_response.text}"
            )

        if comments_response.status_code != 200:
            raise GithubException(
                f"Failed to retrieve comments: {comments_response.status_code} - {comments_response.text}"
            )

        issue_data = issue_response.json()

        comments = []
        comments_data = comments_response.json()
        comments = [
            {"username": comment["user"]["login"], "comment": comment["body"]}
            for comment in comments_data
        ]

    return {
        "number": issue_data["number"],
        "title": issue_data["title"],
        "body": issue_data["body"] or "",
        "comments": comments,
        "state": issue_data["state"],
        "html_url": issue_data["html_url"],
    }


async def is_repository_public(https_url: str) -> bool:
    """
    Check if a GitHub repository is public by making an unauthenticated request.

    Args:
        https_url: HTTPS URL of the GitHub repository

    Returns:
        bool: True if the repository is public, False if private or not found
    """
    # Extract owner and repo from HTTPS URL
    # Example: https://github.com/owner/repo.git -> owner/repo
    url_parts = https_url.replace("https://github.com/", "").replace(".git", "")
    owner, repo = url_parts.split("/")
    # Make unauthenticated request to check repository visibility
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={"Accept": "application/vnd.github.v3+json"},
        )

        if response.status_code == 200:
            # Repository exists and is accessible without authentication (public)
            return True
        elif response.status_code == 404:
            # Repository not found or private (requires authentication)
            return False
        else:
            # Other error, assume private for safety
            return False
