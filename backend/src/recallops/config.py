"""Environment-based application configuration."""

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    """Application configuration loaded from process environment variables."""

    app_name: str
    app_env: str
    api_prefix: str
    database_url: str | None
    aws_region: str | None
    bedrock_chat_model_id: str | None
    bedrock_embedding_model_id: str | None

    def require_database_url(self) -> str:
        """Return the database URL only when database functionality needs it."""

        if not self.database_url:
            raise DatabaseConfigurationError(
                "DATABASE_URL is required for database functionality"
            )
        return self.database_url

    def require_bedrock(self) -> "BedrockSettings":
        """Return Bedrock settings only when AI functionality needs them."""

        region = self.aws_region.strip() if self.aws_region else ""
        model_id = (
            self.bedrock_chat_model_id.strip() if self.bedrock_chat_model_id else ""
        )
        if not region or not model_id:
            raise BedrockConfigurationError(
                "AWS_REGION and BEDROCK_CHAT_MODEL_ID are required for AI analysis"
            )
        return BedrockSettings(
            region=region,
            model_id=model_id,
        )

    def require_bedrock_embedding(self) -> "BedrockEmbeddingSettings":
        """Return embedding settings only when embedding functionality needs them."""

        region = self.aws_region.strip() if self.aws_region else ""
        model_id = (
            self.bedrock_embedding_model_id.strip()
            if self.bedrock_embedding_model_id
            else ""
        )
        if not region or not model_id:
            raise BedrockEmbeddingConfigurationError(
                "AWS_REGION and BEDROCK_EMBEDDING_MODEL_ID are required for embeddings"
            )
        return BedrockEmbeddingSettings(region=region, model_id=model_id)


@dataclass(frozen=True)
class BedrockSettings:
    """Non-secret settings needed to call Amazon Bedrock."""

    region: str
    model_id: str


@dataclass(frozen=True)
class BedrockEmbeddingSettings:
    """Non-secret settings needed to call the Bedrock embedding model."""

    region: str
    model_id: str


class DatabaseConfigurationError(RuntimeError):
    """Raised without sensitive values when database configuration is missing."""


class BedrockConfigurationError(RuntimeError):
    """Raised safely when lazy Bedrock configuration is incomplete."""


class BedrockEmbeddingConfigurationError(RuntimeError):
    """Raised safely when lazy embedding configuration is incomplete."""


@lru_cache
def get_settings() -> Settings:
    """Load settings from the environment, with local-development defaults."""

    return Settings(
        app_name=os.getenv("APP_NAME", "RecallOps"),
        app_env=os.getenv("APP_ENV", "development"),
        api_prefix=os.getenv("API_PREFIX", "/api"),
        database_url=os.getenv("DATABASE_URL"),
        aws_region=os.getenv("AWS_REGION"),
        bedrock_chat_model_id=os.getenv("BEDROCK_CHAT_MODEL_ID"),
        bedrock_embedding_model_id=os.getenv("BEDROCK_EMBEDDING_MODEL_ID"),
    )
