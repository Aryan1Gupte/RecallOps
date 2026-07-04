"""Alembic environment configured from RecallOps application settings."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from recallops.config import get_settings
from recallops.database.base import Base
from recallops.database.url import normalize_database_url
from recallops import models  # noqa: F401  # Register model metadata.

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Read and normalize the URL without persisting or logging it."""

    return normalize_database_url(get_settings().require_database_url())


def run_migrations_offline() -> None:
    """Generate SQL without opening a database connection."""

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations through a short-lived, securely configured engine."""

    connectable = create_engine(
        get_database_url(),
        poolclass=pool.NullPool,
        pool_pre_ping=True,
        hide_parameters=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
