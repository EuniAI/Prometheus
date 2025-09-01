from pydantic import BaseModel, Field


class SetGithubTokenRequest(BaseModel):
    github_token: str = Field(description="GitHub token of the user", max_length=100)
