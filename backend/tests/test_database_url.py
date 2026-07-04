import pytest

from recallops.database.url import (
    UnsupportedDatabaseUrlError,
    normalize_database_url,
)


def test_normalize_database_url_preserves_ssl_verification() -> None:
    source = (
        "postgresql://fake_user:fake_password@cluster.example.invalid:26257/"
        "recallops?sslmode=verify-full"
    )

    normalized = normalize_database_url(source)

    assert normalized == (
        "cockroachdb+psycopg://fake_user:fake_password@"
        "cluster.example.invalid:26257/recallops?sslmode=verify-full"
    )


def test_normalize_database_url_rejects_unknown_scheme_safely() -> None:
    with pytest.raises(
        UnsupportedDatabaseUrlError,
        match="DATABASE_URL must use a PostgreSQL or CockroachDB URL scheme",
    ):
        normalize_database_url("mysql://sensitive-value")
