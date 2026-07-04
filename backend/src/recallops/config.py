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

    def require_database_url(self) -> str:
        """Return the database URL only when database functionality needs it."""

        if not self.database_url:
            raise DatabaseConfigurationError(
                "DATABASE_URL is required for database functionality"
            )
        return self.database_url


class DatabaseConfigurationError(RuntimeError):
    """Raised without sensitive values when database configuration is missing."""


@lru_cache
def get_settings() -> Settings:
    """Load settings from the environment, with local-development defaults."""

    return Settings(
        app_name=os.getenv("APP_NAME", "RecallOps"),
        app_env=os.getenv("APP_ENV", "development"),
        api_prefix=os.getenv("API_PREFIX", "/api"),
        database_url=os.getenv("DATABASE_URL"),
    )
