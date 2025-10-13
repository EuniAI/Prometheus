from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    """GitHub App configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra='ignore'
    )
    
    # GitHub App credentials
    APP_ID: str = Field(..., env='GITHUB_APP_ID')
    WEBHOOK_SECRET: str = Field(..., env='GITHUB_WEBHOOK_SECRET')
    PRIVATE_KEY: str = Field(..., env='GITHUB_PRIVATE_KEY')
    
    # Bot configuration
    BOT_HANDLE: str = Field(..., env='GITHUB_BOT_HANDLE')  # The GitHub username of the bot
    ORG_NAME: Optional[str] = Field(None, env='GITHUB_ORG_NAME')  # Organization name for membership validation
    
    # Installation settings
    INSTALLATION_ID: Optional[int] = None  # Optional: specific installation ID


github_settings = GitHubSettings()