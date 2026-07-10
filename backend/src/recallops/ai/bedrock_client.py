"""Shared Bedrock Runtime client construction for all AI providers."""

from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError

DEFAULT_CONNECT_TIMEOUT_SECONDS = 5
DEFAULT_READ_TIMEOUT_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 3


class BedrockClientError(RuntimeError):
    """Raised without provider details when the Bedrock client cannot be built."""


@lru_cache
def build_bedrock_runtime_client(
    region: str,
    read_timeout: int = DEFAULT_READ_TIMEOUT_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> Any:
    """Build one cached Bedrock Runtime client per region and timeout profile.

    A single client type supports both `.converse()` (chat analysis) and
    `.invoke_model()` (embeddings), so every Bedrock-backed feature should
    build its client here instead of duplicating boto3/Config setup.
    """

    try:
        return boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=DEFAULT_CONNECT_TIMEOUT_SECONDS,
                read_timeout=read_timeout,
                retries={"mode": "standard", "total_max_attempts": max_attempts},
            ),
        )
    except BotoCoreError as error:
        raise BedrockClientError("Bedrock client configuration failed") from error
