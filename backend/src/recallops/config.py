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
    frontend_dist: str | None

    def require_database_url(self) -> str:
        """Return the database URL only when database functionality needs it."""

        if not self.database_url:
            raise DatabaseConfigurationError(
                "DATABASE_URL is required for database functionality"
            )
        return self.database_url

    def require_bedrock(self) -> "BedrockSettings":
        """Return Bedrock settings only when AI functionality needs them."""

        region, model_id = self._require_region_and_model(
            self.bedrock_chat_model_id,
            model_id_env_var="BEDROCK_CHAT_MODEL_ID",
            purpose="AI analysis",
            error_cls=BedrockConfigurationError,
        )
        return BedrockSettings(region=region, model_id=model_id)

    def require_bedrock_embedding(self) -> "BedrockEmbeddingSettings":
        """Return embedding settings only when embedding functionality needs them."""

        region, model_id = self._require_region_and_model(
            self.bedrock_embedding_model_id,
            model_id_env_var="BEDROCK_EMBEDDING_MODEL_ID",
            purpose="embeddings",
            error_cls=BedrockEmbeddingConfigurationError,
        )
        return BedrockEmbeddingSettings(region=region, model_id=model_id)

    def _require_region_and_model(
        self,
        model_id: str | None,
        *,
        model_id_env_var: str,
        purpose: str,
        error_cls: type[RuntimeError],
    ) -> tuple[str, str]:
        """Share the strip-and-validate logic every Bedrock feature needs."""

        region = self.aws_region.strip() if self.aws_region else ""
        stripped_model_id = model_id.strip() if model_id else ""
        if not region or not stripped_model_id:
            raise error_cls(
                f"AWS_REGION and {model_id_env_var} are required for {purpose}"
            )
        return region, stripped_model_id


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
        frontend_dist=os.getenv("RECALL_OPS_FRONTEND_DIST"),
    )
