"""Environment-based application configuration."""

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    """Configuration values supported by the initial scaffold."""

    app_name: str
    app_env: str
    api_prefix: str


@lru_cache
def get_settings() -> Settings:
    """Load settings from the environment, with local-development defaults."""

    return Settings(
        app_name=os.getenv("APP_NAME", "RecallOps"),
        app_env=os.getenv("APP_ENV", "development"),
        api_prefix=os.getenv("API_PREFIX", "/api"),
    )
