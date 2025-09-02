import asyncio
from typing import Dict

import httpx


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
            raise Exception(
                f"Failed to retrieve issue: {issue_response.status_code} - {issue_response.text}"
            )

        if comments_response.status_code != 200:
            raise Exception(
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
