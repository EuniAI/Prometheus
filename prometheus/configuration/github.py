from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubSettings(BaseSettings):
    """GitHub App configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        env_prefix="GITHUB_",
        extra='ignore'
    )
    
    # GitHub App credentials
    APP_ID: str
    WEBHOOK_SECRET: str
    PRIVATE_KEY: str
    
    # Bot configuration
    BOT_HANDLE: str  # The GitHub username of the bot
    ORG_NAME: Optional[str] = None  # Organization name for membership validation
    
    # Installation settings
    INSTALLATION_ID: Optional[int] = None  # Optional: specific installation ID


github_settings = GitHubSettings()