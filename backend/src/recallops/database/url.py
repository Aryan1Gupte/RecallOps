"""Safe database URL normalization for CockroachDB's SQLAlchemy dialect."""


class UnsupportedDatabaseUrlError(ValueError):
    """Raised without echoing a database URL that uses an unsupported scheme."""


def normalize_database_url(database_url: str) -> str:
    """Select CockroachDB's sync psycopg dialect without changing URL details."""

    normalized_prefix = "cockroachdb+psycopg://"
    supported_prefixes = (
        "postgresql+psycopg://",
        "postgresql://",
        "cockroachdb://",
        normalized_prefix,
    )

    for prefix in supported_prefixes:
        if database_url.startswith(prefix):
            return normalized_prefix + database_url[len(prefix) :]

    raise UnsupportedDatabaseUrlError(
        "DATABASE_URL must use a PostgreSQL or CockroachDB URL scheme"
    )
