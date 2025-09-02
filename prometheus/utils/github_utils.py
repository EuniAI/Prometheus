from typing import Dict

import requests


def get_github_issue(repo: str, issue_number: int, github_token: str) -> Dict:
    """
    Retrieve issue information from GitHub

    Args:
        repo: Repository name (format: owner/repo)
        issue_number: Issue number
        github_token: GitHub token

    Returns:
        A dictionary containing issue information
    """
    github_headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Retrieve basic issue information
    issue_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    response = requests.get(issue_url, headers=github_headers)

    if response.status_code != 200:
        raise Exception(f"Failed to retrieve issue: {response.status_code} - {response.text}")

    issue_data = response.json()

    # Retrieve issue comments
    comments_url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    comments_response = requests.get(comments_url, headers=github_headers)

    comments = []
    if comments_response.status_code == 200:
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
