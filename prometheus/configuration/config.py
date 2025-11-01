from typing import List, Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="PROMETHEUS_"
    )
    # General settings
    version: str = "1.3"
    BASE_URL: str = f"/v{version}"
    PROJECT_NAME: str = "Prometheus"

    ENVIRONMENT: Literal["local", "production"]
    BACKEND_CORS_ORIGINS: List[str]
    ENABLE_AUTHENTICATION: bool

    # Logging
    LOGGING_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    # Neo4j
    NEO4J_URI: str
    NEO4J_USERNAME: str
    NEO4J_PASSWORD: str
    NEO4J_BATCH_SIZE: int

    # Knowledge Graph
    WORKING_DIRECTORY: str
    KNOWLEDGE_GRAPH_MAX_AST_DEPTH: int
    KNOWLEDGE_GRAPH_CHUNK_SIZE: int
    KNOWLEDGE_GRAPH_CHUNK_OVERLAP: int

    # LLM models
    ADVANCED_MODEL: str
    BASE_MODEL: str

    # API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_FORMAT_BASE_URL: Optional[str] = None
    OPENAI_FORMAT_API_KEY: Optional[str] = None

    # Model parameters
    ADVANCED_MODEL_TEMPERATURE: Optional[float] = None

    BASE_MODEL_TEMPERATURE: Optional[float] = None

    # Database
    DATABASE_URL: str

    # JWT Configuration
    JWT_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_TIME: int = 30  # days

    # Invitation Code Expire Time
    INVITATION_CODE_EXPIRE_TIME: int = 14  # days

    # Default normal user issue credit
    DEFAULT_USER_ISSUE_CREDIT: int = 20

    # Default normal user repository number
    DEFAULT_USER_REPOSITORY_LIMIT: int = 5

    # tool for Websearch
    TAVILY_API_KEY: str

    # Athena semantic memory service
    ATHENA_BASE_URL: Optional[str] = None


settings = Settings()
