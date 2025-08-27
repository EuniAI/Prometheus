from typing import Sequence

from fastapi import APIRouter, Request

from prometheus.app.decorators.require_login import requireLogin
from prometheus.app.entity.user import User
from prometheus.app.models.requests.user import SetGithubTokenRequest
from prometheus.app.models.response.response import Response
from prometheus.app.models.response.user import UserResponse
from prometheus.app.services.user_service import UserService
from prometheus.exceptions.server_exception import ServerException

router = APIRouter()


@router.get(
    "/list/",
    summary="List all users in the database",
    description="Retrieves a list of all users.",
    response_description="Returns a list of users",
    response_model=Response[Sequence[UserResponse]],
)
@requireLogin
def list_users(request: Request) -> Response[Sequence[User]]:
    """
    List all users in the database.
    """
    # Check if the user is an admin
    user_service: UserService = request.app.state.service["user_service"]
    if not user_service.is_admin(request.state.user_id):
        raise ServerException(code=403, message="Only admins can list users")

    # List all users
    users = user_service.list_users()
    return Response(data=[UserResponse.model_validate(user) for user in users])


@router.put(
    "/set-github-token/",
    summary="Set GitHub token for the user",
    description="Sets the GitHub token for the authenticated user.",
    response_description="Returns the updated user information",
    response_model=Response,
)
@requireLogin
def set_github_token(request: Request, set_github_token_request: SetGithubTokenRequest) -> Response:
    """
    Set GitHub token for the user.
    """
    user_service: UserService = request.app.state.service["user_service"]

    # Update the user's GitHub token
    user_service.set_github_token(request.state.user_id, set_github_token_request.github_token)
    return Response()
