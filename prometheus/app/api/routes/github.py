from typing import Dict

from fastapi import APIRouter

from prometheus.app.models.response.response import Response
from prometheus.exceptions.github_exception import GithubException
from prometheus.exceptions.server_exception import ServerException
from prometheus.utils.github_utils import get_github_issue, is_repository_public

router = APIRouter()


@router.get(
    "/issue/",
    summary="Get GitHub issue details",
    description="Get Github Issue details including title, body, and comments.",
    response_description="Returns an object containing issue details",
    response_model=Response[Dict],
)
async def get_github_issue_(
    repo: str, issue_number: int, github_token: str | None
) -> Response[Dict]:
    """
    Get GitHub issue details including title, body, and comments.

    Args:
        repo (str): The GitHub repository in the format "owner/repo".
        issue_number (int): The issue number to retrieve.
        github_token (str): The GitHub token to use.

    Returns:
        Response[Dict]: A response object containing issue details.
    """
    is_repository_public_ = await is_repository_public(repo)
    if not is_repository_public_ and not github_token:
        raise ServerException(
            code=400,
            message="The repository is private or not exists. Please provide a valid GitHub token.",
        )

    try:
        issue_data = await get_github_issue(repo, issue_number, github_token)
    except GithubException as e:
        raise ServerException(code=400, message=str(e))
    return Response(data=issue_data)
